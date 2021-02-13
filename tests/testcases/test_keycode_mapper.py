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
import asyncio
import time

from evdev.ecodes import EV_KEY, EV_ABS, KEY_A, BTN_TL, \
    ABS_HAT0X, ABS_HAT0Y, ABS_HAT1X, ABS_HAT1Y, ABS_Y

from keymapper.dev.keycode_mapper import active_macros, KeycodeMapper, \
    unreleased, subsets
from keymapper.state import system_mapping
from keymapper.dev.macros import parse
from keymapper.config import config, BUTTONS
from keymapper.mapping import Mapping, DISABLE_CODE

from tests.test import new_event, UInput, uinput_write_history, \
    quick_cleanup, InputDevice, MAX_ABS


def wait(func, timeout=1.0):
    """Wait for func to return True."""
    iterations = 0
    sleepytime = 0.1
    while not func():
        time.sleep(sleepytime)
        iterations += 1
        if iterations * sleepytime > timeout:
            raise Exception('Timeout')


def calculate_event_number(holdtime, before, after):
    """
    Parameters
    ----------
    holdtime : int
        in ms, how long was the key held down
    before : int
        how many extra k() calls are executed before h()
    after : int
        how many extra k() calls are executed after h()
    """
    keystroke_sleep = config.get('macros.keystroke_sleep_ms', 10)
    # down and up: two sleeps per k
    # one initial k(a):
    events = before * 2
    holdtime -= keystroke_sleep * 2
    # hold events
    events += (holdtime / (keystroke_sleep * 2)) * 2
    # one trailing k(c)
    events += after * 2
    return events


class TestKeycodeMapper(unittest.TestCase):
    def setUp(self):
        self.mapping = Mapping()
        self.source = InputDevice('/dev/input/event11')

    def tearDown(self):
        # make sure all macros are stopped by tests
        for macro in active_macros.values():
            if macro.is_holding():
                macro.release_key()
            self.assertFalse(macro.is_holding())
            self.assertFalse(macro.running)

        quick_cleanup()

    def test_subsets(self):
        a = subsets(((1,), (2,), (3,)))
        self.assertIn(((1,), (2,)), a)
        self.assertIn(((2,), (3,)), a)
        self.assertIn(((1,), (3,)), a)
        self.assertIn(((1,), (2,), (3,)), a)
        self.assertEqual(len(a), 4)

        b = subsets(((1,), (2,)))
        self.assertIn(((1,), (2,)), b)
        self.assertEqual(len(b), 1)

        c = subsets(((1,),))
        self.assertEqual(len(c), 0)

    def test_d_pad(self):
        ev_1 = (EV_ABS, ABS_HAT0X, 1)
        ev_2 = (EV_ABS, ABS_HAT0X, -1)
        ev_3 = (EV_ABS, ABS_HAT0X, 0)

        ev_4 = (EV_ABS, ABS_HAT0Y, 1)
        ev_5 = (EV_ABS, ABS_HAT0Y, -1)
        ev_6 = (EV_ABS, ABS_HAT0Y, 0)

        _key_to_code = {
            (ev_1,): 51,
            (ev_2,): 52,
            (ev_4,): 54,
            (ev_5,): 55,
        }

        uinput = UInput()

        keycode_mapper = KeycodeMapper(
            self.source, self.mapping, uinput,
            _key_to_code, {}
        )

        # a bunch of d-pad key down events at once
        keycode_mapper.handle_keycode(new_event(*ev_1))
        keycode_mapper.handle_keycode(new_event(*ev_4))
        self.assertEqual(len(unreleased), 2)

        self.assertEqual(unreleased.get(ev_1[:2]).target_type_code, (EV_KEY, _key_to_code[(ev_1,)]))
        self.assertEqual(unreleased.get(ev_1[:2]).input_event_tuple, ev_1)
        self.assertEqual(unreleased.get(ev_1[:2]).key, (ev_1,))  # as seen in _key_to_code

        self.assertEqual(unreleased.get(ev_4[:2]).target_type_code, (EV_KEY, _key_to_code[(ev_4,)]), ev_4)
        self.assertEqual(unreleased.get(ev_4[:2]).input_event_tuple, ev_4)
        self.assertEqual(unreleased.get(ev_4[:2]).key, (ev_4,))

        # release all of them
        keycode_mapper.handle_keycode(new_event(*ev_3))
        keycode_mapper.handle_keycode(new_event(*ev_6))
        self.assertEqual(len(unreleased), 0)

        # repeat with other values
        keycode_mapper.handle_keycode(new_event(*ev_2))
        keycode_mapper.handle_keycode(new_event(*ev_5))
        self.assertEqual(len(unreleased), 2)
        self.assertEqual(unreleased.get(ev_2[:2]).target_type_code, (EV_KEY, _key_to_code[(ev_2,)]))
        self.assertEqual(unreleased.get(ev_2[:2]).input_event_tuple, ev_2)
        self.assertEqual(unreleased.get(ev_5[:2]).target_type_code, (EV_KEY, _key_to_code[(ev_5,)]))
        self.assertEqual(unreleased.get(ev_5[:2]).input_event_tuple, ev_5)

        # release all of them again
        keycode_mapper.handle_keycode(new_event(*ev_3))
        keycode_mapper.handle_keycode(new_event(*ev_6))
        self.assertEqual(len(unreleased), 0)

        self.assertEqual(len(uinput_write_history), 8)

        self.assertEqual(uinput_write_history[0].t, (EV_KEY, 51, 1))
        self.assertEqual(uinput_write_history[1].t, (EV_KEY, 54, 1))

        self.assertEqual(uinput_write_history[2].t, (EV_KEY, 51, 0))
        self.assertEqual(uinput_write_history[3].t, (EV_KEY, 54, 0))

        self.assertEqual(uinput_write_history[4].t, (EV_KEY, 52, 1))
        self.assertEqual(uinput_write_history[5].t, (EV_KEY, 55, 1))

        self.assertEqual(uinput_write_history[6].t, (EV_KEY, 52, 0))
        self.assertEqual(uinput_write_history[7].t, (EV_KEY, 55, 0))

    def test_not_forward(self):
        down = (EV_KEY, 91, 1)
        up = (EV_KEY, 91, 0)
        uinput = UInput()

        keycode_mapper = KeycodeMapper(
            self.source, self.mapping, uinput,
            {}, {}
        )

        keycode_mapper.handle_keycode(new_event(*down), False)
        self.assertEqual(unreleased[(EV_KEY, 91)].input_event_tuple, down)
        self.assertEqual(unreleased[(EV_KEY, 91)].target_type_code, down[:2])
        self.assertEqual(len(unreleased), 1)
        self.assertEqual(uinput.write_count, 0)

        keycode_mapper.handle_keycode(new_event(*up), False)
        self.assertEqual(len(unreleased), 0)
        self.assertEqual(uinput.write_count, 0)

    def test_release_joystick_button(self):
        # with the left joystick mapped as button, it will release the mapped
        # key when it goes back to close to its resting position
        ev_1 = (3, 0, MAX_ABS // 10)  # release
        ev_3 = (3, 0, -MAX_ABS)  # press

        uinput = UInput()

        _key_to_code = {
            ((3, 0, -1),): 73
        }

        self.mapping.set('gamepad.joystick.left_purpose', BUTTONS)

        # something with gamepad capabilities
        source = InputDevice('/dev/input/event30')

        keycode_mapper = KeycodeMapper(
            source, self.mapping, uinput,
            _key_to_code, {}
        )

        keycode_mapper.handle_keycode(new_event(*ev_3))
        keycode_mapper.handle_keycode(new_event(*ev_1))

        # array of 3-tuples
        history = [a.t for a in uinput_write_history]

        self.assertIn((EV_KEY, 73, 1), history)
        self.assertEqual(history.count((EV_KEY, 73, 1)), 1)

        self.assertIn((EV_KEY, 73, 0), history)
        self.assertEqual(history.count((EV_KEY, 73, 0)), 1)

    def test_dont_filter_unmapped(self):
        # if an event is not used at all, it should be written into
        # unmapped but not furthermore modified. For example wheel events
        # keep reporting events of the same value without a release inbetween,
        # they should be forwarded.

        down = (EV_KEY, 91, 1)
        up = (EV_KEY, 91, 0)
        uinput = UInput()

        keycode_mapper = KeycodeMapper(
            self.source, self.mapping, uinput,
            {}, {}
        )

        for _ in range(10):
            keycode_mapper.handle_keycode(new_event(*down))

        self.assertEqual(unreleased[(EV_KEY, 91)].input_event_tuple, down)
        self.assertEqual(unreleased[(EV_KEY, 91)].target_type_code, down[:2])
        self.assertEqual(len(unreleased), 1)
        self.assertEqual(uinput.write_count, 10)

        keycode_mapper.handle_keycode(new_event(*up))
        self.assertEqual(len(unreleased), 0)
        self.assertEqual(uinput.write_count, 11)

    def test_filter_combi_mapped_duplicate_down(self):
        # the opposite of the other test, but don't map the key directly
        # but rather as the trigger for a combination
        down_1 = (EV_KEY, 91, 1)
        down_2 = (EV_KEY, 92, 1)
        up_1 = (EV_KEY, 91, 0)
        up_2 = (EV_KEY, 92, 0)
        uinput = UInput()

        output = 71

        key_to_code = {
            (down_1, down_2): 71
        }

        keycode_mapper = KeycodeMapper(
            self.source, self.mapping, uinput,
            key_to_code, {}
        )

        keycode_mapper.handle_keycode(new_event(*down_1))
        for _ in range(10):
            keycode_mapper.handle_keycode(new_event(*down_2))

        # all duplicate down events should have been ignored
        self.assertEqual(len(unreleased), 2)
        self.assertEqual(uinput.write_count, 2)
        self.assertEqual(uinput_write_history[0].t, down_1)
        self.assertEqual(uinput_write_history[1].t, (EV_KEY, output, 1))

        keycode_mapper.handle_keycode(new_event(*up_1))
        keycode_mapper.handle_keycode(new_event(*up_2))
        self.assertEqual(len(unreleased), 0)
        self.assertEqual(uinput.write_count, 4)
        self.assertEqual(uinput_write_history[2].t, up_1)
        self.assertEqual(uinput_write_history[3].t, (EV_KEY, output, 0))

    def test_d_pad_combination(self):
        ev_1 = (EV_ABS, ABS_HAT0X, 1)
        ev_2 = (EV_ABS, ABS_HAT0Y, -1)

        ev_3 = (EV_ABS, ABS_HAT0X, 0)
        ev_4 = (EV_ABS, ABS_HAT0Y, 0)

        _key_to_code = {
            (ev_1, ev_2): 51,
            (ev_2,): 52,
        }

        uinput = UInput()

        keycode_mapper = KeycodeMapper(
            self.source, self.mapping, uinput,
            _key_to_code, {}
        )

        # a bunch of d-pad key down events at once
        keycode_mapper.handle_keycode(new_event(*ev_1))
        keycode_mapper.handle_keycode(new_event(*ev_2))
        # (what_will_be_released, what_caused_the_key_down)
        self.assertEqual(unreleased.get(ev_1[:2]).target_type_code, (EV_ABS, ABS_HAT0X))
        self.assertEqual(unreleased.get(ev_1[:2]).input_event_tuple, ev_1)
        self.assertEqual(unreleased.get(ev_2[:2]).target_type_code, (EV_KEY, 51))
        self.assertEqual(unreleased.get(ev_2[:2]).input_event_tuple, ev_2)
        self.assertEqual(len(unreleased), 2)

        # ev_1 is unmapped and the other is the triggered combination
        self.assertEqual(len(uinput_write_history), 2)
        self.assertEqual(uinput_write_history[0].t, ev_1)
        self.assertEqual(uinput_write_history[1].t, (EV_KEY, 51, 1))

        # release all of them
        keycode_mapper.handle_keycode(new_event(*ev_3))
        keycode_mapper.handle_keycode(new_event(*ev_4))
        self.assertEqual(len(unreleased), 0)

        self.assertEqual(len(uinput_write_history), 4)
        self.assertEqual(uinput_write_history[2].t, ev_3)
        self.assertEqual(uinput_write_history[3].t, (EV_KEY, 51, 0))

    def test_handle_keycode(self):
        _key_to_code = {
            ((EV_KEY, 1, 1),): 101,
            ((EV_KEY, 2, 1),): 102
        }

        uinput = UInput()

        keycode_mapper = KeycodeMapper(
            self.source, self.mapping, uinput,
            _key_to_code, {}
        )

        keycode_mapper.handle_keycode(new_event(EV_KEY, 1, 1))
        keycode_mapper.handle_keycode(new_event(EV_KEY, 3, 1))
        keycode_mapper.handle_keycode(new_event(EV_KEY, 2, 1))

        self.assertEqual(len(uinput_write_history), 3)
        self.assertEqual(uinput_write_history[0].t, (EV_KEY, 101, 1))
        self.assertEqual(uinput_write_history[1].t, (EV_KEY, 3, 1))
        self.assertEqual(uinput_write_history[2].t, (EV_KEY, 102, 1))

    def test_combination_keycode(self):
        combination = ((EV_KEY, 1, 1), (EV_KEY, 2, 1))
        _key_to_code = {
            combination: 101
        }

        uinput = UInput()

        keycode_mapper = KeycodeMapper(
            self.source, self.mapping, uinput,
            _key_to_code, {}
        )

        keycode_mapper.handle_keycode(new_event(*combination[0]))
        keycode_mapper.handle_keycode(new_event(*combination[1]))

        self.assertEqual(len(uinput_write_history), 2)
        # the first event is written and then the triggered combination
        self.assertEqual(uinput_write_history[0].t, (EV_KEY, 1, 1))
        self.assertEqual(uinput_write_history[1].t, (EV_KEY, 101, 1))

        # release them
        keycode_mapper.handle_keycode(new_event(*combination[0][:2], 0))
        keycode_mapper.handle_keycode(new_event(*combination[1][:2], 0))
        # the first key writes its release event. The second key is hidden
        # behind the executed combination. The result of the combination is
        # also released, because it acts like a key.
        self.assertEqual(len(uinput_write_history), 4)
        self.assertEqual(uinput_write_history[2].t, (EV_KEY, 1, 0))
        self.assertEqual(uinput_write_history[3].t, (EV_KEY, 101, 0))

        # press them in the wrong order (the wrong key at the end, the order
        # of all other keys won't matter). no combination should be triggered
        keycode_mapper.handle_keycode(new_event(*combination[1]))
        keycode_mapper.handle_keycode(new_event(*combination[0]))
        self.assertEqual(len(uinput_write_history), 6)
        self.assertEqual(uinput_write_history[4].t, (EV_KEY, 2, 1))
        self.assertEqual(uinput_write_history[5].t, (EV_KEY, 1, 1))

    def test_combination_keycode_2(self):
        combination_1 = (
            (EV_KEY, 1, 1),
            (EV_ABS, ABS_Y, -MAX_ABS),
            (EV_KEY, 3, 1),
            (EV_KEY, 4, 1)
        )
        combination_2 = (
            # should not be triggered, combination_1 should be prioritized
            # when all of its keys are down
            (EV_KEY, 2, 1),
            (EV_KEY, 3, 1),
            (EV_KEY, 4, 1)
        )

        down_5 = (EV_KEY, 5, 1)
        up_5 = (EV_KEY, 5, 0)
        up_4 = (EV_KEY, 4, 0)

        def sign_value(key):
            return key[0], key[1], key[2] / abs(key[2])

        _key_to_code = {
            # key_to_code is supposed to only contain normalized values
            tuple([sign_value(a) for a in combination_1]): 101,
            combination_2: 102,
            (down_5,): 103
        }

        uinput = UInput()

        source = InputDevice('/dev/input/event30')

        keycode_mapper = KeycodeMapper(
            source, self.mapping, uinput,
            _key_to_code, {}
        )

        # 10 and 11: insert some more arbitrary key-down events,
        # they should not break the combinations
        keycode_mapper.handle_keycode(new_event(EV_KEY, 10, 1))
        keycode_mapper.handle_keycode(new_event(*combination_1[0]))
        keycode_mapper.handle_keycode(new_event(*combination_1[1]))
        keycode_mapper.handle_keycode(new_event(*combination_1[2]))
        keycode_mapper.handle_keycode(new_event(EV_KEY, 11, 1))
        keycode_mapper.handle_keycode(new_event(*combination_1[3]))

        self.assertEqual(len(uinput_write_history), 6)
        # the first events are written and then the triggered combination,
        # while the triggering event is the only one that is omitted
        self.assertEqual(uinput_write_history[1].t, combination_1[0])
        self.assertEqual(uinput_write_history[2].t, combination_1[1])
        self.assertEqual(uinput_write_history[3].t, combination_1[2])
        self.assertEqual(uinput_write_history[5].t, (EV_KEY, 101, 1))

        # while the combination is down, another unrelated key can be used
        keycode_mapper.handle_keycode(new_event(*down_5))
        # the keycode_mapper searches for subsets of the current held-down
        # keys to activate combinations, down_5 should not trigger them
        # again.
        self.assertEqual(len(uinput_write_history), 7)
        self.assertEqual(uinput_write_history[6].t, (EV_KEY, 103, 1))

        # release the combination by releasing the last key, and release
        # the unrelated key
        keycode_mapper.handle_keycode(new_event(*up_4))
        keycode_mapper.handle_keycode(new_event(*up_5))
        self.assertEqual(len(uinput_write_history), 9)

        self.assertEqual(uinput_write_history[7].t, (EV_KEY, 101, 0))
        self.assertEqual(uinput_write_history[8].t, (EV_KEY, 103, 0))

    def test_handle_keycode_macro(self):
        history = []

        code_a = 100
        code_b = 101
        system_mapping.clear()
        system_mapping._set('a', code_a)
        system_mapping._set('b', code_b)

        macro_mapping = {
            ((EV_KEY, 1, 1),): parse('k(a)', self.mapping),
            ((EV_KEY, 2, 1),): parse('r(5, k(b))', self.mapping)
        }

        keycode_mapper = KeycodeMapper(
            self.source, self.mapping, None,
            {}, macro_mapping
        )

        keycode_mapper.macro_write = lambda *args: history.append(args)
        keycode_mapper.macro_write = lambda *args: history.append(args)

        keycode_mapper.handle_keycode(new_event(EV_KEY, 1, 1))
        keycode_mapper.handle_keycode(new_event(EV_KEY, 2, 1))

        loop = asyncio.get_event_loop()

        sleeptime = config.get('macros.keystroke_sleep_ms', 10) * 12

        # let the mainloop run for some time so that the macro does its stuff
        loop.run_until_complete(asyncio.sleep(sleeptime / 1000 + 0.1))

        # 6 keycodes written, with down and up events
        self.assertEqual(len(history), 12)
        self.assertIn((code_a, 1), history)
        self.assertIn((code_a, 0), history)
        self.assertIn((code_b, 1), history)
        self.assertIn((code_b, 0), history)

        # releasing stuff
        self.assertIn((EV_KEY, 1), unreleased)
        self.assertIn((EV_KEY, 2), unreleased)
        keycode_mapper.handle_keycode(new_event(EV_KEY, 1, 0))
        keycode_mapper.handle_keycode(new_event(EV_KEY, 2, 0))
        self.assertNotIn((EV_KEY, 1), unreleased)
        self.assertNotIn((EV_KEY, 2), unreleased)
        loop.run_until_complete(asyncio.sleep(0.1))
        self.assertEqual(len(history), 12)

    def test_hold(self):
        history = []

        code_a = 100
        code_b = 101
        code_c = 102
        system_mapping.clear()
        system_mapping._set('a', code_a)
        system_mapping._set('b', code_b)
        system_mapping._set('c', code_c)

        macro_mapping = {
            ((EV_KEY, 1, 1),): parse('k(a).h(k(b)).k(c)', self.mapping)
        }

        def handler(*args):
            history.append(args)

        keycode_mapper = KeycodeMapper(
            self.source, self.mapping, None,
            {}, macro_mapping
        )

        keycode_mapper.macro_write = handler

        """start macro"""

        keycode_mapper.handle_keycode(new_event(EV_KEY, 1, 1))

        loop = asyncio.get_event_loop()

        # let the mainloop run for some time so that the macro does its stuff
        sleeptime = 500
        keystroke_sleep = config.get('macros.keystroke_sleep_ms', 10)
        loop.run_until_complete(asyncio.sleep(sleeptime / 1000))

        self.assertTrue(active_macros[(EV_KEY, 1)].is_holding())
        self.assertTrue(active_macros[(EV_KEY, 1)].running)

        """stop macro"""

        keycode_mapper.handle_keycode(new_event(EV_KEY, 1, 0))

        loop.run_until_complete(asyncio.sleep(keystroke_sleep * 10 / 1000))

        events = calculate_event_number(sleeptime, 1, 1)

        self.assertGreater(len(history), events * 0.9)
        self.assertLess(len(history), events * 1.1)

        self.assertIn((code_a, 1), history)
        self.assertIn((code_a, 0), history)
        self.assertIn((code_b, 1), history)
        self.assertIn((code_b, 0), history)
        self.assertIn((code_c, 1), history)
        self.assertIn((code_c, 0), history)
        self.assertGreater(history.count((code_b, 1)), 1)
        self.assertGreater(history.count((code_b, 0)), 1)

        # it's stopped and won't write stuff anymore
        count_before = len(history)
        loop.run_until_complete(asyncio.sleep(0.2))
        count_after = len(history)
        self.assertEqual(count_before, count_after)

        self.assertFalse(active_macros[(EV_KEY, 1)].is_holding())
        self.assertFalse(active_macros[(EV_KEY, 1)].running)

    def test_hold_2(self):
        # test irregular input patterns
        code_a = 100
        code_b = 101
        code_c = 102
        code_d = 103
        system_mapping.clear()
        system_mapping._set('a', code_a)
        system_mapping._set('b', code_b)
        system_mapping._set('c', code_c)
        system_mapping._set('d', code_d)

        macro_mapping = {
            ((EV_KEY, 1, 1),): parse('h(k(b))', self.mapping),
            ((EV_KEY, 2, 1),): parse('k(c).r(1, r(1, r(1, h(k(a))))).k(d)', self.mapping),
            ((EV_KEY, 3, 1),): parse('h(k(b))', self.mapping)
        }

        history = []

        def handler(*args):
            history.append(args)

        keycode_mapper = KeycodeMapper(
            self.source, self.mapping, None,
            {}, macro_mapping
        )

        keycode_mapper.macro_write = handler
        keycode_mapper.macro_write = handler
        keycode_mapper.macro_write = handler

        """start macro 2"""

        keycode_mapper.handle_keycode(new_event(EV_KEY, 2, 1))
        loop = asyncio.get_event_loop()

        loop.run_until_complete(asyncio.sleep(0.1))
        # starting code_c written
        self.assertEqual(history.count((code_c, 1)), 1)
        self.assertEqual(history.count((code_c, 0)), 1)

        # spam garbage events
        for _ in range(5):
            keycode_mapper.handle_keycode(new_event(EV_KEY, 1, 1))
            keycode_mapper.handle_keycode(new_event(EV_KEY, 3, 1))
            loop.run_until_complete(asyncio.sleep(0.05))
            self.assertTrue(active_macros[(EV_KEY, 1)].is_holding())
            self.assertTrue(active_macros[(EV_KEY, 1)].running)
            self.assertTrue(active_macros[(EV_KEY, 2)].is_holding())
            self.assertTrue(active_macros[(EV_KEY, 2)].running)
            self.assertTrue(active_macros[(EV_KEY, 3)].is_holding())
            self.assertTrue(active_macros[(EV_KEY, 3)].running)

        # there should only be one code_c in the events, because no key
        # up event was ever done so the hold just continued
        self.assertEqual(history.count((code_c, 1)), 1)
        self.assertEqual(history.count((code_c, 0)), 1)
        # without an key up event on 2, it won't write code_d
        self.assertNotIn((code_d, 1), history)
        self.assertNotIn((code_d, 0), history)

        # stop macro 2
        keycode_mapper.handle_keycode(new_event(EV_KEY, 2, 0))
        loop.run_until_complete(asyncio.sleep(0.1))

        # it stopped and didn't restart, so the count stays at 1
        self.assertEqual(history.count((code_c, 1)), 1)
        self.assertEqual(history.count((code_c, 0)), 1)
        # and the trailing d was written
        self.assertEqual(history.count((code_d, 1)), 1)
        self.assertEqual(history.count((code_d, 0)), 1)

        # it's stopped and won't write stuff anymore
        count_before = history.count((code_a, 1))
        self.assertGreater(count_before, 1)
        loop.run_until_complete(asyncio.sleep(0.1))
        count_after = history.count((code_a, 1))
        self.assertEqual(count_before, count_after)

        """restart macro 2"""

        history = []

        keycode_mapper.handle_keycode(new_event(EV_KEY, 2, 1))
        loop.run_until_complete(asyncio.sleep(0.1))
        self.assertEqual(history.count((code_c, 1)), 1)
        self.assertEqual(history.count((code_c, 0)), 1)

        # spam garbage events again, this time key-up events on all other
        # macros
        for _ in range(5):
            keycode_mapper.handle_keycode(new_event(EV_KEY, 1, 0))
            keycode_mapper.handle_keycode(new_event(EV_KEY, 3, 0))
            loop.run_until_complete(asyncio.sleep(0.05))
            self.assertFalse(active_macros[(EV_KEY, 1)].is_holding())
            self.assertFalse(active_macros[(EV_KEY, 1)].running)
            self.assertTrue(active_macros[(EV_KEY, 2)].is_holding())
            self.assertTrue(active_macros[(EV_KEY, 2)].running)
            self.assertFalse(active_macros[(EV_KEY, 3)].is_holding())
            self.assertFalse(active_macros[(EV_KEY, 3)].running)

        # stop macro 2
        keycode_mapper.handle_keycode(new_event(EV_KEY, 2, 0))
        loop.run_until_complete(asyncio.sleep(0.1))
        # was started only once
        self.assertEqual(history.count((code_c, 1)), 1)
        self.assertEqual(history.count((code_c, 0)), 1)
        # and the trailing d was also written only once
        self.assertEqual(history.count((code_d, 1)), 1)
        self.assertEqual(history.count((code_d, 0)), 1)

        # stop all macros
        keycode_mapper.handle_keycode(new_event(EV_KEY, 1, 0))
        keycode_mapper.handle_keycode(new_event(EV_KEY, 3, 0))
        loop.run_until_complete(asyncio.sleep(0.1))

        # it's stopped and won't write stuff anymore
        count_before = len(history)
        loop.run_until_complete(asyncio.sleep(0.1))
        count_after = len(history)
        self.assertEqual(count_before, count_after)

        self.assertFalse(active_macros[(EV_KEY, 1)].is_holding())
        self.assertFalse(active_macros[(EV_KEY, 1)].running)
        self.assertFalse(active_macros[(EV_KEY, 2)].is_holding())
        self.assertFalse(active_macros[(EV_KEY, 2)].running)
        self.assertFalse(active_macros[(EV_KEY, 3)].is_holding())
        self.assertFalse(active_macros[(EV_KEY, 3)].running)

    def test_hold_3(self):
        # test irregular input patterns
        code_a = 100
        code_b = 101
        code_c = 102
        system_mapping.clear()
        system_mapping._set('a', code_a)
        system_mapping._set('b', code_b)
        system_mapping._set('c', code_c)

        macro_mapping = {
            ((EV_KEY, 1, 1),): parse('k(a).h(k(b)).k(c)', self.mapping),
        }

        history = []

        def handler(*args):
            history.append(args)

        keycode_mapper = KeycodeMapper(
            self.source, self.mapping, None,
            {}, macro_mapping
        )

        keycode_mapper.macro_write = handler

        keycode_mapper.handle_keycode(new_event(EV_KEY, 1, 1))
        loop = asyncio.get_event_loop()

        loop.run_until_complete(asyncio.sleep(0.1))
        for _ in range(5):
            self.assertTrue(active_macros[(EV_KEY, 1)].is_holding())
            self.assertTrue(active_macros[(EV_KEY, 1)].running)
            keycode_mapper.handle_keycode(new_event(EV_KEY, 1, 1))
            loop.run_until_complete(asyncio.sleep(0.05))

        # duplicate key down events don't do anything
        self.assertEqual(history.count((code_a, 1)), 1)
        self.assertEqual(history.count((code_a, 0)), 1)
        self.assertEqual(history.count((code_c, 1)), 0)
        self.assertEqual(history.count((code_c, 0)), 0)

        # stop
        keycode_mapper.handle_keycode(new_event(EV_KEY, 1, 0))
        loop.run_until_complete(asyncio.sleep(0.1))
        self.assertEqual(history.count((code_a, 1)), 1)
        self.assertEqual(history.count((code_a, 0)), 1)
        self.assertEqual(history.count((code_c, 1)), 1)
        self.assertEqual(history.count((code_c, 0)), 1)
        self.assertFalse(active_macros[(EV_KEY, 1)].is_holding())
        self.assertFalse(active_macros[(EV_KEY, 1)].running)

        # it's stopped and won't write stuff anymore
        count_before = len(history)
        loop.run_until_complete(asyncio.sleep(0.1))
        count_after = len(history)
        self.assertEqual(count_before, count_after)

    def test_hold_two(self):
        # holding two macros at the same time,
        # the first one is triggered by a combination
        history = []

        code_1 = 100
        code_2 = 101
        code_3 = 102
        code_a = 103
        code_b = 104
        code_c = 105
        system_mapping.clear()
        system_mapping._set('1', code_1)
        system_mapping._set('2', code_2)
        system_mapping._set('3', code_3)
        system_mapping._set('a', code_a)
        system_mapping._set('b', code_b)
        system_mapping._set('c', code_c)

        key_0 = (EV_KEY, 10)
        key_1 = (EV_KEY, 11)
        key_2 = (EV_ABS, ABS_HAT0X)
        down_0 = (*key_0, 1)
        down_1 = (*key_1, 1)
        down_2 = (*key_2, -1)
        up_0 = (*key_0, 0)
        up_1 = (*key_1, 0)
        up_2 = (*key_2, 0)

        macro_mapping = {
            (down_0, down_1): parse('k(1).h(k(2)).k(3)', self.mapping),
            (down_2,): parse('k(a).h(k(b)).k(c)', self.mapping)
        }

        def handler(*args):
            history.append(args)

        loop = asyncio.get_event_loop()

        uinput_1 = UInput()

        keycode_mapper = KeycodeMapper(
            self.source, self.mapping, uinput_1,
            {}, macro_mapping
        )

        keycode_mapper.macro_write = handler

        # key up won't do anything
        keycode_mapper.handle_keycode(new_event(*up_0))
        keycode_mapper.handle_keycode(new_event(*up_1))
        keycode_mapper.handle_keycode(new_event(*up_2))
        loop.run_until_complete(asyncio.sleep(0.1))
        self.assertEqual(len(active_macros), 0)

        """start macros"""

        uinput_2 = UInput()

        keycode_mapper = KeycodeMapper(
            self.source, self.mapping, uinput_2,
            {}, macro_mapping
        )

        keycode_mapper.macro_write = handler

        keycode_mapper.handle_keycode(new_event(*down_0))
        self.assertEqual(uinput_2.write_count, 1)
        keycode_mapper.handle_keycode(new_event(*down_1))
        keycode_mapper.handle_keycode(new_event(*down_2))
        self.assertEqual(uinput_2.write_count, 1)

        # let the mainloop run for some time so that the macro does its stuff
        sleeptime = 500
        keystroke_sleep = config.get('macros.keystroke_sleep_ms', 10)
        loop.run_until_complete(asyncio.sleep(sleeptime / 1000))

        self.assertEqual(len(active_macros), 2)
        self.assertTrue(active_macros[key_1].is_holding())
        self.assertTrue(active_macros[key_1].running)
        self.assertTrue(active_macros[key_2].is_holding())
        self.assertTrue(active_macros[key_2].running)

        self.assertIn(down_0[:2], unreleased)
        self.assertIn(down_1[:2], unreleased)
        self.assertIn(down_2[:2], unreleased)

        """stop macros"""

        keycode_mapper = KeycodeMapper(
            self.source, self.mapping, None,
            {}, macro_mapping
        )

        # releasing the last key of a combination releases the whole macro
        keycode_mapper.handle_keycode(new_event(*up_1))
        keycode_mapper.handle_keycode(new_event(*up_2))

        self.assertIn(down_0[:2], unreleased)
        self.assertNotIn(down_1[:2], unreleased)
        self.assertNotIn(down_2[:2], unreleased)

        loop.run_until_complete(asyncio.sleep(keystroke_sleep * 10 / 1000))

        self.assertFalse(active_macros[key_1].is_holding())
        self.assertFalse(active_macros[key_1].running)
        self.assertFalse(active_macros[key_2].is_holding())
        self.assertFalse(active_macros[key_2].running)

        events = calculate_event_number(sleeptime, 1, 1) * 2

        self.assertGreater(len(history), events * 0.9)
        self.assertLess(len(history), events * 1.1)

        self.assertIn((code_a, 1), history)
        self.assertIn((code_a, 0), history)
        self.assertIn((code_b, 1), history)
        self.assertIn((code_b, 0), history)
        self.assertIn((code_c, 1), history)
        self.assertIn((code_c, 0), history)
        self.assertIn((code_1, 1), history)
        self.assertIn((code_1, 0), history)
        self.assertIn((code_2, 1), history)
        self.assertIn((code_2, 0), history)
        self.assertIn((code_3, 1), history)
        self.assertIn((code_3, 0), history)
        self.assertGreater(history.count((code_b, 1)), 1)
        self.assertGreater(history.count((code_b, 0)), 1)
        self.assertGreater(history.count((code_2, 1)), 1)
        self.assertGreater(history.count((code_2, 0)), 1)

        # it's stopped and won't write stuff anymore
        count_before = len(history)
        loop.run_until_complete(asyncio.sleep(0.2))
        count_after = len(history)
        self.assertEqual(count_before, count_after)

    def test_two_d_pad_macros(self):
        # executing two macros that stop automatically at the same time

        code_1 = 61
        code_2 = 62
        system_mapping.clear()
        system_mapping._set('1', code_1)
        system_mapping._set('2', code_2)

        # try two concurrent macros with D-Pad events because they are
        # more difficult to manage, since their only difference is their
        # value, and one of them is negative.
        right = (EV_ABS, ABS_HAT0X, 1)
        release = (EV_ABS, ABS_HAT0X, 0)
        left = (EV_ABS, ABS_HAT0X, -1)

        repeats = 10

        macro_mapping = {
            (right,): parse(f'r({repeats}, k(1))', self.mapping),
            (left,): parse(f'r({repeats}, k(2))', self.mapping)
        }

        history = []

        def handler(*args):
            history.append(args)

        keycode_mapper = KeycodeMapper(
            self.source, self.mapping, None,
            {}, macro_mapping
        )

        keycode_mapper.macro_write = handler
        keycode_mapper.macro_write = handler

        keycode_mapper.handle_keycode(new_event(*right))
        self.assertIn((EV_ABS, ABS_HAT0X), unreleased)
        keycode_mapper.handle_keycode(new_event(*release))
        self.assertNotIn((EV_ABS, ABS_HAT0X), unreleased)
        keycode_mapper.handle_keycode(new_event(*left))
        self.assertIn((EV_ABS, ABS_HAT0X), unreleased)

        loop = asyncio.get_event_loop()
        sleeptime = config.get('macros.keystroke_sleep_ms') / 1000
        loop.run_until_complete(asyncio.sleep(1.1 * repeats * 2 * sleeptime))

        self.assertEqual(history.count((code_1, 1)), 10)
        self.assertEqual(history.count((code_1, 0)), 10)
        self.assertEqual(history.count((code_2, 1)), 10)
        self.assertEqual(history.count((code_2, 0)), 10)
        self.assertEqual(len(history), repeats * 4)

    def test_filter_trigger_spam(self):
        # test_filter_duplicates
        trigger = (EV_KEY, BTN_TL)

        _key_to_code = {
            ((*trigger, 1),): 51,
            ((*trigger, -1),): 52
        }

        uinput = UInput()

        keycode_mapper = KeycodeMapper(
            self.source, self.mapping, uinput,
            _key_to_code, {}
        )

        """positive"""

        for _ in range(1, 20):
            keycode_mapper.handle_keycode(new_event(*trigger, 1))
            self.assertIn(trigger, unreleased)

        keycode_mapper.handle_keycode(new_event(*trigger, 0))
        self.assertNotIn(trigger, unreleased)

        self.assertEqual(len(uinput_write_history), 2)

        """negative"""

        for _ in range(1, 20):
            keycode_mapper.handle_keycode(new_event(*trigger, -1))
            self.assertIn(trigger, unreleased)

        keycode_mapper.handle_keycode(new_event(*trigger, 0))
        self.assertNotIn(trigger, unreleased)

        self.assertEqual(len(uinput_write_history), 4)
        self.assertEqual(uinput_write_history[0].t, (EV_KEY, 51, 1))
        self.assertEqual(uinput_write_history[1].t, (EV_KEY, 51, 0))
        self.assertEqual(uinput_write_history[2].t, (EV_KEY, 52, 1))
        self.assertEqual(uinput_write_history[3].t, (EV_KEY, 52, 0))

    def test_ignore_hold(self):
        # hold as in event-value 2, not in macro-hold.
        # linux will generate events with value 2 after key-mapper injected
        # the key-press, so key-mapper doesn't need to forward them.
        key = (EV_KEY, KEY_A)
        ev_1 = (*key, 1)
        ev_2 = (*key, 2)
        ev_3 = (*key, 0)

        _key_to_code = {
            ((*key, 1),): 21,
        }

        uinput = UInput()

        keycode_mapper = KeycodeMapper(
            self.source, self.mapping, uinput,
            _key_to_code, {}
        )

        keycode_mapper.handle_keycode(new_event(*ev_1))

        for _ in range(10):
            keycode_mapper.handle_keycode(new_event(*ev_2))

        self.assertIn(key, unreleased)
        keycode_mapper.handle_keycode(new_event(*ev_3))
        self.assertNotIn(key, unreleased)

        self.assertEqual(len(uinput_write_history), 2)
        self.assertEqual(uinput_write_history[0].t, (EV_KEY, 21, 1))
        self.assertEqual(uinput_write_history[1].t, (EV_KEY, 21, 0))

    def test_ignore_disabled(self):
        ev_1 = (EV_ABS, ABS_HAT0Y, 1)
        ev_2 = (EV_ABS, ABS_HAT0Y, 0)

        ev_3 = (EV_ABS, ABS_HAT0X, 1)  # disabled
        ev_4 = (EV_ABS, ABS_HAT0X, 0)

        ev_5 = (EV_KEY, KEY_A, 1)
        ev_6 = (EV_KEY, KEY_A, 0)

        combi_1 = (ev_5, ev_3)
        combi_2 = (ev_3, ev_5)

        _key_to_code = {
            (ev_1,): 61,
            (ev_3,): DISABLE_CODE,
            combi_1: 62,
            combi_2: 63
        }

        uinput = UInput()

        keycode_mapper = KeycodeMapper(
            self.source, self.mapping, uinput,
            _key_to_code, {}
        )

        """single keys"""

        # down
        keycode_mapper.handle_keycode(new_event(*ev_1))
        keycode_mapper.handle_keycode(new_event(*ev_3))
        self.assertIn(ev_1[:2], unreleased)
        self.assertIn(ev_3[:2], unreleased)
        # up
        keycode_mapper.handle_keycode(new_event(*ev_2))
        keycode_mapper.handle_keycode(new_event(*ev_4))
        self.assertNotIn(ev_1[:2], unreleased)
        self.assertNotIn(ev_3[:2], unreleased)

        self.assertEqual(len(uinput_write_history), 2)
        self.assertEqual(uinput_write_history[0].t, (EV_KEY, 61, 1))
        self.assertEqual(uinput_write_history[1].t, (EV_KEY, 61, 0))

        """a combination that ends in a disabled key"""

        # ev_5 should be forwarded and the combination triggered
        keycode_mapper.handle_keycode(new_event(*combi_1[0]))
        keycode_mapper.handle_keycode(new_event(*combi_1[1]))
        self.assertEqual(len(uinput_write_history), 4)
        self.assertEqual(uinput_write_history[2].t, (EV_KEY, KEY_A, 1))
        self.assertEqual(uinput_write_history[3].t, (EV_KEY, 62, 1))
        self.assertIn(combi_1[0][:2], unreleased)
        self.assertIn(combi_1[1][:2], unreleased)
        # since this event did not trigger anything, key is None
        self.assertEqual(unreleased[combi_1[0][:2]].key, None)
        # that one triggered something from _key_to_code, so the key is that
        self.assertEqual(unreleased[combi_1[1][:2]].key, combi_1)

        # release the last key of the combi first, it should
        # release what the combination maps to
        event = new_event(combi_1[1][0], combi_1[1][1], 0)
        keycode_mapper.handle_keycode(event)
        self.assertEqual(len(uinput_write_history), 5)
        self.assertEqual(uinput_write_history[-1].t, (EV_KEY, 62, 0))
        self.assertIn(combi_1[0][:2], unreleased)
        self.assertNotIn(combi_1[1][:2], unreleased)

        event = new_event(combi_1[0][0], combi_1[0][1], 0)
        keycode_mapper.handle_keycode(event)
        self.assertEqual(len(uinput_write_history), 6)
        self.assertEqual(uinput_write_history[-1].t, (EV_KEY, KEY_A, 0))
        self.assertNotIn(combi_1[0][:2], unreleased)
        self.assertNotIn(combi_1[1][:2], unreleased)

        """a combination that starts with a disabled key"""

        # only the combination should get triggered
        keycode_mapper.handle_keycode(new_event(*combi_2[0]))
        keycode_mapper.handle_keycode(new_event(*combi_2[1]))
        self.assertEqual(len(uinput_write_history), 7)
        self.assertEqual(uinput_write_history[-1].t, (EV_KEY, 63, 1))

        # release the last key of the combi first, it should
        # release what the combination maps to
        event = new_event(combi_2[1][0], combi_2[1][1], 0)
        keycode_mapper.handle_keycode(event)
        self.assertEqual(len(uinput_write_history), 8)
        self.assertEqual(uinput_write_history[-1].t, (EV_KEY, 63, 0))

        # the first key of combi_2 is disabled, so it won't write another
        # key-up event
        event = new_event(combi_2[0][0], combi_2[0][1], 0)
        keycode_mapper.handle_keycode(event)
        self.assertEqual(len(uinput_write_history), 8)

    def test_combination_keycode_macro_mix(self):
        # ev_1 triggers macro, ev_1 + ev_2 triggers key while the macro is
        # still running
        system_mapping.clear()
        system_mapping._set('a', 92)

        down_1 = (EV_ABS, ABS_HAT1X, 1)
        down_2 = (EV_ABS, ABS_HAT1Y, -1)
        up_1 = (EV_ABS, ABS_HAT1X, 0)
        up_2 = (EV_ABS, ABS_HAT1Y, 0)

        macro_mapping = {(down_1,): parse('h(k(a))', self.mapping)}
        _key_to_code = {(down_1, down_2): 91}

        macro_history = []
        def handler(*args):
            macro_history.append(args)

        uinput = UInput()

        loop = asyncio.get_event_loop()

        keycode_mapper = KeycodeMapper(
            self.source, self.mapping, uinput,
            _key_to_code, macro_mapping
        )

        keycode_mapper.macro_write = handler

        # macro starts
        keycode_mapper.handle_keycode(new_event(*down_1))
        loop.run_until_complete(asyncio.sleep(0.05))
        self.assertEqual(len(uinput_write_history), 0)
        self.assertGreater(len(macro_history), 1)
        self.assertIn(down_1[:2], unreleased)
        self.assertIn((92, 1), macro_history)

        # combination triggered
        keycode_mapper.handle_keycode(new_event(*down_2))
        self.assertIn(down_1[:2], unreleased)
        self.assertIn(down_2[:2], unreleased)
        self.assertEqual(uinput_write_history[0].t, (EV_KEY, 91, 1))

        len_a = len(macro_history)
        loop.run_until_complete(asyncio.sleep(0.05))
        len_b = len(macro_history)
        # still running
        self.assertGreater(len_b, len_a)

        # release
        keycode_mapper.handle_keycode(new_event(*up_1))
        self.assertNotIn(down_1[:2], unreleased)
        self.assertIn(down_2[:2], unreleased)
        loop.run_until_complete(asyncio.sleep(0.05))
        len_c = len(macro_history)
        loop.run_until_complete(asyncio.sleep(0.05))
        len_d = len(macro_history)
        # not running anymore
        self.assertEqual(len_c, len_d)

        keycode_mapper.handle_keycode(new_event(*up_2))
        self.assertEqual(uinput_write_history[1].t, (EV_KEY, 91, 0))
        self.assertEqual(len(uinput_write_history), 2)
        self.assertNotIn(down_1[:2], unreleased)
        self.assertNotIn(down_2[:2], unreleased)

    def test_wheel_combination_release_failure(self):
        # test based on a bug that once occurred
        # 1 | 22.6698, ((1, 276, 1)) -------------- forwarding
        # 2 | 22.9904, ((1, 276, 1), (2, 8, -1)) -- maps to 30
        # 3 | 23.0103, ((1, 276, 1), (2, 8, -1)) -- duplicate key down
        # 4 | ... 34 more duplicate key downs (scrolling)
        # 5 | 23.7104, ((1, 276, 1), (2, 8, -1)) -- duplicate key down
        # 6 | 23.7283, ((1, 276, 0)) -------------- forwarding release
        # 7 | 23.7303, ((2, 8, -1)) --------------- forwarding
        # 8 | 23.7865, ((2, 8, 0)) ---------------- not forwarding release
        # line 7 should have been "duplicate key down" as well
        # line 8 should have released 30, instead it was never released

        scroll = (2, 8, -1)
        scroll_up = (2, 8, 0)
        btn_down = (1, 276, 1)
        btn_up = (1, 276, 0)
        combination = ((1, 276, 1), (2, 8, -1))

        system_mapping.clear()
        system_mapping._set('a', 30)
        k2c = {combination: 30}

        uinput = UInput()

        keycode_mapper = KeycodeMapper(
            self.source, self.mapping,
            uinput, k2c, {}
        )

        keycode_mapper.handle_keycode(new_event(*btn_down))
        # "forwarding"
        self.assertEqual(uinput_write_history[0].t, btn_down)

        keycode_mapper.handle_keycode(new_event(*scroll))
        # "maps to 30"
        self.assertEqual(uinput_write_history[1].t, (1, 30, 1))

        for _ in range(5):
            # keep scrolling
            # "duplicate key down"
            keycode_mapper.handle_keycode(new_event(*scroll))

        # nothing new since all of them were duplicate key downs
        self.assertEqual(len(uinput_write_history), 2)

        keycode_mapper.handle_keycode(new_event(*btn_up))
        # "forwarding release"
        self.assertEqual(uinput_write_history[2].t, btn_up)

        # one more scroll event. since the combination is still not released,
        # it should be ignored as duplicate key-down
        self.assertEqual(len(uinput_write_history), 3)
        # "forwarding" (should be "duplicate key down")
        keycode_mapper.handle_keycode(new_event(*scroll))
        self.assertEqual(len(uinput_write_history), 3)

        # the failure to release the mapped key
        # forward=False is what the debouncer uses, because a
        # "scroll release" doesn't actually exist so it is not actually
        # written if it doesn't release any mapping
        keycode_mapper.handle_keycode(new_event(*scroll_up), forward=False)

        # 30 should be released
        self.assertEqual(uinput_write_history[3].t, (1, 30, 0))
        self.assertEqual(len(uinput_write_history), 4)


if __name__ == "__main__":
    unittest.main()
