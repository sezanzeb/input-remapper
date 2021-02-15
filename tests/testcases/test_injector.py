#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@hip70890b.de>
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
from evdev.ecodes import EV_REL, EV_KEY, EV_ABS, ABS_HAT0X, BTN_LEFT, KEY_A, \
    REL_X, REL_Y, REL_WHEEL, REL_HWHEEL, BTN_A, ABS_X, ABS_Y, \
    ABS_Z, ABS_RZ, ABS_VOLUME

from keymapper.injection.injector import Injector, is_in_capabilities, \
    STARTING, RUNNING, STOPPED, NO_GRAB, UNKNOWN
from keymapper.injection.numlock import is_numlock_on, set_numlock, \
    ensure_numlock
from keymapper.state import custom_mapping, system_mapping
from keymapper.mapping import Mapping, DISABLE_CODE, DISABLE_NAME
from keymapper.config import config, NONE, MOUSE, WHEEL, BUTTONS
from keymapper.key import Key
from keymapper.injection.macros import parse
from keymapper import utils
from keymapper.getdevices import get_devices, is_gamepad

from tests.test import new_event, pending_events, fixtures, \
    EVENT_READ_TIMEOUT, uinput_write_history_pipe, \
    MAX_ABS, quick_cleanup, read_write_history_pipe, InputDevice


original_smeab = utils.should_map_event_as_btn


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
        utils.should_map_event_as_btn = original_smeab

        if self.injector is not None:
            self.injector.stop_injecting()
            self.assertEqual(self.injector.get_state(), STOPPED)
            self.injector = None
        evdev.InputDevice.grab = self.grab

        quick_cleanup()

    def test_grab(self):
        # path is from the fixtures
        custom_mapping.change(Key(EV_KEY, 10, 1), 'a')

        self.injector = Injector('device 1', custom_mapping)
        path = '/dev/input/event10'
        # this test needs to pass around all other constraints of
        # _grab_device
        device = self.injector._grab_device(path)
        gamepad = is_gamepad(device)
        self.assertFalse(gamepad)
        self.assertEqual(self.failed, 2)
        # success on the third try
        device.name = fixtures[path]['name']

    def test_fail_grab(self):
        self.make_it_fail = 10
        custom_mapping.change(Key(EV_KEY, 10, 1), 'a')

        self.injector = Injector('device 1', custom_mapping)
        path = '/dev/input/event10'
        device = self.injector._grab_device(path)
        self.assertIsNone(device)
        self.assertGreaterEqual(self.failed, 1)

        self.assertEqual(self.injector.get_state(), UNKNOWN)
        self.injector.start()
        self.assertEqual(self.injector.get_state(), STARTING)
        # since none can be grabbed, the process will terminate. But that
        # actually takes quite some time.
        time.sleep(1.5)
        self.assertFalse(self.injector.is_alive())
        self.assertEqual(self.injector.get_state(), NO_GRAB)

    def test_grab_device_1(self):
        # according to the fixtures, /dev/input/event30 can do ABS_HAT0X
        custom_mapping.change(Key(EV_ABS, ABS_HAT0X, 1), 'a')
        self.injector = Injector('foobar', custom_mapping)

        _grab_device = self.injector._grab_device
        self.assertIsNone(_grab_device('/dev/input/event10'))
        self.assertIsNotNone(_grab_device('/dev/input/event30'))

    def test_grab_device_non_existing(self):
        custom_mapping.change(Key(EV_ABS, ABS_HAT0X, 1), 'a')
        self.injector = Injector('foobar', custom_mapping)

        _grab_device = self.injector._grab_device
        self.assertIsNone(_grab_device('/dev/input/event1234'))

    def test_gamepad_capabilities(self):
        self.injector = Injector('gamepad', custom_mapping)

        path = '/dev/input/event30'
        device = self.injector._grab_device(path)
        gamepad = is_gamepad(device)
        self.assertIsNotNone(device)
        self.assertTrue(gamepad)

        capabilities = self.injector._modify_capabilities(device, gamepad)
        self.assertNotIn(EV_ABS, capabilities)
        self.assertIn(EV_REL, capabilities)

        self.assertIn(evdev.ecodes.REL_X, capabilities.get(EV_REL))
        self.assertIn(evdev.ecodes.REL_Y, capabilities.get(EV_REL))
        self.assertIn(evdev.ecodes.REL_WHEEL, capabilities.get(EV_REL))
        self.assertIn(evdev.ecodes.REL_HWHEEL, capabilities.get(EV_REL))

        self.assertIn(EV_KEY, capabilities)
        self.assertIn(evdev.ecodes.BTN_LEFT, capabilities[EV_KEY])

    def test_gamepad_purpose_none(self):
        # forward abs joystick events
        custom_mapping.set('gamepad.joystick.left_purpose', NONE)
        config.set('gamepad.joystick.right_purpose', NONE)

        self.injector = Injector('gamepad', custom_mapping)

        path = '/dev/input/event30'
        device = self.injector._grab_device(path)
        self.assertIsNone(device)  # no capability is used, so it won't grab

        custom_mapping.change(Key(EV_KEY, BTN_A, 1), 'a')
        device = self.injector._grab_device(path)
        self.assertIsNotNone(device)
        gamepad = is_gamepad(device)
        self.assertTrue(gamepad)
        capabilities = self.injector._modify_capabilities(device, gamepad)
        self.assertIn(EV_ABS, capabilities)

    def test_gamepad_purpose_none_2(self):
        # forward abs joystick events for the left joystick only
        custom_mapping.set('gamepad.joystick.left_purpose', NONE)
        config.set('gamepad.joystick.right_purpose', MOUSE)

        self.injector = Injector('gamepad', custom_mapping)

        path = '/dev/input/event30'
        device = self.injector._grab_device(path)
        # the right joystick maps as mouse, so it is grabbed
        # even with an empty mapping
        self.assertIsNotNone(device)
        gamepad = is_gamepad(device)
        self.assertTrue(gamepad)
        capabilities = self.injector._modify_capabilities(device, gamepad)
        self.assertIn(EV_ABS, capabilities)
        self.assertIn(EV_REL, capabilities)

        custom_mapping.change(Key(EV_KEY, BTN_A, 1), 'a')
        device = self.injector._grab_device(path)
        gamepad = is_gamepad(device)
        self.assertIsNotNone(device)
        self.assertTrue(gamepad)
        capabilities = self.injector._modify_capabilities(device, gamepad)
        self.assertIn(EV_ABS, capabilities)
        self.assertIn(EV_REL, capabilities)
        self.assertIn(EV_KEY, capabilities)

    def test_adds_ev_key(self):
        # for some reason, having any EV_KEY capability is needed to
        # be able to control the mouse. it probably wants the mouse click.
        custom_mapping.change(Key(EV_KEY, BTN_A, 1), 'a')
        self.injector = Injector('gamepad 2', custom_mapping)

        """ABS device without any key capability"""

        path = self.new_gamepad
        gamepad_template = copy.deepcopy(fixtures['/dev/input/event30'])
        fixtures[path] = {
            'name': 'qux 2', 'phys': 'abcd', 'info': '1234',
            'capabilities': gamepad_template['capabilities']
        }
        del fixtures[path]['capabilities'][EV_KEY]
        device = self.injector._grab_device(path)
        # no reason to grab, BTN_A capability is missing in the device
        self.assertIsNone(device)

        """ABS device with a btn_mouse capability"""

        path = self.new_gamepad
        gamepad_template = copy.deepcopy(fixtures['/dev/input/event30'])
        fixtures[path] = {
            'name': 'qux 3', 'phys': 'abcd', 'info': '1234',
            'capabilities': gamepad_template['capabilities']
        }
        fixtures[path]['capabilities'][EV_KEY].append(BTN_LEFT)
        fixtures[path]['capabilities'][EV_KEY].append(KEY_A)
        device = self.injector._grab_device(path)
        gamepad = is_gamepad(device)
        capabilities = self.injector._modify_capabilities(device, gamepad)
        self.assertIn(EV_KEY, capabilities)
        self.assertIn(evdev.ecodes.BTN_MOUSE, capabilities[EV_KEY])
        self.assertIn(evdev.ecodes.KEY_A, capabilities[EV_KEY])

        """a gamepad"""

        path = '/dev/input/event30'
        device = self.injector._grab_device(path)
        gamepad = is_gamepad(device)
        self.assertIn(EV_KEY, device.capabilities())
        self.assertNotIn(evdev.ecodes.BTN_MOUSE, device.capabilities()[EV_KEY])
        capabilities = self.injector._modify_capabilities(device, gamepad)
        self.assertIn(EV_KEY, capabilities)
        self.assertGreater(len(capabilities), 1)
        self.assertIn(evdev.ecodes.BTN_MOUSE, capabilities[EV_KEY])

    def test_skip_unused_device(self):
        # skips a device because its capabilities are not used in the mapping
        custom_mapping.change(Key(EV_KEY, 10, 1), 'a')
        self.injector = Injector('device 1', custom_mapping)
        path = '/dev/input/event11'
        device = self.injector._grab_device(path)
        self.assertIsNone(device)
        self.assertEqual(self.failed, 0)

    def test_skip_unknown_device(self):
        # skips a device because its capabilities are not used in the mapping
        self.injector = Injector('device 1', custom_mapping)
        path = '/dev/input/event11'
        device = self.injector._grab_device(path)

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

    def test_gamepad_to_mouse(self):
        # maps gamepad joystick events to mouse events
        config.set('gamepad.joystick.non_linearity', 1)
        pointer_speed = 80
        config.set('gamepad.joystick.pointer_speed', pointer_speed)

        # they need to sum up before something is written
        divisor = 10
        x = MAX_ABS / pointer_speed / divisor
        y = MAX_ABS / pointer_speed / divisor
        pending_events['gamepad'] = [
            new_event(EV_ABS, ABS_X, x),
            new_event(EV_ABS, ABS_Y, y),
            new_event(EV_ABS, ABS_X, -x),
            new_event(EV_ABS, ABS_Y, -y),
        ]

        self.injector = Injector('gamepad', custom_mapping)
        self.injector.start()

        # wait for the injector to start sending, at most 1s
        uinput_write_history_pipe[0].poll(1)

        # wait a bit more for it to sum up
        sleep = 0.5
        time.sleep(sleep)

        # convert the write history to some easier to manage list
        history = read_write_history_pipe()

        if history[0][0] == EV_ABS:
            raise AssertionError(
                'The injector probably just forwarded them unchanged'
                # possibly in addition to writing mouse events
            )

        # movement is written at 60hz and it takes `divisor` steps to
        # move 1px. take it times 2 for both x and y events.
        self.assertGreater(len(history), 60 * sleep * 0.9 * 2 / divisor)
        self.assertLess(len(history), 60 * sleep * 1.1 * 2 / divisor)

        # those may be in arbitrary order
        count_x = history.count((EV_REL, REL_X, -1))
        count_y = history.count((EV_REL, REL_Y, -1))
        self.assertGreater(count_x, 1)
        self.assertGreater(count_y, 1)
        # only those two types of events were written
        self.assertEqual(len(history), count_x + count_y)

    def test_gamepad_forward_joysticks(self):
        pending_events['gamepad'] = [
            # should forward them unmodified
            new_event(EV_ABS, ABS_X, 10),
            new_event(EV_ABS, ABS_Y, 20),
            new_event(EV_ABS, ABS_X, -30),
            new_event(EV_ABS, ABS_Y, -40),
            new_event(EV_KEY, BTN_A, 1),
            new_event(EV_KEY, BTN_A, 0)
        ] * 2

        custom_mapping.set('gamepad.joystick.left_purpose', NONE)
        custom_mapping.set('gamepad.joystick.right_purpose', NONE)
        # BTN_A -> 77
        custom_mapping.change(Key((1, BTN_A, 1)), 'b')
        system_mapping._set('b', 77)
        self.injector = Injector('gamepad', custom_mapping)
        self.injector.start()

        # wait for the injector to start sending, at most 1s
        uinput_write_history_pipe[0].poll(1)
        time.sleep(0.2)

        # convert the write history to some easier to manage list
        history = read_write_history_pipe()

        self.assertEqual(history.count((EV_ABS, ABS_X, 10)), 2)
        self.assertEqual(history.count((EV_ABS, ABS_Y, 20)), 2)
        self.assertEqual(history.count((EV_ABS, ABS_X, -30)), 2)
        self.assertEqual(history.count((EV_ABS, ABS_Y, -40)), 2)
        self.assertEqual(history.count((EV_KEY, 77, 1)), 2)
        self.assertEqual(history.count((EV_KEY, 77, 0)), 2)

    def test_gamepad_trigger(self):
        # map one of the triggers to BTN_NORTH, while the other one
        # should be forwarded unchanged
        value = MAX_ABS // 2
        pending_events['gamepad'] = [
            new_event(EV_ABS, ABS_Z, value),
            new_event(EV_ABS, ABS_RZ, value),
        ]

        # ABS_Z -> 77
        # ABS_RZ is not mapped
        custom_mapping.change(Key((EV_ABS, ABS_Z, 1)), 'b')
        system_mapping._set('b', 77)
        self.injector = Injector('gamepad', custom_mapping)
        self.injector.start()

        # wait for the injector to start sending, at most 1s
        uinput_write_history_pipe[0].poll(1)
        time.sleep(0.2)

        # convert the write history to some easier to manage list
        history = read_write_history_pipe()

        self.assertEqual(history.count((EV_KEY, 77, 1)), 1)
        self.assertEqual(history.count((EV_ABS, ABS_RZ, value)), 1)

    def test_gamepad_to_mouse_event_producer(self):
        custom_mapping.set('gamepad.joystick.left_purpose', MOUSE)
        custom_mapping.set('gamepad.joystick.right_purpose', NONE)
        self.injector = Injector('gamepad', custom_mapping)
        # the stop message will be available in the pipe right away,
        # so run won't block and just stop. all the stuff
        # will be initialized though, so that stuff can be tested
        self.injector.stop_injecting()
        self.injector.run()
        # not in a process, so the event_producer state can be checked
        self.assertEqual(self.injector._event_producer.max_abs, MAX_ABS)
        self.assertIsNotNone(self.injector._event_producer.mouse_uinput)

    def test_gamepad_to_buttons_event_producer(self):
        custom_mapping.set('gamepad.joystick.left_purpose', BUTTONS)
        custom_mapping.set('gamepad.joystick.right_purpose', BUTTONS)
        self.injector = Injector('gamepad', custom_mapping)
        self.injector.stop_injecting()
        self.injector.run()
        self.assertIsNone(self.injector._event_producer.max_abs, MAX_ABS)
        self.assertIsNone(self.injector._event_producer.mouse_uinput)

    def test_device1_event_producer(self):
        custom_mapping.set('gamepad.joystick.left_purpose', MOUSE)
        custom_mapping.set('gamepad.joystick.right_purpose', WHEEL)
        self.injector = Injector('device 1', custom_mapping)
        self.injector.stop_injecting()
        self.injector.run()
        # not a gamepad, so _event_producer is not initialized for that.
        # it can still debounce stuff though
        self.assertIsNone(self.injector._event_producer.max_abs)
        self.assertIsNone(self.injector._event_producer.mouse_uinput)

    def test_injector(self):
        # the tests in test_keycode_mapper.py test this stuff in detail

        numlock_before = is_numlock_on()

        combination = Key((EV_KEY, 8, 1), (EV_KEY, 9, 1))
        custom_mapping.change(combination, 'k(KEY_Q).k(w)')
        custom_mapping.change(Key(EV_ABS, ABS_HAT0X, -1), 'a')
        # one mapping that is unknown in the system_mapping on purpose
        input_b = 10
        custom_mapping.change(Key(EV_KEY, input_b, 1), 'b')

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
            new_event(EV_KEY, 8, 1),
            new_event(EV_KEY, 9, 1),  # ...now
            new_event(EV_KEY, 8, 0),
            new_event(EV_KEY, 9, 0),
            # gamepad stuff. trigger a combination
            new_event(EV_ABS, ABS_HAT0X, -1),
            new_event(EV_ABS, ABS_HAT0X, 0),
            # just pass those over without modifying
            new_event(EV_KEY, 10, 1),
            new_event(EV_KEY, 10, 0),
            new_event(3124, 3564, 6542),
        ]

        self.injector = Injector('device 2', custom_mapping)
        self.assertEqual(self.injector.get_state(), UNKNOWN)
        self.injector.start()
        self.assertEqual(self.injector.get_state(), STARTING)

        uinput_write_history_pipe[0].poll(timeout=1)
        self.assertEqual(self.injector.get_state(), RUNNING)
        time.sleep(EVENT_READ_TIMEOUT * 10)

        # sending anything arbitrary does not stop the process
        # (is_alive checked later after some time)
        self.injector._msg_pipe[1].send(1234)

        # convert the write history to some easier to manage list
        history = read_write_history_pipe()

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
        self.assertTrue(self.injector.is_alive())

        numlock_after = is_numlock_on()
        self.assertEqual(numlock_before, numlock_after)
        self.assertEqual(self.injector.get_state(), RUNNING)

    def test_any_funky_event_as_button(self):
        # as long as should_map_event_as_btn says it should be a button,
        # it will be.
        EV_TYPE = 4531
        CODE_1 = 754
        CODE_2 = 4139

        w_down = (EV_TYPE, CODE_1, -1)
        w_up = (EV_TYPE, CODE_1, 0)

        d_down = (EV_TYPE, CODE_2, 1)
        d_up = (EV_TYPE, CODE_2, 0)

        custom_mapping.change(Key(*w_down[:2], -1), 'w')
        custom_mapping.change(Key(*d_down[:2], 1), 'k(d)')

        system_mapping.clear()
        code_w = 71
        code_d = 74
        system_mapping._set('w', code_w)
        system_mapping._set('d', code_d)

        def do_stuff():
            if self.injector is not None:
                # discard the previous injector
                self.injector.stop_injecting()
                time.sleep(0.1)
                while uinput_write_history_pipe[0].poll():
                    uinput_write_history_pipe[0].recv()

            pending_events['gamepad'] = [
                new_event(*w_down),
                new_event(*d_down),
                new_event(*w_up),
                new_event(*d_up),
            ]

            self.injector = Injector('gamepad', custom_mapping)

            # the injector will otherwise skip the device because
            # the capabilities don't contain EV_TYPE
            input = InputDevice('/dev/input/event30')
            self.injector._grab_device = lambda *args: input

            self.injector.start()
            uinput_write_history_pipe[0].poll(timeout=1)
            time.sleep(EVENT_READ_TIMEOUT * 10)
            return read_write_history_pipe()

        """no"""

        history = do_stuff()
        self.assertEqual(history.count((EV_KEY, code_w, 1)), 0)
        self.assertEqual(history.count((EV_KEY, code_d, 1)), 0)
        self.assertEqual(history.count((EV_KEY, code_w, 0)), 0)
        self.assertEqual(history.count((EV_KEY, code_d, 0)), 0)

        """yes"""

        utils.should_map_event_as_btn = lambda *args: True
        history = do_stuff()
        self.assertEqual(history.count((EV_KEY, code_w, 1)), 1)
        self.assertEqual(history.count((EV_KEY, code_d, 1)), 1)
        self.assertEqual(history.count((EV_KEY, code_w, 0)), 1)
        self.assertEqual(history.count((EV_KEY, code_d, 0)), 1)

    def test_wheel(self):
        # this tests both keycode_mapper and event_producer, and it seems
        # to test stuff not covered in test_keycode_mapper, so it's a quite
        # important one.

        # wheel release events are made up with a debouncer

        # map those two to stuff
        w_up = (EV_REL, REL_WHEEL, -1)
        hw_right = (EV_REL, REL_HWHEEL, 1)

        # should be forwarded and present in the capabilities
        hw_left = (EV_REL, REL_HWHEEL, -1)

        custom_mapping.change(Key(*hw_right), 'k(b)')
        custom_mapping.change(Key(*w_up), 'c')

        system_mapping.clear()
        code_b = 91
        code_c = 92
        system_mapping._set('b', code_b)
        system_mapping._set('c', code_c)

        device_name = 'device 1'
        pending_events[device_name] = [
            new_event(*w_up),
        ] * 10 + [
            new_event(*hw_right),
            new_event(*w_up),
        ] * 5 + [
            new_event(*hw_left)
        ]

        self.injector = Injector(device_name, custom_mapping)

        device = InputDevice('/dev/input/event11')
        # make sure this test uses a device that has the needed capabilities
        # for the injector to grab it
        self.assertIn(EV_REL, device.capabilities())
        self.assertIn(REL_WHEEL, device.capabilities()[EV_REL])
        self.assertIn(REL_HWHEEL, device.capabilities()[EV_REL])
        self.assertIn(device.path, get_devices()[device_name]['paths'])

        self.injector.start()

        # wait for the first injected key down event
        uinput_write_history_pipe[0].poll(timeout=1)
        self.assertTrue(uinput_write_history_pipe[0].poll())
        event = uinput_write_history_pipe[0].recv()
        self.assertEqual(event.t, (EV_KEY, code_c, 1))

        time.sleep(EVENT_READ_TIMEOUT * 5)
        # in 5 more read-loop ticks, nothing new should have happened
        self.assertFalse(uinput_write_history_pipe[0].poll())

        time.sleep(EVENT_READ_TIMEOUT * 6)
        # 5 more and it should be within the second phase in which
        # the horizontal wheel is used. add some tolerance
        self.assertTrue(uinput_write_history_pipe[0].poll())
        event = uinput_write_history_pipe[0].recv()
        self.assertEqual(event.t, (EV_KEY, code_b, 1))

        time.sleep(EVENT_READ_TIMEOUT * 10 + 5 / 60)
        # after 21 read-loop ticks all events should be consumed, wait for
        # at least 3 (=5) producer-ticks so that the debouncers are triggered.
        # Key-up events for both wheel events should be written now that no
        # new key-down event arrived.
        events = read_write_history_pipe()
        self.assertEqual(events.count((EV_KEY, code_b, 0)), 1)
        self.assertEqual(events.count((EV_KEY, code_c, 0)), 1)
        self.assertEqual(events.count(hw_left), 1)  # the unmapped wheel

        # the unmapped wheel won't get a debounced release command, it's
        # forwarded as is
        self.assertNotIn((EV_REL, REL_HWHEEL, 0), events)

        self.assertEqual(len(events), 3)

    def test_store_permutations_for_macros(self):
        mapping = Mapping()
        ev_1 = (EV_KEY, 41, 1)
        ev_2 = (EV_KEY, 42, 1)
        ev_3 = (EV_KEY, 43, 1)
        # a combination
        mapping.change(Key(ev_1, ev_2, ev_3), 'k(a)')
        self.injector = Injector('device 1', mapping)

        history = []

        class Stop(Exception):
            pass

        def _modify_capabilities(*args):
            history.append(args)
            # avoid going into any mainloop
            raise Stop()

        self.injector._modify_capabilities = _modify_capabilities
        try:
            self.injector.run()
        except Stop:
            pass

        # one call
        self.assertEqual(len(history), 1)
        # first argument of the first call
        macros = self.injector.context.macros
        self.assertEqual(len(macros), 2)
        self.assertEqual(macros[(ev_1, ev_2, ev_3)].code, 'k(a)')
        self.assertEqual(macros[(ev_2, ev_1, ev_3)].code, 'k(a)')

    def test_key_to_code(self):
        mapping = Mapping()
        ev_1 = (EV_KEY, 41, 1)
        ev_2 = (EV_KEY, 42, 1)
        ev_3 = (EV_KEY, 43, 1)
        ev_4 = (EV_KEY, 44, 1)
        mapping.change(Key(ev_1), 'a')
        # a combination
        mapping.change(Key(ev_2, ev_3, ev_4), 'b')
        self.assertEqual(mapping.get_character(Key(ev_2, ev_3, ev_4)), 'b')

        system_mapping.clear()
        system_mapping._set('a', 51)
        system_mapping._set('b', 52)

        injector = Injector('device 1', mapping)
        self.assertEqual(injector.context.key_to_code.get((ev_1,)), 51)
        # permutations to make matching combinations easier
        self.assertEqual(injector.context.key_to_code.get((ev_2, ev_3, ev_4)), 52)
        self.assertEqual(injector.context.key_to_code.get((ev_3, ev_2, ev_4)), 52)
        self.assertEqual(len(injector.context.key_to_code), 3)

    def test_is_in_capabilities(self):
        key = Key(1, 2, 1)
        capabilities = {
            1: [9, 2, 5]
        }
        self.assertTrue(is_in_capabilities(key, capabilities))

        key = Key((1, 2, 1), (1, 3, 1))
        capabilities = {
            1: [9, 2, 5]
        }
        # only one of the codes of the combination is required.
        # The goal is to make combinations across those sub-devices possible,
        # that make up one hardware device
        self.assertTrue(is_in_capabilities(key, capabilities))

        key = Key((1, 2, 1), (1, 5, 1))
        capabilities = {
            1: [9, 2, 5]
        }
        self.assertTrue(is_in_capabilities(key, capabilities))


class TestModifyCapabilities(unittest.TestCase):
    def setUp(self):
        class FakeDevice:
            def __init__(self):
                self._capabilities = {
                    evdev.ecodes.EV_SYN: [1, 2, 3],
                    evdev.ecodes.EV_FF: [1, 2, 3],
                    EV_ABS: [
                        (1, evdev.AbsInfo(
                            value=None, min=None, max=1234, fuzz=None,
                            flat=None, resolution=None
                        )),
                        (2, evdev.AbsInfo(
                            value=None, min=50, max=2345, fuzz=None,
                            flat=None, resolution=None
                        )),
                        3
                    ]
                }

            def capabilities(self, absinfo=False):
                assert absinfo is True
                return self._capabilities

        mapping = Mapping()
        mapping.change(Key(EV_KEY, 80, 1), 'a')
        mapping.change(Key(EV_KEY, 81, 1), DISABLE_NAME)

        macro_code = 'r(2, m(sHiFt_l, r(2, k(1).k(2))))'
        macro = parse(macro_code, mapping)

        mapping.change(Key(EV_KEY, 60, 111), macro_code)

        # going to be ignored, because EV_REL cannot be mapped, that's
        # mouse movements.
        mapping.change(Key(EV_REL, 1234, 3), 'b')

        self.a = system_mapping.get('a')
        self.shift_l = system_mapping.get('ShIfT_L')
        self.one = system_mapping.get(1)
        self.two = system_mapping.get('2')
        self.left = system_mapping.get('BtN_lEfT')
        self.fake_device = FakeDevice()
        self.mapping = mapping
        self.macro = macro

    def check_keys(self, capabilities):
        """No matter the configuration, EV_KEY will be mapped to EV_KEY."""
        self.assertIn(EV_KEY, capabilities)
        keys = capabilities[EV_KEY]
        self.assertIn(self.a, keys)
        self.assertIn(self.one, keys)
        self.assertIn(self.two, keys)
        self.assertIn(self.shift_l, keys)
        self.assertNotIn(DISABLE_CODE, keys)

    def tearDown(self):
        quick_cleanup()

    def test_modify_capabilities(self):
        self.mapping.change(Key(EV_KEY, 60, 1), self.macro.code)
        
        self.injector = Injector('foo', self.mapping)

        capabilities = self.injector._modify_capabilities(
            self.fake_device,
            gamepad=False
        )

        self.assertIn(EV_ABS, capabilities)
        self.check_keys(capabilities)
        keys = capabilities[EV_KEY]
        # mouse capabilities were not present in the fake_device and are
        # still not needed
        self.assertNotIn(self.left, keys)

        self.assertNotIn(evdev.ecodes.EV_SYN, capabilities)
        self.assertNotIn(evdev.ecodes.EV_FF, capabilities)
        self.assertNotIn(EV_REL, capabilities)

        # keeps that stuff since modify_capabilities is told that it is not
        # a gamepad, so it probably serves some special purpose for that
        # device type. For example drawing tablets need that information in
        # order to move the cursor around. Since it keeps ABS, the AbsInfo
        # should also be still intact
        self.assertIn(EV_ABS, capabilities)
        self.assertEqual(capabilities[EV_ABS][0][1].max, 1234)
        self.assertEqual(capabilities[EV_ABS][1][1].max, 2345)
        self.assertEqual(capabilities[EV_ABS][1][1].min, 50)
        self.assertEqual(capabilities[EV_ABS][2], 3)

    def test_no_abs_volume(self):
        self.mapping.change(Key(EV_KEY, 60, 1), self.macro.code)
        
        # I don't know what ABS_VOLUME is, for now I would like to just always
        # remove it until somebody complains
        self.injector = Injector('foo', self.mapping)
        self.fake_device._capabilities = {
            EV_ABS: [ABS_Y, ABS_VOLUME, ABS_X]
        }

        capabilities = self.injector._modify_capabilities(
            self.fake_device,
            gamepad=False
        )
        self.assertNotIn(ABS_VOLUME, capabilities[EV_ABS])

    def test_modify_capabilities_gamepad(self):
        self.mapping.change(Key((EV_KEY, 60, 1)), self.macro.code)

        config.set('gamepad.joystick.left_purpose', MOUSE)
        self.mapping.set('gamepad.joystick.right_purpose', WHEEL)

        self.injector = Injector('foo', self.mapping)
        self.assertFalse(self.injector.context.forwards_joystick())
        self.assertTrue(self.injector.context.maps_joystick())
        self.assertTrue(self.injector.context.joystick_as_mouse())

        capabilities = self.injector._modify_capabilities(
            self.fake_device,
            gamepad=True
        )
        # because ABS is translated to REL, ABS is not a capability anymore
        self.assertNotIn(EV_ABS, capabilities)

        self.check_keys(capabilities)
        keys = capabilities[EV_KEY]

        # now that it is told that it is a gamepad, btn_left is inserted
        # to ensure the operating system interprets it as mouse.
        self.assertIn(self.left, keys)

    def test_modify_capabilities_gamepad_none_none(self):
        self.mapping.change(Key(EV_KEY, 60, 1), self.macro.code)

        config.set('gamepad.joystick.left_purpose', NONE)
        self.mapping.set('gamepad.joystick.right_purpose', NONE)

        self.injector = Injector('foo', self.mapping)
        self.assertTrue(self.injector.context.forwards_joystick())
        self.assertFalse(self.injector.context.maps_joystick())
        self.assertFalse(self.injector.context.joystick_as_mouse())

        capabilities = self.injector._modify_capabilities(
            self.fake_device,
            gamepad=True
        )

        self.check_keys(capabilities)
        self.assertIn(EV_ABS, capabilities)

    def test_modify_capabilities_gamepad_buttons_buttons(self):
        self.mapping.change(Key((EV_KEY, 60, 1)), self.macro.code)

        config.set('gamepad.joystick.left_purpose', BUTTONS)
        self.mapping.set('gamepad.joystick.right_purpose', BUTTONS)

        self.injector = Injector('foo', self.mapping)
        self.assertFalse(self.injector.context.forwards_joystick())
        self.assertTrue(self.injector.context.maps_joystick())
        self.assertFalse(self.injector.context.joystick_as_mouse())

        capabilities = self.injector._modify_capabilities(
            self.fake_device,
            gamepad=True
        )

        self.check_keys(capabilities)
        self.assertNotIn(EV_ABS, capabilities)
        self.assertNotIn(EV_REL, capabilities)

    def test_modify_capabilities_buttons_buttons(self):
        self.mapping.change(Key(EV_KEY, 60, 1), self.macro.code)

        # those settings shouldn't have an effect with gamepad=False
        config.set('gamepad.joystick.left_purpose', BUTTONS)
        self.mapping.set('gamepad.joystick.right_purpose', BUTTONS)

        self.injector = Injector('foo', self.mapping)

        capabilities = self.injector._modify_capabilities(
            self.fake_device,
            gamepad=False
        )

        self.check_keys(capabilities)
        # not a gamepad, keeps EV_ABS because it probably has some special
        # purpose
        self.assertIn(EV_ABS, capabilities)
        self.assertNotIn(EV_REL, capabilities)


if __name__ == "__main__":
    unittest.main()
