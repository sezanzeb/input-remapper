#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2020 sezanzeb <proxima@hip70890b.de>
#
# This file is part of key-mapper.
#
# key-mapper is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# key-mapper is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with key-mapper.  If not, see <https://www.gnu.org/licenses/>.


import unittest
import time

import evdev
from evdev.ecodes import EV_REL, EV_KEY, EV_ABS

from keymapper.dev.injector import is_numlock_on, toggle_numlock,\
    ensure_numlock, KeycodeInjector
from keymapper.state import custom_mapping, system_mapping, \
    clear_system_mapping, KEYCODE_OFFSET
from keymapper.mapping import Mapping
from keymapper.config import config

from test import uinput_write_history, Event, pending_events, fixtures, \
    clear_write_history, EVENT_READ_TIMEOUT, uinput_write_history_pipe, \
    MAX_ABS


class TestInjector(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.injector = None
        cls.grab = evdev.InputDevice.grab

    def setUp(self):
        self.failed = 0

        def grab_fail_twice(_):
            if self.failed < 2:
                self.failed += 1
                raise OSError()

        evdev.InputDevice.grab = grab_fail_twice

    def tearDown(self):
        if self.injector is not None:
            self.injector.stop_injecting()
            self.injector = None
        evdev.InputDevice.grab = self.grab
        if pending_events.get('device 2') is not None:
            del pending_events['device 2']
        clear_write_history()

    def test_modify_capabilities(self):
        class FakeDevice:
            def capabilities(self, absinfo=True):
                assert absinfo is False
                return {
                    evdev.ecodes.EV_SYN: [1, 2, 3],
                    evdev.ecodes.EV_FF: [1, 2, 3]
                }

        mapping = Mapping()
        mapping.change(
            new_keycode=80,
            character='a'
        )

        maps_to = system_mapping['a'] - KEYCODE_OFFSET

        self.injector = KeycodeInjector('foo', mapping)
        capabilities = self.injector._modify_capabilities(FakeDevice())

        self.assertIn(EV_KEY, capabilities)
        keys = capabilities[EV_KEY]
        self.assertEqual(keys[0], maps_to)

        self.assertNotIn(evdev.ecodes.EV_SYN, capabilities)
        self.assertNotIn(evdev.ecodes.EV_FF, capabilities)

    def test_grab(self):
        # path is from the fixtures
        custom_mapping.change(10, 'a')

        self.injector = KeycodeInjector('device 1', custom_mapping)
        path = '/dev/input/event10'
        # this test needs to pass around all other constraints of
        # _prepare_device
        device = self.injector._prepare_device(path)
        self.assertEqual(self.failed, 2)
        # success on the third try
        device.name = fixtures[path]['name']

    def test_skip_unused_device(self):
        # skips a device because its capabilities are not used in the mapping
        custom_mapping.change(10, 'a')
        self.injector = KeycodeInjector('device 1', custom_mapping)
        path = '/dev/input/event11'
        device = self.injector._prepare_device(path)
        self.assertEqual(self.failed, 0)
        self.assertIsNone(device)

    def test_skip_unknown_device(self):
        # skips a device because its capabilities are not used in the mapping
        self.injector = KeycodeInjector('device 1', custom_mapping)
        path = '/dev/input/event11'
        device = self.injector._prepare_device(path)

        # make sure the test uses a fixture without interesting capabilities
        capabilities = evdev.InputDevice(path).capabilities()
        self.assertEqual(len(capabilities.get(EV_KEY, [])), 0)
        self.assertEqual(len(capabilities.get(EV_ABS, [])), 0)

        # skips the device alltogether, so no grab attempts fail
        self.assertEqual(self.failed, 0)
        self.assertIsNone(device)

    def test_numlock(self):
        before = is_numlock_on()

        toggle_numlock()  # should change
        self.assertEqual(not before, is_numlock_on())

        @ensure_numlock
        def wrapped():
            toggle_numlock()

        wrapped()  # should not change
        self.assertEqual(not before, is_numlock_on())

        # toggle one more time to restore the previous configuration
        toggle_numlock()
        self.assertEqual(before, is_numlock_on())

    def test_abs_to_rel(self):
        # maps gamepad joystick events to mouse events
        # TODO enable this somewhere so that map_abs_to_rel returns true
        #  in the .json file of the mapping.
        config.set('gamepad.non_linearity', 1)
        pointer_speed = 80
        config.set('gamepad.pointer_speed', pointer_speed)

        # same for ABS, 0 for x, 1 for y
        rel_x = evdev.ecodes.REL_X
        rel_y = evdev.ecodes.REL_Y

        # they need to sum up before something is written
        divisor = 10
        x = MAX_ABS / pointer_speed / divisor
        y = MAX_ABS / pointer_speed / divisor
        pending_events['gamepad'] = [
            Event(EV_ABS, rel_x, x),
            Event(EV_ABS, rel_y, y),
            Event(EV_ABS, rel_x, -x),
            Event(EV_ABS, rel_y, -y),
        ]

        self.injector = KeycodeInjector('gamepad', custom_mapping)
        self.injector.start_injecting()

        # wait for the injector to start sending, at most 1s
        uinput_write_history_pipe[0].poll(1)

        # wait a bit more for it to sum up
        sleep = 0.5
        time.sleep(sleep)

        # convert the write history to some easier to manage list
        history = []
        while uinput_write_history_pipe[0].poll():
            event = uinput_write_history_pipe[0].recv()
            history.append((event.type, event.code, event.value))

        # movement is written at 60hz and it takes `divisor` steps to
        # move 1px. take it times 2 for both x and y events.
        self.assertGreater(len(history), 60 * sleep * 0.9 * 2 / divisor)
        self.assertLess(len(history), 60 * sleep * 1.1 * 2 / divisor)

        # those may be in arbitrary order, the injector happens to write
        # y first
        self.assertEqual(history[-1][0], EV_REL)
        self.assertEqual(history[-1][1], rel_x)
        self.assertAlmostEqual(history[-1][2], -1)
        self.assertEqual(history[-2][0], EV_REL)
        self.assertEqual(history[-2][1], rel_y)
        self.assertAlmostEqual(history[-2][2], -1)

    def test_injector(self):
        custom_mapping.change(8, 'k(q).k(w)')
        custom_mapping.change(9, 'a')
        # one mapping that is unknown in the system_mapping on purpose
        custom_mapping.change(10, 'b')

        clear_system_mapping()
        code_a = 100
        code_q = 101
        code_w = 102
        system_mapping['a'] = code_a
        system_mapping['q'] = code_q
        system_mapping['w'] = code_w

        # the second arg of those event objects is 8 lower than the
        # keycode used in X and in the mappings
        pending_events['device 2'] = [
            # should execute a macro
            Event(EV_KEY, 0, 1),
            Event(EV_KEY, 0, 0),
            # normal keystroke
            Event(EV_KEY, 1, 1),
            Event(EV_KEY, 1, 0),
            # ignored because unknown to the system
            Event(EV_KEY, 2, 1),
            Event(EV_KEY, 2, 0),
            # just pass those over without modifying
            Event(3124, 3564, 6542),
        ]

        self.injector = KeycodeInjector('device 2', custom_mapping)
        self.injector.start_injecting()

        uinput_write_history_pipe[0].poll(timeout=1)
        time.sleep(EVENT_READ_TIMEOUT * 10)

        # convert the write history to some easier to manage list
        history = []
        while uinput_write_history_pipe[0].poll():
            event = uinput_write_history_pipe[0].recv()
            history.append((event.type, event.code, event.value))

        # 4 events for the macro
        # 3 for non-macros
        self.assertEqual(len(history), 7)

        # since the macro takes a little bit of time to execute, its
        # keystrokes are all over the place.
        # just check if they are there and if so, remove them from the list.
        ev_key = EV_KEY
        self.assertIn((ev_key, code_q - KEYCODE_OFFSET, 1), history)
        self.assertIn((ev_key, code_q - KEYCODE_OFFSET, 0), history)
        self.assertIn((ev_key, code_w - KEYCODE_OFFSET, 1), history)
        self.assertIn((ev_key, code_w - KEYCODE_OFFSET, 0), history)
        index_q_1 = history.index((ev_key, code_q - KEYCODE_OFFSET, 1))
        index_q_0 = history.index((ev_key, code_q - KEYCODE_OFFSET, 0))
        index_w_1 = history.index((ev_key, code_w - KEYCODE_OFFSET, 1))
        index_w_0 = history.index((ev_key, code_w - KEYCODE_OFFSET, 0))
        self.assertGreater(index_q_0, index_q_1)
        self.assertGreater(index_w_1, index_q_0)
        self.assertGreater(index_w_0, index_w_1)
        del history[index_q_1]
        index_q_0 = history.index((ev_key, code_q - KEYCODE_OFFSET, 0))
        del history[index_q_0]
        index_w_1 = history.index((ev_key, code_w - KEYCODE_OFFSET, 1))
        del history[index_w_1]
        index_w_0 = history.index((ev_key, code_w - KEYCODE_OFFSET, 0))
        del history[index_w_0]

        # the rest should be in order.
        self.assertEqual(history[0], (ev_key, code_a - KEYCODE_OFFSET, 1))
        self.assertEqual(history[1], (ev_key, code_a - KEYCODE_OFFSET, 0))
        self.assertEqual(history[2], (3124, 3564, 6542))


if __name__ == "__main__":
    unittest.main()
