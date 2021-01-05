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
    ABS_HAT0X, ABS_HAT0Y, ABS_HAT1X, ABS_HAT1Y

from keymapper.dev.keycode_mapper import active_macros, handle_keycode,\
    unreleased, subsets
from keymapper.state import system_mapping
from keymapper.dev.macros import parse
from keymapper.config import config
from keymapper.mapping import Mapping, DISABLE_CODE

from tests.test import new_event, UInput, uinput_write_history, \
    cleanup


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

    def tearDown(self):
        # make sure all macros are stopped by tests
        for macro in active_macros.values():
            if macro.holding:
                macro.release_key()
            self.assertFalse(macro.holding)
            self.assertFalse(macro.running)

        cleanup()

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
        # a bunch of d-pad key down events at once
        handle_keycode(_key_to_code, {}, new_event(*ev_1), uinput)
        handle_keycode(_key_to_code, {}, new_event(*ev_4), uinput)
        self.assertEqual(len(unreleased), 2)
        self.assertEqual(unreleased.get(ev_1[:2]), ((EV_KEY, _key_to_code[(ev_1,)]), ev_1))
        self.assertEqual(unreleased.get(ev_4[:2]), ((EV_KEY, _key_to_code[(ev_4,)]), ev_4))

        # release all of them
        handle_keycode(_key_to_code, {}, new_event(*ev_3), uinput)
        handle_keycode(_key_to_code, {}, new_event(*ev_6), uinput)
        self.assertEqual(len(unreleased), 0)

        # repeat with other values
        handle_keycode(_key_to_code, {}, new_event(*ev_2), uinput)
        handle_keycode(_key_to_code, {}, new_event(*ev_5), uinput)
        self.assertEqual(len(unreleased), 2)
        self.assertEqual(unreleased.get(ev_2[:2]), ((EV_KEY, _key_to_code[(ev_2,)]), ev_2))
        self.assertEqual(unreleased.get(ev_5[:2]), ((EV_KEY, _key_to_code[(ev_5,)]), ev_5))

        # release all of them again
        handle_keycode(_key_to_code, {}, new_event(*ev_3), uinput)
        handle_keycode(_key_to_code, {}, new_event(*ev_6), uinput)
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

        handle_keycode({}, {}, new_event(*down), uinput, False)
        self.assertEqual(unreleased[(EV_KEY, 91)], (down[:2], down))
        self.assertEqual(len(unreleased), 1)
        self.assertEqual(uinput.write_count, 0)

        handle_keycode({}, {}, new_event(*up), uinput, False)
        self.assertEqual(len(unreleased), 0)
        self.assertEqual(uinput.write_count, 0)

    def test_dont_filter_unmapped(self):
        # if an event is not used at all, it should be written into
        # unmapped but not furthermore modified
        down = (EV_KEY, 91, 1)
        up = (EV_KEY, 91, 0)
        uinput = UInput()

        for _ in range(10):
            handle_keycode({}, {}, new_event(*down), uinput)

        self.assertEqual(unreleased[(EV_KEY, 91)], (down[:2], down))
        self.assertEqual(len(unreleased), 1)
        self.assertEqual(uinput.write_count, 10)

        handle_keycode({}, {}, new_event(*up), uinput)
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

        handle_keycode(key_to_code, {}, new_event(*down_1), uinput)
        for _ in range(10):
            handle_keycode(key_to_code, {}, new_event(*down_2), uinput)

        # all duplicate down events should have been ignored
        self.assertEqual(len(unreleased), 2)
        self.assertEqual(uinput.write_count, 2)
        self.assertEqual(uinput_write_history[0].t, down_1)
        self.assertEqual(uinput_write_history[1].t, (EV_KEY, output, 1))

        handle_keycode({}, {}, new_event(*up_1), uinput)
        handle_keycode({}, {}, new_event(*up_2), uinput)
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
        # a bunch of d-pad key down events at once
        handle_keycode(_key_to_code, {}, new_event(*ev_1), uinput)
        handle_keycode(_key_to_code, {}, new_event(*ev_2), uinput)
        # (what_will_be_released, what_caused_the_key_down)
        self.assertEqual(unreleased.get(ev_1[:2]), ((EV_ABS, ABS_HAT0X), ev_1))
        self.assertEqual(unreleased.get(ev_2[:2]), ((EV_KEY, 51), ev_2))
        self.assertEqual(len(unreleased), 2)

        # ev_1 is unmapped and the other is the triggered combination
        self.assertEqual(len(uinput_write_history), 2)
        self.assertEqual(uinput_write_history[0].t, ev_1)
        self.assertEqual(uinput_write_history[1].t, (EV_KEY, 51, 1))

        # release all of them
        handle_keycode(_key_to_code, {}, new_event(*ev_3), uinput)
        handle_keycode(_key_to_code, {}, new_event(*ev_4), uinput)
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
        handle_keycode(_key_to_code, {}, new_event(EV_KEY, 1, 1), uinput)
        handle_keycode(_key_to_code, {}, new_event(EV_KEY, 3, 1), uinput)
        handle_keycode(_key_to_code, {}, new_event(EV_KEY, 2, 1), uinput)

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
        handle_keycode(_key_to_code, {}, new_event(*combination[0]), uinput)
        handle_keycode(_key_to_code, {}, new_event(*combination[1]), uinput)

        self.assertEqual(len(uinput_write_history), 2)
        # the first event is written and then the triggered combination
        self.assertEqual(uinput_write_history[0].t, (EV_KEY, 1, 1))
        self.assertEqual(uinput_write_history[1].t, (EV_KEY, 101, 1))

        # release them
        handle_keycode(_key_to_code, {}, new_event(*combination[0][:2], 0), uinput)
        handle_keycode(_key_to_code, {}, new_event(*combination[1][:2], 0), uinput)
        # the first key writes its release event. The second key is hidden
        # behind the executed combination. The result of the combination is
        # also released, because it acts like a key.
        self.assertEqual(len(uinput_write_history), 4)
        self.assertEqual(uinput_write_history[2].t, (EV_KEY, 1, 0))
        self.assertEqual(uinput_write_history[3].t, (EV_KEY, 101, 0))

        # press them in the wrong order (the wrong key at the end, the order
        # of all other keys won't matter). no combination should be triggered
        handle_keycode(_key_to_code, {}, new_event(*combination[1]), uinput)
        handle_keycode(_key_to_code, {}, new_event(*combination[0]), uinput)
        self.assertEqual(len(uinput_write_history), 6)
        self.assertEqual(uinput_write_history[4].t, (EV_KEY, 2, 1))
        self.assertEqual(uinput_write_history[5].t, (EV_KEY, 1, 1))

    def test_combination_keycode_2(self):
        combination_1 = (
            (EV_KEY, 1, 1),
            (EV_KEY, 2, 1),
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

        _key_to_code = {
            combination_1: 101,
            combination_2: 102,
            (down_5,): 103
        }

        uinput = UInput()
        # 10 and 11: more key-down events than needed
        handle_keycode(_key_to_code, {}, new_event(EV_KEY, 10, 1), uinput)
        handle_keycode(_key_to_code, {}, new_event(*combination_1[0]), uinput)
        handle_keycode(_key_to_code, {}, new_event(*combination_1[1]), uinput)
        handle_keycode(_key_to_code, {}, new_event(*combination_1[2]), uinput)
        handle_keycode(_key_to_code, {}, new_event(EV_KEY, 11, 1), uinput)
        handle_keycode(_key_to_code, {}, new_event(*combination_1[3]), uinput)

        self.assertEqual(len(uinput_write_history), 6)
        # the first event is written and then the triggered combination
        self.assertEqual(uinput_write_history[1].t, (EV_KEY, 1, 1))
        self.assertEqual(uinput_write_history[2].t, (EV_KEY, 2, 1))
        self.assertEqual(uinput_write_history[3].t, (EV_KEY, 3, 1))
        self.assertEqual(uinput_write_history[5].t, (EV_KEY, 101, 1))

        # while the combination is down, another unrelated key can be used
        handle_keycode(_key_to_code, {}, new_event(*down_5), uinput)
        # the keycode_mapper searches for subsets of the current held-down
        # keys to activate combinations, down_5 should not trigger them
        # again.
        self.assertEqual(len(uinput_write_history), 7)
        self.assertEqual(uinput_write_history[6].t, (EV_KEY, 103, 1))

        # release the combination by releasing the last key, and release
        # the unrelated key
        handle_keycode(_key_to_code, {}, new_event(*up_4), uinput)
        handle_keycode(_key_to_code, {}, new_event(*up_5), uinput)
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

        macro_mapping[((EV_KEY, 1, 1),)].set_handler(lambda *args: history.append(args))
        macro_mapping[((EV_KEY, 2, 1),)].set_handler(lambda *args: history.append(args))

        handle_keycode({}, macro_mapping, new_event(EV_KEY, 1, 1), None)
        handle_keycode({}, macro_mapping, new_event(EV_KEY, 2, 1), None)

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
        handle_keycode({}, macro_mapping, new_event(EV_KEY, 1, 0), None)
        handle_keycode({}, macro_mapping, new_event(EV_KEY, 2, 0), None)
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

        macro_mapping[((EV_KEY, 1, 1),)].set_handler(handler)

        """start macro"""

        handle_keycode({}, macro_mapping, new_event(EV_KEY, 1, 1), None)

        loop = asyncio.get_event_loop()

        # let the mainloop run for some time so that the macro does its stuff
        sleeptime = 500
        keystroke_sleep = config.get('macros.keystroke_sleep_ms', 10)
        loop.run_until_complete(asyncio.sleep(sleeptime / 1000))

        self.assertTrue(active_macros[(EV_KEY, 1)].holding)
        self.assertTrue(active_macros[(EV_KEY, 1)].running)

        """stop macro"""

        handle_keycode({}, macro_mapping, new_event(EV_KEY, 1, 0), None)

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

        self.assertFalse(active_macros[(EV_KEY, 1)].holding)
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

        macro_mapping[((EV_KEY, 1, 1),)].set_handler(handler)
        macro_mapping[((EV_KEY, 2, 1),)].set_handler(handler)
        macro_mapping[((EV_KEY, 3, 1),)].set_handler(handler)

        """start macro 2"""

        handle_keycode({}, macro_mapping, new_event(EV_KEY, 2, 1), None)
        loop = asyncio.get_event_loop()

        loop.run_until_complete(asyncio.sleep(0.1))
        # starting code_c written
        self.assertEqual(history.count((code_c, 1)), 1)
        self.assertEqual(history.count((code_c, 0)), 1)

        # spam garbage events
        for _ in range(5):
            handle_keycode({}, macro_mapping, new_event(EV_KEY, 1, 1), None)
            handle_keycode({}, macro_mapping, new_event(EV_KEY, 3, 1), None)
            loop.run_until_complete(asyncio.sleep(0.05))
            self.assertTrue(active_macros[(EV_KEY, 1)].holding)
            self.assertTrue(active_macros[(EV_KEY, 1)].running)
            self.assertTrue(active_macros[(EV_KEY, 2)].holding)
            self.assertTrue(active_macros[(EV_KEY, 2)].running)
            self.assertTrue(active_macros[(EV_KEY, 3)].holding)
            self.assertTrue(active_macros[(EV_KEY, 3)].running)

        # there should only be one code_c in the events, because no key
        # up event was ever done so the hold just continued
        self.assertEqual(history.count((code_c, 1)), 1)
        self.assertEqual(history.count((code_c, 0)), 1)
        # without an key up event on 2, it won't write code_d
        self.assertNotIn((code_d, 1), history)
        self.assertNotIn((code_d, 0), history)

        # stop macro 2
        handle_keycode({}, macro_mapping, new_event(EV_KEY, 2, 0), None)
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

        handle_keycode({}, macro_mapping, new_event(EV_KEY, 2, 1), None)
        loop.run_until_complete(asyncio.sleep(0.1))
        self.assertEqual(history.count((code_c, 1)), 1)
        self.assertEqual(history.count((code_c, 0)), 1)

        # spam garbage events again, this time key-up events on all other
        # macros
        for _ in range(5):
            handle_keycode({}, macro_mapping, new_event(EV_KEY, 1, 0), None)
            handle_keycode({}, macro_mapping, new_event(EV_KEY, 3, 0), None)
            loop.run_until_complete(asyncio.sleep(0.05))
            self.assertFalse(active_macros[(EV_KEY, 1)].holding)
            self.assertFalse(active_macros[(EV_KEY, 1)].running)
            self.assertTrue(active_macros[(EV_KEY, 2)].holding)
            self.assertTrue(active_macros[(EV_KEY, 2)].running)
            self.assertFalse(active_macros[(EV_KEY, 3)].holding)
            self.assertFalse(active_macros[(EV_KEY, 3)].running)

        # stop macro 2
        handle_keycode({}, macro_mapping, new_event(EV_KEY, 2, 0), None)
        loop.run_until_complete(asyncio.sleep(0.1))
        # was started only once
        self.assertEqual(history.count((code_c, 1)), 1)
        self.assertEqual(history.count((code_c, 0)), 1)
        # and the trailing d was also written only once
        self.assertEqual(history.count((code_d, 1)), 1)
        self.assertEqual(history.count((code_d, 0)), 1)

        # stop all macros
        handle_keycode({}, macro_mapping, new_event(EV_KEY, 1, 0), None)
        handle_keycode({}, macro_mapping, new_event(EV_KEY, 3, 0), None)
        loop.run_until_complete(asyncio.sleep(0.1))

        # it's stopped and won't write stuff anymore
        count_before = len(history)
        loop.run_until_complete(asyncio.sleep(0.1))
        count_after = len(history)
        self.assertEqual(count_before, count_after)

        self.assertFalse(active_macros[(EV_KEY, 1)].holding)
        self.assertFalse(active_macros[(EV_KEY, 1)].running)
        self.assertFalse(active_macros[(EV_KEY, 2)].holding)
        self.assertFalse(active_macros[(EV_KEY, 2)].running)
        self.assertFalse(active_macros[(EV_KEY, 3)].holding)
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

        macro_mapping[((EV_KEY, 1, 1),)].set_handler(handler)

        handle_keycode({}, macro_mapping, new_event(EV_KEY, 1, 1), None)
        loop = asyncio.get_event_loop()

        loop.run_until_complete(asyncio.sleep(0.1))
        for _ in range(5):
            self.assertTrue(active_macros[(EV_KEY, 1)].holding)
            self.assertTrue(active_macros[(EV_KEY, 1)].running)
            handle_keycode({}, macro_mapping, new_event(EV_KEY, 1, 1), None)
            loop.run_until_complete(asyncio.sleep(0.05))

        # duplicate key down events don't do anything
        self.assertEqual(history.count((code_a, 1)), 1)
        self.assertEqual(history.count((code_a, 0)), 1)
        self.assertEqual(history.count((code_c, 1)), 0)
        self.assertEqual(history.count((code_c, 0)), 0)

        # stop
        handle_keycode({}, macro_mapping, new_event(EV_KEY, 1, 0), None)
        loop.run_until_complete(asyncio.sleep(0.1))
        self.assertEqual(history.count((code_a, 1)), 1)
        self.assertEqual(history.count((code_a, 0)), 1)
        self.assertEqual(history.count((code_c, 1)), 1)
        self.assertEqual(history.count((code_c, 0)), 1)
        self.assertFalse(active_macros[(EV_KEY, 1)].holding)
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

        macro_mapping[(down_0, down_1)].set_handler(handler)
        macro_mapping[(down_2,)].set_handler(handler)

        loop = asyncio.get_event_loop()

        macros_uinput = UInput()
        keys_uinput = UInput()

        # key up won't do anything
        handle_keycode({}, macro_mapping, new_event(*up_0), macros_uinput)
        handle_keycode({}, macro_mapping, new_event(*up_1), macros_uinput)
        handle_keycode({}, macro_mapping, new_event(*up_2), macros_uinput)
        loop.run_until_complete(asyncio.sleep(0.1))
        self.assertEqual(len(active_macros), 0)

        """start macros"""

        handle_keycode({}, macro_mapping, new_event(*down_0), keys_uinput)
        self.assertEqual(keys_uinput.write_count, 1)
        handle_keycode({}, macro_mapping, new_event(*down_1), keys_uinput)
        handle_keycode({}, macro_mapping, new_event(*down_2), keys_uinput)
        self.assertEqual(keys_uinput.write_count, 1)

        # let the mainloop run for some time so that the macro does its stuff
        sleeptime = 500
        keystroke_sleep = config.get('macros.keystroke_sleep_ms', 10)
        loop.run_until_complete(asyncio.sleep(sleeptime / 1000))

        self.assertEqual(len(active_macros), 2)
        self.assertTrue(active_macros[key_1].holding)
        self.assertTrue(active_macros[key_1].running)
        self.assertTrue(active_macros[key_2].holding)
        self.assertTrue(active_macros[key_2].running)

        self.assertIn(down_0[:2], unreleased)
        self.assertIn(down_1[:2], unreleased)
        self.assertIn(down_2[:2], unreleased)

        """stop macros"""

        # releasing the last key of a combination releases the whole macro
        handle_keycode({}, macro_mapping, new_event(*up_1), None)
        handle_keycode({}, macro_mapping, new_event(*up_2), None)

        self.assertIn(down_0[:2], unreleased)
        self.assertNotIn(down_1[:2], unreleased)
        self.assertNotIn(down_2[:2], unreleased)

        loop.run_until_complete(asyncio.sleep(keystroke_sleep * 10 / 1000))

        self.assertFalse(active_macros[key_1].holding)
        self.assertFalse(active_macros[key_1].running)
        self.assertFalse(active_macros[key_2].holding)
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

        macro_mapping[(right,)].set_handler(handler)
        macro_mapping[(left,)].set_handler(handler)

        handle_keycode({}, macro_mapping, new_event(*right), None)
        self.assertIn((EV_ABS, ABS_HAT0X), unreleased)
        handle_keycode({}, macro_mapping, new_event(*release), None)
        self.assertNotIn((EV_ABS, ABS_HAT0X), unreleased)
        handle_keycode({}, macro_mapping, new_event(*left), None)
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

        """positive"""

        for _ in range(1, 20):
            handle_keycode(_key_to_code, {}, new_event(*trigger, 1), uinput)
            self.assertIn(trigger, unreleased)

        handle_keycode(_key_to_code, {}, new_event(*trigger, 0), uinput)
        self.assertNotIn(trigger, unreleased)

        self.assertEqual(len(uinput_write_history), 2)

        """negative"""

        for _ in range(1, 20):
            handle_keycode(_key_to_code, {}, new_event(*trigger, -1), uinput)
            self.assertIn(trigger, unreleased)

        handle_keycode(_key_to_code, {}, new_event(*trigger, 0), uinput)
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
        handle_keycode(_key_to_code, {}, new_event(*ev_1), uinput)

        for _ in range(10):
            handle_keycode(_key_to_code, {}, new_event(*ev_2), uinput)

        self.assertIn(key, unreleased)
        handle_keycode(_key_to_code, {}, new_event(*ev_3), uinput)
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

        """single keys"""

        # down
        handle_keycode(_key_to_code, {}, new_event(*ev_1), uinput)
        handle_keycode(_key_to_code, {}, new_event(*ev_3), uinput)
        self.assertIn(ev_1[:2], unreleased)
        self.assertIn(ev_3[:2], unreleased)
        # up
        handle_keycode(_key_to_code, {}, new_event(*ev_2), uinput)
        handle_keycode(_key_to_code, {}, new_event(*ev_4), uinput)
        self.assertNotIn(ev_1[:2], unreleased)
        self.assertNotIn(ev_3[:2], unreleased)

        self.assertEqual(len(uinput_write_history), 2)
        self.assertEqual(uinput_write_history[0].t, (EV_KEY, 61, 1))
        self.assertEqual(uinput_write_history[1].t, (EV_KEY, 61, 0))

        """a combination that ends in a disabled key"""

        # ev_5 should be forwarded and the combination triggered
        handle_keycode(_key_to_code, {}, new_event(*combi_1[0]), uinput)
        handle_keycode(_key_to_code, {}, new_event(*combi_1[1]), uinput)
        self.assertEqual(len(uinput_write_history), 4)
        self.assertEqual(uinput_write_history[2].t, (EV_KEY, KEY_A, 1))
        self.assertEqual(uinput_write_history[3].t, (EV_KEY, 62, 1))
        self.assertIn(combi_1[0][:2], unreleased)
        self.assertIn(combi_1[1][:2], unreleased)

        # release the last key of the combi first, it should
        # release what the combination maps to
        event = new_event(combi_1[1][0], combi_1[1][1], 0)
        handle_keycode(_key_to_code, {}, event, uinput)
        self.assertEqual(len(uinput_write_history), 5)
        self.assertEqual(uinput_write_history[-1].t, (EV_KEY, 62, 0))
        self.assertIn(combi_1[0][:2], unreleased)
        self.assertNotIn(combi_1[1][:2], unreleased)

        event = new_event(combi_1[0][0], combi_1[0][1], 0)
        handle_keycode(_key_to_code, {}, event, uinput)
        self.assertEqual(len(uinput_write_history), 6)
        self.assertEqual(uinput_write_history[-1].t, (EV_KEY, KEY_A, 0))
        self.assertNotIn(combi_1[0][:2], unreleased)
        self.assertNotIn(combi_1[1][:2], unreleased)

        """a combination that starts with a disabled key"""

        # only the combination should get triggered
        handle_keycode(_key_to_code, {}, new_event(*combi_2[0]), uinput)
        handle_keycode(_key_to_code, {}, new_event(*combi_2[1]), uinput)
        self.assertEqual(len(uinput_write_history), 7)
        self.assertEqual(uinput_write_history[-1].t, (EV_KEY, 63, 1))

        # release the last key of the combi first, it should
        # release what the combination maps to
        event = new_event(combi_2[1][0], combi_2[1][1], 0)
        handle_keycode(_key_to_code, {}, event, uinput)
        self.assertEqual(len(uinput_write_history), 8)
        self.assertEqual(uinput_write_history[-1].t, (EV_KEY, 63, 0))

        # the first key of combi_2 is disabled, so it won't write another
        # key-up event
        event = new_event(combi_2[0][0], combi_2[0][1], 0)
        handle_keycode(_key_to_code, {}, event, uinput)
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
        macro_mapping[(down_1,)].set_handler(handler)

        uinput = UInput()

        loop = asyncio.get_event_loop()

        # macro starts
        handle_keycode(_key_to_code, macro_mapping, new_event(*down_1), uinput)
        loop.run_until_complete(asyncio.sleep(0.05))
        self.assertEqual(len(uinput_write_history), 0)
        self.assertGreater(len(macro_history), 1)
        self.assertIn(down_1[:2], unreleased)
        self.assertIn((92, 1), macro_history)

        # combination triggered
        handle_keycode(_key_to_code, macro_mapping, new_event(*down_2), uinput)
        self.assertIn(down_1[:2], unreleased)
        self.assertIn(down_2[:2], unreleased)
        self.assertEqual(uinput_write_history[0].t, (EV_KEY, 91, 1))

        len_a = len(macro_history)
        loop.run_until_complete(asyncio.sleep(0.05))
        len_b = len(macro_history)
        # still running
        self.assertGreater(len_b, len_a)

        # release
        handle_keycode(_key_to_code, macro_mapping, new_event(*up_1), uinput)
        self.assertNotIn(down_1[:2], unreleased)
        self.assertIn(down_2[:2], unreleased)
        loop.run_until_complete(asyncio.sleep(0.05))
        len_c = len(macro_history)
        loop.run_until_complete(asyncio.sleep(0.05))
        len_d = len(macro_history)
        # not running anymore
        self.assertEqual(len_c, len_d)

        handle_keycode(_key_to_code, macro_mapping, new_event(*up_2), uinput)
        self.assertEqual(uinput_write_history[1].t, (EV_KEY, 91, 0))
        self.assertEqual(len(uinput_write_history), 2)
        self.assertNotIn(down_1[:2], unreleased)
        self.assertNotIn(down_2[:2], unreleased)


if __name__ == "__main__":
    unittest.main()
