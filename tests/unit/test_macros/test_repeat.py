#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2025 sezanzeb <b8x45ygc9@mozmail.com>
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
import time
import unittest

from evdev.ecodes import EV_KEY

from inputremapper.configs.keyboard_layout import keyboard_layout
from inputremapper.configs.validation_errors import MacroError
from inputremapper.injection.macros.parse import Parser
from tests.lib.test_setup import test_setup
from tests.unit.test_macros.macro_test_base import MacroTestBase, DummyMapping


@test_setup
class TestRepeat(MacroTestBase):
    async def test_1(self):
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

        # This test is rather lax, timing in github actions is slow
        self.assertLess(time.time() - start, sleep_time * 1.4)

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

    async def test_2(self):
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

    async def test_not_an_int(self):
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

    async def test_raises_error(self):
        self.assertRaises(MacroError, Parser.parse, "r(1)", self.context)
        self.assertRaises(MacroError, Parser.parse, "repeat(a, k(1))", self.context)
        Parser.parse("repeat($a, k(1))", self.context)  # no error
        Parser.parse("repeat(2, k(1))", self.context)  # no error
        self.assertRaises(MacroError, Parser.parse, 'repeat("2", k(1))', self.context)
        self.assertRaises(MacroError, Parser.parse, "r(1, 1)", self.context)
        self.assertRaises(MacroError, Parser.parse, "r(k(1), 1)", self.context)
        Parser.parse("r(1, macro=k(1))", self.context)  # no error
        self.assertRaises(MacroError, Parser.parse, "r(a=1, b=k(1))", self.context)
        self.assertRaises(
            MacroError,
            Parser.parse,
            "r(repeats=1, macro=k(1), a=2)",
            self.context,
        )
        self.assertRaises(
            MacroError,
            Parser.parse,
            "r(repeats=1, macro=k(1), repeats=2)",
            self.context,
        )


if __name__ == "__main__":
    unittest.main()
