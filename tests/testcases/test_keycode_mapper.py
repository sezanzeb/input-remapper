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
import asyncio

from evdev.ecodes import EV_KEY, EV_ABS, ABS_HAT0X, KEY_A, ABS_X, EV_REL, REL_X

from keymapper.dev.keycode_mapper import should_map_event_as_btn, \
    active_macros, handle_keycode
from keymapper.state import system_mapping
from keymapper.dev.macros import parse
from keymapper.config import config

from tests.test import InputEvent


class TestKeycodeMapper(unittest.TestCase):
    def tearDown(self):
        # make sure all macros are stopped by tests
        for code in active_macros:
            macro = active_macros[code]
            if macro.holding:
                macro.release_key()
            self.assertFalse(macro.holding)
            self.assertFalse(macro.running)

        keys = list(active_macros.keys())
        for key in keys:
            del active_macros[key]

        system_mapping.populate()

    def test_should_map_event_as_btn(self):
        self.assertTrue(should_map_event_as_btn(EV_ABS, ABS_HAT0X))
        self.assertTrue(should_map_event_as_btn(EV_KEY, KEY_A))
        self.assertFalse(should_map_event_as_btn(EV_ABS, ABS_X))
        self.assertFalse(should_map_event_as_btn(EV_REL, REL_X))

    def test_handle_keycode(self):
        _code_to_code = {
            1: 101,
            2: 102
        }

        history = []

        class UInput:
            def write(self, type, code, value):
                history.append((type, code, value))

            def syn(self):
                pass

        uinput = UInput()

        handle_keycode(_code_to_code, {}, InputEvent(EV_KEY, 1, 1), uinput)
        handle_keycode(_code_to_code, {}, InputEvent(EV_KEY, 3, 1), uinput)
        handle_keycode(_code_to_code, {}, InputEvent(EV_KEY, 2, 1), uinput)

        self.assertEqual(len(history), 3)
        self.assertEqual(history[0], (EV_KEY, 101, 1))
        self.assertEqual(history[1], (EV_KEY, 3, 1))
        self.assertEqual(history[2], (EV_KEY, 102, 1))

    def test_handle_keycode_macro(self):
        history = []

        code_a = 100
        code_b = 101
        system_mapping.clear()
        system_mapping._set('a', code_a)
        system_mapping._set('b', code_b)

        macro_mapping = {
            1: parse('k(a)'),
            2: parse('r(5, k(b))')
        }

        macro_mapping[1].set_handler(lambda *args: history.append(args))
        macro_mapping[2].set_handler(lambda *args: history.append(args))

        handle_keycode({}, macro_mapping, InputEvent(EV_KEY, 1, 1), None)
        handle_keycode({}, macro_mapping, InputEvent(EV_KEY, 2, 1), None)

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

    def calculate_event_number(self, holdtime, before, after):
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
            1: parse('k(a).h(k(b)).k(c)')
        }

        def handler(*args):
            history.append(args)

        macro_mapping[1].set_handler(handler)

        """start macro"""

        handle_keycode({}, macro_mapping, InputEvent(EV_KEY, 1, 1), None)

        loop = asyncio.get_event_loop()

        # let the mainloop run for some time so that the macro does its stuff
        sleeptime = 500
        keystroke_sleep = config.get('macros.keystroke_sleep_ms', 10)
        loop.run_until_complete(asyncio.sleep(sleeptime / 1000))

        self.assertTrue(active_macros[1].holding)
        self.assertTrue(active_macros[1].running)

        """stop macro"""

        handle_keycode({}, macro_mapping, InputEvent(EV_KEY, 1, 0), None)

        loop.run_until_complete(asyncio.sleep(keystroke_sleep * 10 / 1000))

        events = self.calculate_event_number(sleeptime, 1, 1)

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

        self.assertFalse(active_macros[1].holding)
        self.assertFalse(active_macros[1].running)

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
            1: parse('h(k(b))'),
            2: parse('k(c).r(1, r(1, r(1, h(k(a))))).k(d)'),
            3: parse('h(k(b))')
        }

        history = []

        def handler(*args):
            history.append(args)

        macro_mapping[1].set_handler(handler)
        macro_mapping[2].set_handler(handler)
        macro_mapping[3].set_handler(handler)

        """start macro 2"""

        handle_keycode({}, macro_mapping, InputEvent(EV_KEY, 2, 1), None)
        loop = asyncio.get_event_loop()

        loop.run_until_complete(asyncio.sleep(0.1))
        # starting code_c written
        self.assertEqual(history.count((code_c, 1)), 1)
        self.assertEqual(history.count((code_c, 0)), 1)

        # spam garbage events
        for _ in range(5):
            handle_keycode({}, macro_mapping, InputEvent(EV_KEY, 1, 1), None)
            handle_keycode({}, macro_mapping, InputEvent(EV_KEY, 3, 1), None)
            loop.run_until_complete(asyncio.sleep(0.05))
            self.assertTrue(active_macros[1].holding)
            self.assertTrue(active_macros[1].running)
            self.assertTrue(active_macros[2].holding)
            self.assertTrue(active_macros[2].running)
            self.assertTrue(active_macros[3].holding)
            self.assertTrue(active_macros[3].running)

        # there should only be one code_c in the events, because no key
        # up event was ever done so the hold just continued
        self.assertEqual(history.count((code_c, 1)), 1)
        self.assertEqual(history.count((code_c, 0)), 1)
        # without an key up event on 2, it won't write code_d
        self.assertNotIn((code_d, 1), history)
        self.assertNotIn((code_d, 0), history)

        # stop macro 2
        handle_keycode({}, macro_mapping, InputEvent(EV_KEY, 2, 0), None)
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

        handle_keycode({}, macro_mapping, InputEvent(EV_KEY, 2, 1), None)
        loop.run_until_complete(asyncio.sleep(0.1))
        self.assertEqual(history.count((code_c, 1)), 1)
        self.assertEqual(history.count((code_c, 0)), 1)

        # spam garbage events again, this time key-up events on all other
        # macros
        for _ in range(5):
            handle_keycode({}, macro_mapping, InputEvent(EV_KEY, 1, 0), None)
            handle_keycode({}, macro_mapping, InputEvent(EV_KEY, 3, 0), None)
            loop.run_until_complete(asyncio.sleep(0.05))
            self.assertFalse(active_macros[1].holding)
            self.assertFalse(active_macros[1].running)
            self.assertTrue(active_macros[2].holding)
            self.assertTrue(active_macros[2].running)
            self.assertFalse(active_macros[3].holding)
            self.assertFalse(active_macros[3].running)

        # stop macro 2
        handle_keycode({}, macro_mapping, InputEvent(EV_KEY, 2, 0), None)
        loop.run_until_complete(asyncio.sleep(0.1))
        # was started only once
        self.assertEqual(history.count((code_c, 1)), 1)
        self.assertEqual(history.count((code_c, 0)), 1)
        # and the trailing d was also written only once
        self.assertEqual(history.count((code_d, 1)), 1)
        self.assertEqual(history.count((code_d, 0)), 1)

        # stop all macros
        handle_keycode({}, macro_mapping, InputEvent(EV_KEY, 1, 0), None)
        handle_keycode({}, macro_mapping, InputEvent(EV_KEY, 3, 0), None)
        loop.run_until_complete(asyncio.sleep(0.1))

        # it's stopped and won't write stuff anymore
        count_before = len(history)
        loop.run_until_complete(asyncio.sleep(0.1))
        count_after = len(history)
        self.assertEqual(count_before, count_after)

        self.assertFalse(active_macros[1].holding)
        self.assertFalse(active_macros[1].running)
        self.assertFalse(active_macros[2].holding)
        self.assertFalse(active_macros[2].running)
        self.assertFalse(active_macros[3].holding)
        self.assertFalse(active_macros[3].running)

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
            1: parse('k(a).h(k(b)).k(c)'),
        }

        history = []

        def handler(*args):
            history.append(args)

        macro_mapping[1].set_handler(handler)

        handle_keycode({}, macro_mapping, InputEvent(EV_KEY, 1, 1), None)
        loop = asyncio.get_event_loop()

        loop.run_until_complete(asyncio.sleep(0.1))
        for _ in range(5):
            self.assertTrue(active_macros[1].holding)
            self.assertTrue(active_macros[1].running)
            handle_keycode({}, macro_mapping, InputEvent(EV_KEY, 1, 1), None)
            loop.run_until_complete(asyncio.sleep(0.05))

        # duplicate key down events don't do anything
        self.assertEqual(history.count((code_a, 1)), 1)
        self.assertEqual(history.count((code_a, 0)), 1)
        self.assertEqual(history.count((code_c, 1)), 0)
        self.assertEqual(history.count((code_c, 0)), 0)

        # stop
        handle_keycode({}, macro_mapping, InputEvent(EV_KEY, 1, 0), None)
        loop.run_until_complete(asyncio.sleep(0.1))
        self.assertEqual(history.count((code_a, 1)), 1)
        self.assertEqual(history.count((code_a, 0)), 1)
        self.assertEqual(history.count((code_c, 1)), 1)
        self.assertEqual(history.count((code_c, 0)), 1)
        self.assertFalse(active_macros[1].holding)
        self.assertFalse(active_macros[1].running)

        # it's stopped and won't write stuff anymore
        count_before = len(history)
        loop.run_until_complete(asyncio.sleep(0.1))
        count_after = len(history)
        self.assertEqual(count_before, count_after)

    def test_hold_two(self):
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

        macro_mapping = {
            1: parse('k(1).h(k(2)).k(3)'),
            2: parse('k(a).h(k(b)).k(c)')
        }

        def handler(*args):
            history.append(args)

        macro_mapping[1].set_handler(handler)
        macro_mapping[2].set_handler(handler)

        loop = asyncio.get_event_loop()

        # key up won't do anything
        handle_keycode({}, macro_mapping, InputEvent(EV_KEY, 1, 0), None)
        handle_keycode({}, macro_mapping, InputEvent(EV_KEY, 2, 0), None)
        loop.run_until_complete(asyncio.sleep(0.1))
        self.assertEqual(len(active_macros), 0)

        """start macros"""

        handle_keycode({}, macro_mapping, InputEvent(EV_KEY, 1, 1), None)
        handle_keycode({}, macro_mapping, InputEvent(EV_KEY, 2, 1), None)

        # let the mainloop run for some time so that the macro does its stuff
        sleeptime = 500
        keystroke_sleep = config.get('macros.keystroke_sleep_ms', 10)
        loop.run_until_complete(asyncio.sleep(sleeptime / 1000))

        self.assertEqual(len(active_macros), 2)
        self.assertTrue(active_macros[1].holding)
        self.assertTrue(active_macros[1].running)
        self.assertTrue(active_macros[2].holding)
        self.assertTrue(active_macros[2].running)

        """stop macros"""

        handle_keycode({}, macro_mapping, InputEvent(EV_KEY, 1, 0), None)
        handle_keycode({}, macro_mapping, InputEvent(EV_KEY, 2, 0), None)

        loop.run_until_complete(asyncio.sleep(keystroke_sleep * 10 / 1000))

        self.assertFalse(active_macros[1].holding)
        self.assertFalse(active_macros[1].running)
        self.assertFalse(active_macros[2].holding)
        self.assertFalse(active_macros[2].running)

        events = self.calculate_event_number(sleeptime, 1, 1) * 2

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


if __name__ == "__main__":
    unittest.main()
