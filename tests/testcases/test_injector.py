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
import copy

import evdev
from evdev.ecodes import EV_REL, EV_KEY, EV_ABS, ABS_HAT0X, BTN_A

from keymapper.dev.injector import is_numlock_on, set_numlock, \
    ensure_numlock, KeycodeInjector, store_permutations, is_in_capabilities
from keymapper.state import custom_mapping, system_mapping
from keymapper.mapping import Mapping
from keymapper.config import config
from keymapper.dev.macros import parse

from tests.test import InputEvent, pending_events, fixtures, \
    EVENT_READ_TIMEOUT, uinput_write_history_pipe, \
    MAX_ABS, cleanup


class TestInjector(unittest.TestCase):
    new_gamepad = '/dev/input/event100'

    @classmethod
    def setUpClass(cls):
        cls.injector = None
        cls.grab = evdev.InputDevice.grab

    def setUp(self):
        self.failed = 0
        self.make_it_fail = 2

        def grab_fail_twice(_):
            if self.failed < self.make_it_fail:
                self.failed += 1
                raise OSError()

        evdev.InputDevice.grab = grab_fail_twice

    def tearDown(self):
        if self.injector is not None:
            self.injector.stop_injecting()
            self.injector = None
        evdev.InputDevice.grab = self.grab

        cleanup()

    def test_modify_capabilities(self):
        class FakeDevice:
            def capabilities(self, absinfo=True):
                assert absinfo is False
                return {
                    evdev.ecodes.EV_SYN: [1, 2, 3],
                    evdev.ecodes.EV_FF: [1, 2, 3],
                    evdev.ecodes.EV_ABS: [1, 2, 3]
                }

        mapping = Mapping()
        mapping.change((EV_KEY, 80, 1), 'a')

        macro_code = 'r(2, m(sHiFt_l, r(2, k(1).k(2))))'
        macro = parse(macro_code, mapping)

        mapping.change((EV_KEY, 60, 111), macro_code)

        # going to be ignored, because EV_REL cannot be mapped, that's
        # mouse movements.
        mapping.change((EV_REL, 1234, 3), 'b')

        a = system_mapping.get('a')
        shift_l = system_mapping.get('ShIfT_L')
        one = system_mapping.get(1)
        two = system_mapping.get('2')

        self.injector = KeycodeInjector('foo', mapping)
        fake_device = FakeDevice()
        capabilities = self.injector._modify_capabilities(
            {60: macro},
            fake_device,
            abs_to_rel=False
        )

        self.assertIn(EV_KEY, capabilities)
        keys = capabilities[EV_KEY]
        self.assertIn(a, keys)
        self.assertIn(one, keys)
        self.assertIn(two, keys)
        self.assertIn(shift_l, keys)

        self.assertNotIn(evdev.ecodes.EV_SYN, capabilities)
        self.assertNotIn(evdev.ecodes.EV_FF, capabilities)
        self.assertNotIn(evdev.ecodes.EV_REL, capabilities)
        self.assertNotIn(evdev.ecodes.EV_ABS, capabilities)

    def test_grab(self):
        # path is from the fixtures
        custom_mapping.change((EV_KEY, 10, 1), 'a')

        self.injector = KeycodeInjector('device 1', custom_mapping)
        path = '/dev/input/event10'
        # this test needs to pass around all other constraints of
        # _prepare_device
        device, abs_to_rel = self.injector._prepare_device(path)
        self.assertFalse(abs_to_rel)
        self.assertEqual(self.failed, 2)
        # success on the third try
        device.name = fixtures[path]['name']

    def test_fail_grab(self):
        self.make_it_fail = 10
        custom_mapping.change((EV_KEY, 10, 1), 'a')

        self.injector = KeycodeInjector('device 1', custom_mapping)
        path = '/dev/input/event10'
        device, abs_to_rel = self.injector._prepare_device(path)
        self.assertFalse(abs_to_rel)
        self.assertGreaterEqual(self.failed, 1)
        self.assertIsNone(device)

        self.injector.start_injecting()
        # since none can be grabbed, the process will terminate. But that
        # actually takes quite some time.
        time.sleep(1.5)
        self.assertFalse(self.injector._process.is_alive())

    def test_prepare_device_1(self):
        # according to the fixtures, /dev/input/event30 can do ABS_HAT0X
        custom_mapping.change((EV_ABS, ABS_HAT0X, 1), 'a')
        self.injector = KeycodeInjector('foobar', custom_mapping)

        _prepare_device = self.injector._prepare_device
        self.assertIsNone(_prepare_device('/dev/input/event10')[0])
        self.assertIsNotNone(_prepare_device('/dev/input/event30')[0])

    def test_prepare_device_non_existing(self):
        custom_mapping.change((EV_ABS, ABS_HAT0X, 1), 'a')
        self.injector = KeycodeInjector('foobar', custom_mapping)

        _prepare_device = self.injector._prepare_device
        self.assertIsNone(_prepare_device('/dev/input/event1234')[0])

    def test_gamepad_capabilities(self):
        self.injector = KeycodeInjector('gamepad', custom_mapping)

        path = '/dev/input/event30'
        device, abs_to_rel = self.injector._prepare_device(path)
        self.assertTrue(abs_to_rel)

        capabilities = self.injector._modify_capabilities(
            {},
            device,
            abs_to_rel
        )
        self.assertNotIn(evdev.ecodes.EV_ABS, capabilities)
        self.assertIn(evdev.ecodes.EV_REL, capabilities)

        self.assertIn(evdev.ecodes.REL_X, capabilities.get(EV_REL))
        self.assertIn(evdev.ecodes.REL_Y, capabilities.get(EV_REL))
        self.assertIn(evdev.ecodes.REL_WHEEL, capabilities.get(EV_REL))
        self.assertIn(evdev.ecodes.REL_HWHEEL, capabilities.get(EV_REL))

        self.assertIn(evdev.ecodes.EV_KEY, capabilities)
        self.assertEqual(len(capabilities[evdev.ecodes.EV_KEY]), 1)

    def test_adds_ev_key(self):
        # for some reason, having any EV_KEY capability is needed to
        # be able to control the mouse. it probably wants the mouse click.
        self.injector = KeycodeInjector('gamepad 2', custom_mapping)

        """gamepad without any existing key capability"""

        path = self.new_gamepad
        gamepad_template = copy.deepcopy(fixtures['/dev/input/event30'])
        fixtures[path] = {
            'name': 'gamepad 2',
            'phys': 'abcd',
            'info': '1234',
            'capabilities': gamepad_template['capabilities']
        }
        del fixtures[path]['capabilities'][EV_KEY]
        device, abs_to_rel = self.injector._prepare_device(path)
        self.assertNotIn(EV_KEY, device.capabilities())
        capabilities = self.injector._modify_capabilities(
            {},
            device,
            abs_to_rel
        )
        self.assertIn(EV_KEY, capabilities)
        self.assertIn(evdev.ecodes.BTN_MOUSE, capabilities[EV_KEY])

        """gamepad with existing key capabilities, but not btn_mouse"""

        path = '/dev/input/event30'
        device, abs_to_rel = self.injector._prepare_device(path)
        self.assertIn(EV_KEY, device.capabilities())
        self.assertNotIn(evdev.ecodes.BTN_MOUSE, device.capabilities()[EV_KEY])
        capabilities = self.injector._modify_capabilities(
            {},
            device,
            abs_to_rel
        )
        self.assertIn(EV_KEY, capabilities)
        self.assertIn(evdev.ecodes.BTN_MOUSE, capabilities[EV_KEY])

    def test_skip_unused_device(self):
        # skips a device because its capabilities are not used in the mapping
        custom_mapping.change((EV_KEY, 10, 1), 'a')
        self.injector = KeycodeInjector('device 1', custom_mapping)
        path = '/dev/input/event11'
        device, abs_to_rel = self.injector._prepare_device(path)
        self.assertFalse(abs_to_rel)
        self.assertEqual(self.failed, 0)
        self.assertIsNone(device)

    def test_skip_unknown_device(self):
        # skips a device because its capabilities are not used in the mapping
        self.injector = KeycodeInjector('device 1', custom_mapping)
        path = '/dev/input/event11'
        device, _ = self.injector._prepare_device(path)

        # make sure the test uses a fixture without interesting capabilities
        capabilities = evdev.InputDevice(path).capabilities()
        self.assertEqual(len(capabilities.get(EV_KEY, [])), 0)
        self.assertEqual(len(capabilities.get(EV_ABS, [])), 0)

        # skips the device alltogether, so no grab attempts fail
        self.assertEqual(self.failed, 0)
        self.assertIsNone(device)

    def test_numlock(self):
        before = is_numlock_on()

        set_numlock(not before)  # should change
        self.assertEqual(not before, is_numlock_on())

        @ensure_numlock
        def wrapped_1():
            set_numlock(not is_numlock_on())

        @ensure_numlock
        def wrapped_2():
            pass

        # should not change
        wrapped_1()
        self.assertEqual(not before, is_numlock_on())
        wrapped_2()
        self.assertEqual(not before, is_numlock_on())

        # toggle one more time to restore the previous configuration
        set_numlock(before)
        self.assertEqual(before, is_numlock_on())

    def test_abs_to_rel(self):
        # maps gamepad joystick events to mouse events
        config.set('gamepad.joystick.non_linearity', 1)
        pointer_speed = 80
        config.set('gamepad.joystick.pointer_speed', pointer_speed)

        # same for ABS, 0 for x, 1 for y
        rel_x = evdev.ecodes.REL_X
        rel_y = evdev.ecodes.REL_Y

        # they need to sum up before something is written
        divisor = 10
        x = MAX_ABS / pointer_speed / divisor
        y = MAX_ABS / pointer_speed / divisor
        pending_events['gamepad'] = [
            InputEvent(EV_ABS, rel_x, x),
            InputEvent(EV_ABS, rel_y, y),
            InputEvent(EV_ABS, rel_x, -x),
            InputEvent(EV_ABS, rel_y, -y),
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

        if history[0][0] == EV_ABS:
            raise AssertionError(
                'The injector probably just forwarded them unchanged'
            )

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
        # the tests in test_keycode_mapper.py test this stuff in detail

        numlock_before = is_numlock_on()

        combination = ((EV_KEY, 8, 1), (EV_KEY, 9, 1))
        custom_mapping.change(combination, 'k(KEY_Q).k(w)')
        custom_mapping.change((EV_ABS, ABS_HAT0X, -1), 'a')
        # one mapping that is unknown in the system_mapping on purpose
        input_b = 10
        custom_mapping.change((EV_KEY, input_b, 1), 'b')

        # stuff the custom_mapping outputs (except for the unknown b)
        system_mapping.clear()
        code_a = 100
        code_q = 101
        code_w = 102
        system_mapping._set('a', code_a)
        system_mapping._set('key_q', code_q)
        system_mapping._set('w', code_w)

        pending_events['device 2'] = [
            # should execute a macro...
            InputEvent(EV_KEY, 8, 1),
            InputEvent(EV_KEY, 9, 1),  # ...now
            InputEvent(EV_KEY, 8, 0),
            InputEvent(EV_KEY, 9, 0),
            # gamepad stuff. trigger a combination
            InputEvent(EV_ABS, ABS_HAT0X, -1),
            InputEvent(EV_ABS, ABS_HAT0X, 0),
            # just pass those over without modifying
            InputEvent(EV_KEY, 10, 1),
            InputEvent(EV_KEY, 10, 0),
            InputEvent(3124, 3564, 6542),
        ]

        self.injector = KeycodeInjector('device 2', custom_mapping)
        self.injector.start_injecting()

        uinput_write_history_pipe[0].poll(timeout=1)
        time.sleep(EVENT_READ_TIMEOUT * 10)

        # sending anything arbitrary does not stop the process
        # (is_alive checked later after some time)
        self.injector._msg_pipe[1].send(1234)

        # convert the write history to some easier to manage list
        history = []
        while uinput_write_history_pipe[0].poll():
            event = uinput_write_history_pipe[0].recv()
            history.append((event.type, event.code, event.value))

        # 1 event before the combination was triggered (+1 for release)
        # 4 events for the macro
        # 2 for mapped keys
        # 3 for forwarded events
        self.assertEqual(len(history), 11)

        # since the macro takes a little bit of time to execute, its
        # keystrokes are all over the place.
        # just check if they are there and if so, remove them from the list.
        self.assertIn((EV_KEY, 8, 1), history)
        self.assertIn((EV_KEY, code_q, 1), history)
        self.assertIn((EV_KEY, code_q, 1), history)
        self.assertIn((EV_KEY, code_q, 0), history)
        self.assertIn((EV_KEY, code_w, 1), history)
        self.assertIn((EV_KEY, code_w, 0), history)
        index_q_1 = history.index((EV_KEY, code_q, 1))
        index_q_0 = history.index((EV_KEY, code_q, 0))
        index_w_1 = history.index((EV_KEY, code_w, 1))
        index_w_0 = history.index((EV_KEY, code_w, 0))
        self.assertGreater(index_q_0, index_q_1)
        self.assertGreater(index_w_1, index_q_0)
        self.assertGreater(index_w_0, index_w_1)
        del history[index_q_1]
        index_q_0 = history.index((EV_KEY, code_q, 0))
        del history[index_q_0]
        index_w_1 = history.index((EV_KEY, code_w, 1))
        del history[index_w_1]
        index_w_0 = history.index((EV_KEY, code_w, 0))
        del history[index_w_0]

        # the rest should be in order.
        # first the incomplete combination key that wasn't mapped to anything
        # and just forwarded. The input event that triggered the macro
        # won't appear here.
        self.assertEqual(history[0], (EV_KEY, 8, 1))
        self.assertEqual(history[1], (EV_KEY, 8, 0))
        # value should be 1, even if the input event was -1.
        # Injected keycodes should always be either 0 or 1
        self.assertEqual(history[2], (EV_KEY, code_a, 1))
        self.assertEqual(history[3], (EV_KEY, code_a, 0))
        self.assertEqual(history[4], (EV_KEY, input_b, 1))
        self.assertEqual(history[5], (EV_KEY, input_b, 0))
        self.assertEqual(history[6], (3124, 3564, 6542))

        time.sleep(0.1)
        self.assertTrue(self.injector._process.is_alive())

        numlock_after = is_numlock_on()
        self.assertEqual(numlock_before, numlock_after)

    def test_store_permutations(self):
        target = {}

        store_permutations(target, ((1,), (2,), (3,), (4,)), 1234)
        self.assertEqual(len(target), 6)
        self.assertEqual(target[((1,), (2,), (3,), (4,))], 1234)
        self.assertEqual(target[((1,), (3,), (2,), (4,))], 1234)
        self.assertEqual(target[((2,), (1,), (3,), (4,))], 1234)
        self.assertEqual(target[((2,), (3,), (1,), (4,))], 1234)
        self.assertEqual(target[((3,), (1,), (2,), (4,))], 1234)
        self.assertEqual(target[((3,), (2,), (1,), (4,))], 1234)

        store_permutations(target, ((1,), (2,)), 5678)
        self.assertEqual(len(target), 7)
        self.assertEqual(target[((1,), (2,))], 5678)

        store_permutations(target, ((1,),), 3456)
        self.assertEqual(len(target), 8)
        self.assertEqual(target[((1,),)], 3456)

        store_permutations(target, (1,), 7890)
        self.assertEqual(len(target), 9)
        self.assertEqual(target[(1,)], 7890)

        # only accepts tuples, because key-mapper always uses tuples
        # for this stuff
        store_permutations(target, 1, 1357)
        self.assertEqual(len(target), 9)

    def test_store_permutations_for_macros(self):
        mapping = Mapping()
        ev_1 = (EV_KEY, 41, 1)
        ev_2 = (EV_KEY, 42, 1)
        ev_3 = (EV_KEY, 43, 1)
        # a combination
        mapping.change((ev_1, ev_2, ev_3), 'k(a)')
        self.injector = KeycodeInjector('device 1', mapping)

        history = []

        class Stop(Exception):
            pass

        def _modify_capabilities(*args):
            history.append(args)
            # avoid going into any mainloop
            raise Stop()

        self.injector._modify_capabilities = _modify_capabilities
        try:
            self.injector._start_injecting()
        except Stop:
            pass

        # one call
        self.assertEqual(len(history), 1)
        # first argument of the first call
        self.assertEqual(len(history[0][0]), 2)
        self.assertEqual(history[0][0][(ev_1, ev_2, ev_3)].code, 'k(a)')
        self.assertEqual(history[0][0][(ev_2, ev_1, ev_3)].code, 'k(a)')

    def test_key_to_code(self):
        mapping = Mapping()
        ev_1 = (EV_KEY, 41, 1)
        ev_2 = (EV_KEY, 42, 1)
        ev_3 = (EV_KEY, 43, 1)
        ev_4 = (EV_KEY, 44, 1)
        mapping.change(ev_1, 'a')
        # a combination
        mapping.change((ev_2, ev_3, ev_4), 'b')
        self.assertEqual(mapping.get_character((ev_2, ev_3, ev_4)), 'b')

        system_mapping.clear()
        system_mapping._set('a', 51)
        system_mapping._set('b', 52)

        injector = KeycodeInjector('device 1', mapping)
        self.assertEqual(injector._key_to_code.get(ev_1), 51)
        # permutations to make matching combinations easier
        self.assertEqual(injector._key_to_code.get((ev_2, ev_3, ev_4)), 52)
        self.assertEqual(injector._key_to_code.get((ev_3, ev_2, ev_4)), 52)
        self.assertEqual(len(injector._key_to_code), 3)

    def test_is_in_capabilities(self):
        key = (1, 2, 1)
        capabilities = {
            1: [9, 2, 5]
        }
        self.assertTrue(is_in_capabilities(key, capabilities))

        key = ((1, 2, 1), (1, 3, 1))
        capabilities = {
            1: [9, 2, 5]
        }
        # only one of the codes of the combination is required.
        # The goal is to make combinations across those sub-devices possible,
        # that make up one hardware device
        self.assertTrue(is_in_capabilities(key, capabilities))

        key = ((1, 2, 1), (1, 5, 1))
        capabilities = {
            1: [9, 2, 5]
        }
        self.assertTrue(is_in_capabilities(key, capabilities))


if __name__ == "__main__":
    unittest.main()
