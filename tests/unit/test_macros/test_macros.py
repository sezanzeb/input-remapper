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


if __name__ == "__main__":
    unittest.main()
