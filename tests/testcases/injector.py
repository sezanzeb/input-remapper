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

import evdev

from keymapper.dev.injector import is_numlock_on, toggle_numlock,\
    ensure_numlock, KeycodeInjector
from keymapper.state import custom_mapping, system_mapping, \
    clear_system_mapping, KEYCODE_OFFSET
from keymapper.mapping import Mapping

from test import uinput_write_history, Event, pending_events, fixtures, \
    clear_write_history


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

        self.injector = KeycodeInjector('foo', Mapping())
        capabilities = self.injector._modify_capabilities(FakeDevice())

        self.assertIn(evdev.ecodes.EV_KEY, capabilities)
        self.assertIsInstance(capabilities[evdev.ecodes.EV_KEY], list)
        self.assertIsInstance(capabilities[evdev.ecodes.EV_KEY][0], int)

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

        # make sure the test uses a fixture without capabilities
        capabilities = evdev.InputDevice(path).capabilities()
        self.assertEqual(len(capabilities[evdev.ecodes.EV_KEY]), 0)

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
            Event(evdev.events.EV_KEY, 0, 1),
            Event(evdev.events.EV_KEY, 0, 0),
            # normal keystroke
            Event(evdev.events.EV_KEY, 1, 1),
            Event(evdev.events.EV_KEY, 1, 0),
            # ignored because unknown to the system
            Event(evdev.events.EV_KEY, 2, 1),
            Event(evdev.events.EV_KEY, 2, 0),
            # just pass those over without modifying
            Event(3124, 3564, 6542),
        ]

        self.injector = KeycodeInjector('device 2', custom_mapping)
        # don't start as process for coverage testing purposes
        self.injector._start_injecting()

        self.assertEqual(len(uinput_write_history), 7)

        # convert the write history to some easier to manage list
        history = [
            (event.type, event.code, event.value)
            for event in uinput_write_history
        ]

        # since the macro takes a little bit of time to execute, its
        # keystrokes are all over the place.
        # just check if they are there and if so, remove them from the list.
        ev_key = evdev.events.EV_KEY
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
