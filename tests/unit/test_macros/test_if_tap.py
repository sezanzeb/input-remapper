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

from evdev.ecodes import (
    EV_KEY,
    KEY_A,
    KEY_B,
)

from inputremapper.configs.keyboard_layout import keyboard_layout
from inputremapper.configs.validation_errors import MacroError
from inputremapper.injection.macros.parse import Parser
from tests.lib.test_setup import test_setup
from tests.unit.test_macros.macro_test_base import DummyMapping, MacroTestBase


@test_setup
class TestIfTap(MacroTestBase):
    async def test_if_tap(self):
        macro = Parser.parse("if_tap(key(x), key(y), 100)", self.context, DummyMapping)
        self.assertEqual(self.count_child_macros(macro), 2)

        x = keyboard_layout.get("x")
        y = keyboard_layout.get("y")

        # this is the regular routine of how a macro is started. the tigger is pressed
        # already when the macro runs, and released during if_tap within the timeout.
        macro.press_trigger()
        asyncio.ensure_future(macro.run(self.handler))
        await asyncio.sleep(0.05)
        macro.release_trigger()
        await asyncio.sleep(0.05)

        self.assertListEqual(self.result, [(EV_KEY, x, 1), (EV_KEY, x, 0)])
        self.assertFalse(macro.running)

    async def test_if_tap_2(self):
        # when the press arrives shortly after run.
        # a tap will happen within the timeout even if the tigger is not pressed when
        # it does into if_tap
        macro = Parser.parse("if_tap(key(a), key(b), 100)", self.context, DummyMapping)
        asyncio.ensure_future(macro.run(self.handler))

        await asyncio.sleep(0.01)
        macro.press_trigger()
        await asyncio.sleep(0.01)
        macro.release_trigger()
        await asyncio.sleep(0.2)
        self.assertListEqual(self.result, [(EV_KEY, KEY_A, 1), (EV_KEY, KEY_A, 0)])
        self.assertFalse(macro.running)
        self.result.clear()

    async def test_if_double_tap(self):
        macro = Parser.parse(
            "if_tap(if_tap(key(a), key(b), 100), key(c), 100)",
            self.context,
            DummyMapping,
        )
        self.assertEqual(self.count_child_macros(macro), 4)
        self.assertEqual(self.count_tasks(macro), 5)

        asyncio.ensure_future(macro.run(self.handler))

        # first tap
        macro.press_trigger()
        await asyncio.sleep(0.05)
        macro.release_trigger()

        # second tap
        await asyncio.sleep(0.04)
        macro.press_trigger()
        await asyncio.sleep(0.04)
        macro.release_trigger()

        await asyncio.sleep(0.05)
        self.assertListEqual(self.result, [(EV_KEY, KEY_A, 1), (EV_KEY, KEY_A, 0)])
        self.assertFalse(macro.running)
        self.result.clear()

        """If the second tap takes too long, runs else there"""

        asyncio.ensure_future(macro.run(self.handler))

        # first tap
        macro.press_trigger()
        await asyncio.sleep(0.05)
        macro.release_trigger()

        # second tap
        await asyncio.sleep(0.06)
        macro.press_trigger()
        await asyncio.sleep(0.06)
        macro.release_trigger()

        await asyncio.sleep(0.05)
        self.assertListEqual(self.result, [(EV_KEY, KEY_B, 1), (EV_KEY, KEY_B, 0)])
        self.assertFalse(macro.running)
        self.result.clear()

    async def test_if_tap_none(self):
        # first param none
        macro = Parser.parse("if_tap(, key(y), 100)", self.context, DummyMapping)
        self.assertEqual(self.count_child_macros(macro), 1)
        y = keyboard_layout.get("y")
        macro.press_trigger()
        asyncio.ensure_future(macro.run(self.handler))
        await asyncio.sleep(0.05)
        macro.release_trigger()
        await asyncio.sleep(0.05)
        self.assertListEqual(self.result, [])

        # second param none
        macro = Parser.parse("if_tap(key(y), , 50)", self.context, DummyMapping)
        self.assertEqual(self.count_child_macros(macro), 1)
        y = keyboard_layout.get("y")
        macro.press_trigger()
        asyncio.ensure_future(macro.run(self.handler))
        await asyncio.sleep(0.1)
        macro.release_trigger()
        await asyncio.sleep(0.05)
        self.assertListEqual(self.result, [])

        self.assertFalse(macro.running)

    async def test_if_not_tap(self):
        macro = Parser.parse("if_tap(key(x), key(y), 50)", self.context, DummyMapping)
        self.assertEqual(self.count_child_macros(macro), 2)

        y = keyboard_layout.get("y")

        macro.press_trigger()
        asyncio.ensure_future(macro.run(self.handler))
        await asyncio.sleep(0.1)
        macro.release_trigger()
        await asyncio.sleep(0.05)

        self.assertListEqual(self.result, [(EV_KEY, y, 1), (EV_KEY, y, 0)])
        self.assertFalse(macro.running)

    async def test_if_not_tap_named(self):
        macro = Parser.parse(
            "if_tap(key(x), key(y), timeout=50)", self.context, DummyMapping
        )
        self.assertEqual(self.count_child_macros(macro), 2)

        x = keyboard_layout.get("x")
        y = keyboard_layout.get("y")

        macro.press_trigger()
        asyncio.ensure_future(macro.run(self.handler))
        await asyncio.sleep(0.1)
        macro.release_trigger()
        await asyncio.sleep(0.05)

        self.assertListEqual(self.result, [(EV_KEY, y, 1), (EV_KEY, y, 0)])
        self.assertFalse(macro.running)

    async def test_raises_error(self):
        Parser.parse("if_tap(, k(a), 1000)", self.context)  # no error
        Parser.parse("if_tap(, k(a), timeout=1000)", self.context)  # no error
        Parser.parse("if_tap(, k(a), $timeout)", self.context)  # no error
        Parser.parse("if_tap(, k(a), timeout=$t)", self.context)  # no error
        Parser.parse("if_tap(, key(a))", self.context)  # no error
        Parser.parse("if_tap(k(a),)", self.context)  # no error
        self.assertRaises(MacroError, Parser.parse, "if_tap(k(a), b)", self.context)


if __name__ == "__main__":
    unittest.main()
