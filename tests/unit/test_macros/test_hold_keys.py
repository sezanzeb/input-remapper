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


import asyncio
import unittest

from evdev.ecodes import EV_KEY

from inputremapper.configs.keyboard_layout import keyboard_layout
from inputremapper.configs.validation_errors import MacroError
from inputremapper.injection.macros.parse import Parser
from tests.lib.test_setup import test_setup
from tests.unit.test_macros.macro_test_base import MacroTestBase, DummyMapping


@test_setup
class TestHoldKeys(MacroTestBase):
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

    async def test_aldjfakl(self):
        repeats = 5

        macro = Parser.parse(
            f"repeat({repeats}, key(k))",
            self.context,
            DummyMapping,
        )

        self.assertEqual(self.count_child_macros(macro), 1)

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

    async def test_raises_error(self):
        self.assertRaises(
            MacroError, Parser.parse, "hold_keys(a, broken, b)", self.context
        )


if __name__ == "__main__":
    unittest.main()
