#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2024 sezanzeb <b8x45ygc9@mozmail.com>
#
# This file is part of input-remapper.
#
# input-remapper is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# input-remapper is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with input-remapper.  If not, see <https://www.gnu.org/licenses/>.


import asyncio
import time
import unittest

from evdev.ecodes import (
    EV_REL,
    EV_KEY,
    REL_Y,
    REL_HWHEEL,
    REL_HWHEEL_HI_RES,
    KEY_A,
    KEY_B,
    KEY_C,
    KEY_E,
)

from inputremapper.configs.keyboard_layout import keyboard_layout
from inputremapper.configs.validation_errors import (
    MacroError,
)
from inputremapper.injection.macros.macro import Macro, macro_variables
from inputremapper.injection.macros.parse import Parser
from tests.lib.test_setup import test_setup
from tests.unit.test_macros.macro_test_base import MacroTestBase, DummyMapping


@test_setup
class TestMacros(MacroTestBase):
    async def test_run_plus_syntax(self):
        macro = Parser.parse("a + b + c + d", self.context, DummyMapping)

        macro.press_trigger()
        asyncio.ensure_future(macro.run(self.handler))
        await asyncio.sleep(0.2)
        self.assertTrue(macro.tasks[0].is_holding())

        # starting from the left, presses each one down
        self.assertEqual(self.result[0], (EV_KEY, keyboard_layout.get("a"), 1))
        self.assertEqual(self.result[1], (EV_KEY, keyboard_layout.get("b"), 1))
        self.assertEqual(self.result[2], (EV_KEY, keyboard_layout.get("c"), 1))
        self.assertEqual(self.result[3], (EV_KEY, keyboard_layout.get("d"), 1))

        # and then releases starting with the previously pressed key
        macro.release_trigger()
        await asyncio.sleep(0.2)
        self.assertFalse(macro.tasks[0].is_holding())
        self.assertEqual(self.result[4], (EV_KEY, keyboard_layout.get("d"), 0))
        self.assertEqual(self.result[5], (EV_KEY, keyboard_layout.get("c"), 0))
        self.assertEqual(self.result[6], (EV_KEY, keyboard_layout.get("b"), 0))
        self.assertEqual(self.result[7], (EV_KEY, keyboard_layout.get("a"), 0))

    async def test_child_macro_count(self):
        # It correctly keeps track of child-macros for both positional and keyword-args
        macro = Parser.parse(
            "hold(macro=hold(hold())).repeat(1, macro=repeat(1, hold()))",
            self.context,
            DummyMapping,
            True,
        )
        self.assertEqual(self.count_child_macros(macro), 4)
        self.assertEqual(self.count_tasks(macro), 6)

    async def test_0(self):
        macro = Parser.parse("key(1)", self.context, DummyMapping, True)
        one_code = keyboard_layout.get("1")

        await macro.run(self.handler)
        self.assertListEqual(
            self.result,
            [(EV_KEY, one_code, 1), (EV_KEY, one_code, 0)],
        )
        self.assertEqual(self.count_child_macros(macro), 0)

    async def test_named_parameter(self):
        macro = Parser.parse("key(symbol=1)", self.context, DummyMapping, True)
        one_code = keyboard_layout.get("1")

        await macro.run(self.handler)
        self.assertListEqual(
            self.result,
            [(EV_KEY, one_code, 1), (EV_KEY, one_code, 0)],
        )
        self.assertEqual(self.count_child_macros(macro), 0)

    async def test_1(self):
        macro = Parser.parse('key(1).key("KEY_A").key(3)', self.context, DummyMapping)

        await macro.run(self.handler)
        self.assertListEqual(
            self.result,
            [
                (EV_KEY, keyboard_layout.get("1"), 1),
                (EV_KEY, keyboard_layout.get("1"), 0),
                (EV_KEY, keyboard_layout.get("a"), 1),
                (EV_KEY, keyboard_layout.get("a"), 0),
                (EV_KEY, keyboard_layout.get("3"), 1),
                (EV_KEY, keyboard_layout.get("3"), 0),
            ],
        )
        self.assertEqual(self.count_child_macros(macro), 0)

    async def test_key(self):
        code_a = keyboard_layout.get("a")
        code_b = keyboard_layout.get("b")
        macro = Parser.parse("set(foo, b).key($foo).key(a)", self.context, DummyMapping)
        await macro.run(self.handler)
        self.assertListEqual(
            self.result,
            [
                (EV_KEY, code_b, 1),
                (EV_KEY, code_b, 0),
                (EV_KEY, code_a, 1),
                (EV_KEY, code_a, 0),
            ],
        )

    async def test_key_down_up(self):
        code_a = keyboard_layout.get("a")
        code_b = keyboard_layout.get("b")
        macro = Parser.parse(
            "set(foo, b).key_down($foo).key_up($foo).key_up(a).key_down(a)",
            self.context,
            DummyMapping,
        )
        await macro.run(self.handler)
        self.assertListEqual(
            self.result,
            [
                (EV_KEY, code_b, 1),
                (EV_KEY, code_b, 0),
                (EV_KEY, code_a, 0),
                (EV_KEY, code_a, 1),
            ],
        )

    async def test_modify(self):
        code_a = keyboard_layout.get("a")
        code_b = keyboard_layout.get("b")
        code_c = keyboard_layout.get("c")
        macro = Parser.parse(
            "set(foo, b).modify($foo, modify(a, key(c)))",
            self.context,
            DummyMapping,
        )
        await macro.run(self.handler)
        self.assertListEqual(
            self.result,
            [
                (EV_KEY, code_b, 1),
                (EV_KEY, code_a, 1),
                (EV_KEY, code_c, 1),
                (EV_KEY, code_c, 0),
                (EV_KEY, code_a, 0),
                (EV_KEY, code_b, 0),
            ],
        )

    async def test_hold_variable(self):
        code_a = keyboard_layout.get("a")
        macro = Parser.parse("set(foo, a).hold($foo)", self.context, DummyMapping)
        await macro.run(self.handler)
        self.assertListEqual(
            self.result,
            [
                (EV_KEY, code_a, 1),
                (EV_KEY, code_a, 0),
            ],
        )

    async def test_hold_keys(self):
        macro = Parser.parse(
            "set(foo, b).hold_keys(a, $foo, c)", self.context, DummyMapping
        )
        # press first
        macro.press_trigger()
        # then run, just like how it is going to happen during runtime
        asyncio.ensure_future(macro.run(self.handler))

        code_a = keyboard_layout.get("a")
        code_b = keyboard_layout.get("b")
        code_c = keyboard_layout.get("c")

        await asyncio.sleep(0.2)
        self.assertListEqual(
            self.result,
            [
                (EV_KEY, code_a, 1),
                (EV_KEY, code_b, 1),
                (EV_KEY, code_c, 1),
            ],
        )

        macro.release_trigger()

        await asyncio.sleep(0.2)
        self.assertListEqual(
            self.result,
            [
                (EV_KEY, code_a, 1),
                (EV_KEY, code_b, 1),
                (EV_KEY, code_c, 1),
                (EV_KEY, code_c, 0),
                (EV_KEY, code_b, 0),
                (EV_KEY, code_a, 0),
            ],
        )

    async def test_hold_keys_broken(self):
        # Won't run any of the keys when one of them is invalid
        macro = Parser.parse(
            "set(foo, broken).hold_keys(a, $foo, c)", self.context, DummyMapping
        )
        # press first
        macro.press_trigger()
        # then run, just like how it is going to happen during runtime
        asyncio.ensure_future(macro.run(self.handler))
        await asyncio.sleep(0.2)
        self.assertListEqual(self.result, [])
        macro.release_trigger()
        await asyncio.sleep(0.2)
        self.assertListEqual(self.result, [])

    async def test_hold(self):
        # repeats key(a) as long as the key is held down
        macro = Parser.parse("key(1).hold(key(a)).key(3)", self.context, DummyMapping)

        """down"""

        macro.press_trigger()
        await asyncio.sleep(0.05)
        self.assertTrue(macro.tasks[1].is_holding())

        macro.press_trigger()  # redundantly calling doesn't break anything
        asyncio.ensure_future(macro.run(self.handler))
        await asyncio.sleep(0.2)
        self.assertTrue(macro.tasks[1].is_holding())
        self.assertGreater(len(self.result), 2)

        """up"""

        macro.release_trigger()
        await asyncio.sleep(0.05)
        self.assertFalse(macro.tasks[1].is_holding())

        self.assertEqual(self.result[0], (EV_KEY, keyboard_layout.get("1"), 1))
        self.assertEqual(self.result[-1], (EV_KEY, keyboard_layout.get("3"), 0))

        code_a = keyboard_layout.get("a")
        self.assertGreater(self.result.count((EV_KEY, code_a, 1)), 2)

        self.assertEqual(self.count_child_macros(macro), 1)
        self.assertEqual(self.count_tasks(macro), 4)

    async def test_hold_failing_child(self):
        # if a child macro fails, hold will not try to run it again.
        # The exception is properly propagated through both `hold`s and the macro
        # stops. If the code is broken, this test might enter an infinite loop.
        macro = Parser.parse("hold(hold(key(a)))", self.context, DummyMapping)

        class MyException(Exception):
            pass

        def f(*_):
            raise MyException("foo")

        macro.press_trigger()
        with self.assertRaises(MyException):
            await macro.run(f)

        await asyncio.sleep(0.1)
        self.assertFalse(macro.running)

    async def test_dont_hold(self):
        macro = Parser.parse("key(1).hold(key(a)).key(3)", self.context, DummyMapping)

        asyncio.ensure_future(macro.run(self.handler))
        await asyncio.sleep(0.2)
        self.assertFalse(macro.tasks[1].is_holding())
        # press_trigger was never called, so the macro completes right away
        # and the child macro of hold is never called.
        self.assertEqual(len(self.result), 4)

        self.assertEqual(self.result[0], (EV_KEY, keyboard_layout.get("1"), 1))
        self.assertEqual(self.result[-1], (EV_KEY, keyboard_layout.get("3"), 0))

        self.assertEqual(self.count_child_macros(macro), 1)
        self.assertEqual(self.count_tasks(macro), 4)

    async def test_just_hold(self):
        macro = Parser.parse("key(1).hold().key(3)", self.context, DummyMapping)

        """down"""

        macro.press_trigger()
        asyncio.ensure_future(macro.run(self.handler))
        await asyncio.sleep(0.1)
        self.assertTrue(macro.tasks[1].is_holding())
        self.assertEqual(len(self.result), 2)
        await asyncio.sleep(0.1)
        # doesn't do fancy stuff, is blocking until the release
        self.assertEqual(len(self.result), 2)

        """up"""

        macro.release_trigger()
        await asyncio.sleep(0.05)
        self.assertFalse(macro.tasks[1].is_holding())
        self.assertEqual(len(self.result), 4)

        self.assertEqual(self.result[0], (EV_KEY, keyboard_layout.get("1"), 1))
        self.assertEqual(self.result[-1], (EV_KEY, keyboard_layout.get("3"), 0))

        self.assertEqual(self.count_child_macros(macro), 0)
        self.assertEqual(self.count_tasks(macro), 3)

    async def test_dont_just_hold(self):
        macro = Parser.parse("key(1).hold().key(3)", self.context, DummyMapping)

        asyncio.ensure_future(macro.run(self.handler))
        await asyncio.sleep(0.1)
        self.assertFalse(macro.tasks[1].is_holding())
        # since press_trigger was never called it just does the macro
        # completely
        self.assertEqual(len(self.result), 4)

        self.assertEqual(self.result[0], (EV_KEY, keyboard_layout.get("1"), 1))
        self.assertEqual(self.result[-1], (EV_KEY, keyboard_layout.get("3"), 0))

        self.assertEqual(self.count_child_macros(macro), 0)

    async def test_hold_down(self):
        # writes down and waits for the up event until the key is released
        macro = Parser.parse("hold(a)", self.context, DummyMapping)
        self.assertEqual(self.count_child_macros(macro), 0)

        """down"""

        macro.press_trigger()
        await asyncio.sleep(0.05)
        self.assertTrue(macro.tasks[0].is_holding())

        asyncio.ensure_future(macro.run(self.handler))
        macro.press_trigger()  # redundantly calling doesn't break anything
        await asyncio.sleep(0.2)
        self.assertTrue(macro.tasks[0].is_holding())
        self.assertEqual(len(self.result), 1)
        self.assertEqual(self.result[0], (EV_KEY, keyboard_layout.get("a"), 1))

        """up"""

        macro.release_trigger()
        await asyncio.sleep(0.05)
        self.assertFalse(macro.tasks[0].is_holding())

        self.assertEqual(len(self.result), 2)
        self.assertEqual(self.result[0], (EV_KEY, keyboard_layout.get("a"), 1))
        self.assertEqual(self.result[1], (EV_KEY, keyboard_layout.get("a"), 0))

    async def test_aldjfakl(self):
        repeats = 5

        macro = Parser.parse(
            f"repeat({repeats}, key(k))",
            self.context,
            DummyMapping,
        )

        self.assertEqual(self.count_child_macros(macro), 1)

    async def test_2(self):
        start = time.time()
        repeats = 20

        macro = Parser.parse(
            f"repeat({repeats}, key(k)).repeat(1, key(k))",
            self.context,
            DummyMapping,
        )
        k_code = keyboard_layout.get("k")

        await macro.run(self.handler)
        keystroke_sleep = DummyMapping.macro_key_sleep_ms
        sleep_time = 2 * repeats * keystroke_sleep / 1000
        self.assertGreater(time.time() - start, sleep_time * 0.9)
        self.assertLess(time.time() - start, sleep_time * 1.3)

        self.assertListEqual(
            self.result,
            [(EV_KEY, k_code, 1), (EV_KEY, k_code, 0)] * (repeats + 1),
        )

        self.assertEqual(self.count_child_macros(macro), 2)

        self.assertEqual(len(macro.tasks[0].child_macros), 1)
        self.assertEqual(len(macro.tasks[0].child_macros[0].tasks), 1)
        self.assertEqual(len(macro.tasks[0].child_macros[0].tasks[0].child_macros), 0)

        self.assertEqual(len(macro.tasks[1].child_macros), 1)
        self.assertEqual(len(macro.tasks[1].child_macros[0].tasks), 1)
        self.assertEqual(len(macro.tasks[1].child_macros[0].tasks[0].child_macros), 0)

    async def test_3(self):
        start = time.time()
        macro = Parser.parse("repeat(3, key(m).w(100))", self.context, DummyMapping)
        m_code = keyboard_layout.get("m")
        await macro.run(self.handler)

        keystroke_time = 6 * DummyMapping.macro_key_sleep_ms
        total_time = keystroke_time + 300
        total_time /= 1000

        self.assertGreater(time.time() - start, total_time * 0.9)
        self.assertLess(time.time() - start, total_time * 1.2)
        self.assertListEqual(
            self.result,
            [
                (EV_KEY, m_code, 1),
                (EV_KEY, m_code, 0),
                (EV_KEY, m_code, 1),
                (EV_KEY, m_code, 0),
                (EV_KEY, m_code, 1),
                (EV_KEY, m_code, 0),
            ],
        )
        self.assertEqual(self.count_child_macros(macro), 1)
        self.assertEqual(len(macro.tasks), 1)
        self.assertEqual(len(macro.tasks[0].child_macros), 1)
        self.assertEqual(len(macro.tasks[0].child_macros[0].tasks), 2)
        self.assertEqual(len(macro.tasks[0].child_macros[0].tasks[0].child_macros), 0)
        self.assertEqual(len(macro.tasks[0].child_macros[0].tasks[1].child_macros), 0)

    async def test_4(self):
        macro = Parser.parse(
            "  repeat(2,\nkey(\nr ).key(minus\n )).key(m)  ",
            self.context,
            DummyMapping,
        )

        r = keyboard_layout.get("r")
        minus = keyboard_layout.get("minus")
        m = keyboard_layout.get("m")

        await macro.run(self.handler)
        self.assertListEqual(
            self.result,
            [
                (EV_KEY, r, 1),
                (EV_KEY, r, 0),
                (EV_KEY, minus, 1),
                (EV_KEY, minus, 0),
                (EV_KEY, r, 1),
                (EV_KEY, r, 0),
                (EV_KEY, minus, 1),
                (EV_KEY, minus, 0),
                (EV_KEY, m, 1),
                (EV_KEY, m, 0),
            ],
        )
        self.assertEqual(self.count_child_macros(macro), 1)
        self.assertEqual(self.count_tasks(macro), 4)

    async def test_5(self):
        start = time.time()
        macro = Parser.parse(
            "w(200).repeat(2,modify(w,\nrepeat(2,\tkey(BtN_LeFt))).w(10).key(k))",
            self.context,
            DummyMapping,
        )

        self.assertEqual(self.count_child_macros(macro), 3)
        self.assertEqual(self.count_tasks(macro), 7)

        w = keyboard_layout.get("w")
        left = keyboard_layout.get("bTn_lEfT")
        k = keyboard_layout.get("k")

        await macro.run(self.handler)

        num_pauses = 8 + 6 + 4
        keystroke_time = num_pauses * DummyMapping.macro_key_sleep_ms
        wait_time = 220
        total_time = (keystroke_time + wait_time) / 1000

        self.assertLess(time.time() - start, total_time * 1.2)
        self.assertGreater(time.time() - start, total_time * 0.9)
        expected = [(EV_KEY, w, 1)]
        expected += [(EV_KEY, left, 1), (EV_KEY, left, 0)] * 2
        expected += [(EV_KEY, w, 0)]
        expected += [(EV_KEY, k, 1), (EV_KEY, k, 0)]
        expected *= 2
        self.assertListEqual(self.result, expected)

    async def test_6(self):
        # does nothing without .run
        macro = Parser.parse("key(a).repeat(3, key(b))", self.context)
        self.assertIsInstance(macro, Macro)
        self.assertListEqual(self.result, [])

    async def test_duplicate_run(self):
        # it won't restart the macro, because that may screw up the
        # internal state (in particular the _trigger_release_event).
        # I actually don't know at all what kind of bugs that might produce,
        # lets just avoid it. It might cause it to be held down forever.
        a = keyboard_layout.get("a")
        b = keyboard_layout.get("b")
        c = keyboard_layout.get("c")

        macro = Parser.parse(
            "key(a).modify(b, hold()).key(c)", self.context, DummyMapping
        )
        asyncio.ensure_future(macro.run(self.handler))
        self.assertFalse(macro.tasks[1].child_macros[0].tasks[0].is_holding())

        asyncio.ensure_future(macro.run(self.handler))  # ignored
        self.assertFalse(macro.tasks[1].child_macros[0].tasks[0].is_holding())

        macro.press_trigger()
        await asyncio.sleep(0.2)
        self.assertTrue(macro.tasks[1].child_macros[0].tasks[0].is_holding())

        asyncio.ensure_future(macro.run(self.handler))  # ignored
        self.assertTrue(macro.tasks[1].child_macros[0].tasks[0].is_holding())

        macro.release_trigger()
        await asyncio.sleep(0.2)
        self.assertFalse(macro.tasks[1].child_macros[0].tasks[0].is_holding())

        expected = [
            (EV_KEY, a, 1),
            (EV_KEY, a, 0),
            (EV_KEY, b, 1),
            (EV_KEY, b, 0),
            (EV_KEY, c, 1),
            (EV_KEY, c, 0),
        ]
        self.assertListEqual(self.result, expected)

        """not ignored, since previous run is over"""

        asyncio.ensure_future(macro.run(self.handler))
        macro.press_trigger()
        await asyncio.sleep(0.2)
        self.assertTrue(macro.tasks[1].child_macros[0].tasks[0].is_holding())
        macro.release_trigger()
        await asyncio.sleep(0.2)
        self.assertFalse(macro.tasks[1].child_macros[0].tasks[0].is_holding())

        expected = [
            (EV_KEY, a, 1),
            (EV_KEY, a, 0),
            (EV_KEY, b, 1),
            (EV_KEY, b, 0),
            (EV_KEY, c, 1),
            (EV_KEY, c, 0),
        ] * 2
        self.assertListEqual(self.result, expected)

    async def test_mouse(self):
        wheel_speed = 60
        macro_1 = Parser.parse("mouse(up, 4)", self.context, DummyMapping)
        macro_2 = Parser.parse(
            f"wheel(left, {wheel_speed})", self.context, DummyMapping
        )
        macro_1.press_trigger()
        macro_2.press_trigger()
        asyncio.ensure_future(macro_1.run(self.handler))
        asyncio.ensure_future(macro_2.run(self.handler))

        sleep = 0.1
        await asyncio.sleep(sleep)
        self.assertTrue(macro_1.tasks[0].is_holding())
        self.assertTrue(macro_2.tasks[0].is_holding())
        macro_1.release_trigger()
        macro_2.release_trigger()

        self.assertIn((EV_REL, REL_Y, -4), self.result)
        expected_wheel_hi_res_event_count = sleep * DummyMapping.rel_rate
        expected_wheel_event_count = int(
            expected_wheel_hi_res_event_count / 120 * wheel_speed
        )
        actual_wheel_event_count = self.result.count((EV_REL, REL_HWHEEL, 1))
        actual_wheel_hi_res_event_count = self.result.count(
            (
                EV_REL,
                REL_HWHEEL_HI_RES,
                wheel_speed,
            )
        )
        # this seems to have a tendency of injecting less wheel events,
        # especially if the sleep is short
        self.assertGreater(actual_wheel_event_count, expected_wheel_event_count * 0.8)
        self.assertLess(actual_wheel_event_count, expected_wheel_event_count * 1.1)
        self.assertGreater(
            actual_wheel_hi_res_event_count, expected_wheel_hi_res_event_count * 0.8
        )
        self.assertLess(
            actual_wheel_hi_res_event_count, expected_wheel_hi_res_event_count * 1.1
        )

    async def test_mouse_accel(self):
        macro_1 = Parser.parse("mouse(up, 10, 0.9)", self.context, DummyMapping)
        macro_1.press_trigger()
        asyncio.ensure_future(macro_1.run(self.handler))

        sleep = 0.1
        await asyncio.sleep(sleep)
        self.assertTrue(macro_1.tasks[0].is_holding())
        macro_1.release_trigger()
        self.assertEqual(
            [(2, 1, 0), (2, 1, -2), (2, 1, -3), (2, 1, -4), (2, 1, -4), (2, 1, -5)],
            self.result,
        )

    async def test_event_1(self):
        macro = Parser.parse("e(EV_KEY, KEY_A, 1)", self.context, DummyMapping)
        a_code = keyboard_layout.get("a")

        await macro.run(self.handler)
        self.assertListEqual(self.result, [(EV_KEY, a_code, 1)])
        self.assertEqual(self.count_child_macros(macro), 0)

    async def test_event_2(self):
        macro = Parser.parse(
            "repeat(1, event(type=5421, code=324, value=154))",
            self.context,
            DummyMapping,
        )
        code = 324

        await macro.run(self.handler)
        self.assertListEqual(self.result, [(5421, code, 154)])
        self.assertEqual(self.count_child_macros(macro), 1)

    async def test_macro_breaks(self):
        # the first parameter for `repeat` requires an integer, not "foo",
        # which makes `repeat` throw
        macro = Parser.parse(
            'set(a, "foo").repeat($a, key(KEY_A)).key(KEY_B)',
            self.context,
            DummyMapping,
        )

        try:
            await macro.run(self.handler)
        except MacroError as e:
            self.assertIn("foo", str(e))

        self.assertFalse(macro.running)

        # key(KEY_B) is not executed, the macro stops
        self.assertListEqual(self.result, [])

    async def test_set(self):
        """await Parser.parse('set(a, "foo")', self.context, DummyMapping).run(self.handler)
        self.assertEqual(macro_variables.get("a"), "foo")

        await Parser.parse('set( \t"b" \n, "1")', self.context, DummyMapping).run(self.handler)
        self.assertEqual(macro_variables.get("b"), "1")"""

        await Parser.parse("set(a, 1)", self.context, DummyMapping).run(self.handler)
        self.assertEqual(macro_variables.get("a"), 1)

        """await Parser.parse("set(a, )", self.context, DummyMapping).run(self.handler)
        self.assertEqual(macro_variables.get("a"), None)"""

    async def test_add(self):
        await Parser.parse("set(a, 1).add(a, 1)", self.context, DummyMapping).run(
            self.handler
        )
        self.assertEqual(macro_variables.get("a"), 2)

        await Parser.parse("set(b, 1).add(b, -1)", self.context, DummyMapping).run(
            self.handler
        )
        self.assertEqual(macro_variables.get("b"), 0)

        await Parser.parse("set(c, -1).add(c, 500)", self.context, DummyMapping).run(
            self.handler
        )
        self.assertEqual(macro_variables.get("c"), 499)

        await Parser.parse("add(d, 500)", self.context, DummyMapping).run(self.handler)
        self.assertEqual(macro_variables.get("d"), 500)

    async def test_add_invalid(self):
        # For invalid input it should do nothing (except to log to the console)
        await Parser.parse('set(e, "foo").add(e, 1)', self.context, DummyMapping).run(
            self.handler
        )
        self.assertEqual(macro_variables.get("e"), "foo")

        await Parser.parse('set(e, "2").add(e, 3)', self.context, DummyMapping).run(
            self.handler
        )
        self.assertEqual(macro_variables.get("e"), "2")

    async def test_multiline_macro_and_comments(self):
        # the parser is not confused by the code in the comments and can use hashtags
        # in strings in the actual code
        comment = '# repeat(1,key(KEY_D)).set(a,"#b")'
        macro = Parser.parse(
            f"""
            {comment}
            key(KEY_A).{comment}
            key(KEY_B). {comment}
            repeat({comment}
                1, {comment}
                key(KEY_C){comment}
            ). {comment}
            {comment}
            set(a, "#").{comment}
            if_eq($a, "#", key(KEY_E), key(KEY_F)) {comment}
            {comment}
        """,
            self.context,
            DummyMapping,
        )
        await macro.run(self.handler)
        self.assertListEqual(
            self.result,
            [
                (EV_KEY, KEY_A, 1),
                (EV_KEY, KEY_A, 0),
                (EV_KEY, KEY_B, 1),
                (EV_KEY, KEY_B, 0),
                (EV_KEY, KEY_C, 1),
                (EV_KEY, KEY_C, 0),
                (EV_KEY, KEY_E, 1),
                (EV_KEY, KEY_E, 0),
            ],
        )


if __name__ == "__main__":
    unittest.main()
