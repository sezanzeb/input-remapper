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
    ABS_Y,
)

from inputremapper.configs.keyboard_layout import keyboard_layout
from inputremapper.configs.validation_errors import MacroError
from inputremapper.injection.macros.parse import Parser
from inputremapper.input_event import InputEvent
from tests.lib.test_setup import test_setup
from tests.unit.test_macros.macro_test_base import DummyMapping, MacroTestBase


@test_setup
class TestIfSingle(MacroTestBase):
    async def test_if_single(self):
        macro = Parser.parse("if_single(key(x), key(y))", self.context, DummyMapping)
        self.assertEqual(self.count_child_macros(macro), 2)

        a = keyboard_layout.get("a")
        x = keyboard_layout.get("x")

        await self.trigger_sequence(macro, InputEvent.key(a, 1))
        await asyncio.sleep(0.1)
        await self.release_sequence(macro, InputEvent.key(a, 0))
        # the key that triggered the macro is released
        await asyncio.sleep(0.1)

        self.assertListEqual(self.result, [(EV_KEY, x, 1), (EV_KEY, x, 0)])
        self.assertFalse(macro.running)

    async def test_if_single_ignores_releases(self):
        # the timeout won't break the macro, everything happens well within that
        # timeframe.
        macro = Parser.parse(
            "if_single(key(x), else=key(y), timeout=100000)",
            self.context,
            DummyMapping,
        )
        self.assertEqual(self.count_child_macros(macro), 2)

        a = keyboard_layout.get("a")
        b = keyboard_layout.get("b")

        x = keyboard_layout.get("x")
        y = keyboard_layout.get("y")

        # pressing the macro key
        await self.trigger_sequence(macro, InputEvent.key(a, 1))
        await asyncio.sleep(0.05)

        # if_single only looks out for newly pressed keys,
        # it doesn't care if keys were released that have been
        # pressed before if_single. This was decided because it is a lot
        # less tricky and more fluently to use if you type fast
        for listener in self.context.listeners:
            asyncio.ensure_future(listener(InputEvent.key(b, 0)))
        await asyncio.sleep(0.05)
        self.assertListEqual(self.result, [])

        # releasing the actual key triggers if_single
        await asyncio.sleep(0.05)
        await self.release_sequence(macro, InputEvent.key(a, 0))
        await asyncio.sleep(0.05)
        self.assertListEqual(self.result, [(EV_KEY, x, 1), (EV_KEY, x, 0)])
        self.assertFalse(macro.running)

    async def test_if_not_single(self):
        # Will run the `else` macro if another key is pressed.
        # Also works if if_single is a child macro, i.e. the event is passed to it
        # from the outside macro correctly.
        macro = Parser.parse(
            "repeat(1, if_single(then=key(x), else=key(y)))",
            self.context,
            DummyMapping,
        )
        self.assertEqual(self.count_child_macros(macro), 3)
        self.assertEqual(self.count_tasks(macro), 4)

        a = keyboard_layout.get("a")
        b = keyboard_layout.get("b")

        x = keyboard_layout.get("x")
        y = keyboard_layout.get("y")

        # press the trigger key
        await self.trigger_sequence(macro, InputEvent.key(a, 1))
        await asyncio.sleep(0.1)
        # press another key
        for listener in self.context.listeners:
            asyncio.ensure_future(listener(InputEvent.key(b, 1)))
        await asyncio.sleep(0.1)

        self.assertListEqual(self.result, [(EV_KEY, y, 1), (EV_KEY, y, 0)])
        self.assertFalse(macro.running)

    async def test_if_not_single_none(self):
        macro = Parser.parse("if_single(key(x),)", self.context, DummyMapping)
        self.assertEqual(self.count_child_macros(macro), 1)

        a = keyboard_layout.get("a")
        b = keyboard_layout.get("b")

        x = keyboard_layout.get("x")

        # press trigger key
        await self.trigger_sequence(macro, InputEvent.key(a, 1))
        await asyncio.sleep(0.1)
        # press another key
        for listener in self.context.listeners:
            asyncio.ensure_future(listener(InputEvent.key(b, 1)))
        await asyncio.sleep(0.1)

        self.assertListEqual(self.result, [])
        self.assertFalse(macro.running)

    async def test_if_single_times_out(self):
        macro = Parser.parse(
            "set(t, 300).if_single(key(x), key(y), timeout=$t)",
            self.context,
            DummyMapping,
        )
        self.assertEqual(self.count_child_macros(macro), 2)

        a = keyboard_layout.get("a")
        y = keyboard_layout.get("y")

        await self.trigger_sequence(macro, InputEvent.key(a, 1))

        # no timeout yet
        await asyncio.sleep(0.2)
        self.assertListEqual(self.result, [])
        self.assertTrue(macro.running)

        # times out now
        await asyncio.sleep(0.2)
        self.assertListEqual(self.result, [(EV_KEY, y, 1), (EV_KEY, y, 0)])
        self.assertFalse(macro.running)

    async def test_if_single_ignores_joystick(self):
        """Triggers else + delayed_handle_keycode."""
        # Integration test style for if_single.
        # If a joystick that is mapped to a button is moved, if_single stops
        macro = Parser.parse(
            "if_single(k(a), k(KEY_LEFTSHIFT))", self.context, DummyMapping
        )
        code_shift = keyboard_layout.get("KEY_LEFTSHIFT")
        code_a = keyboard_layout.get("a")
        trigger = 1

        await self.trigger_sequence(macro, InputEvent.key(trigger, 1))
        await asyncio.sleep(0.1)
        for listener in self.context.listeners:
            asyncio.ensure_future(listener(InputEvent.abs(ABS_Y, 10)))
        await asyncio.sleep(0.1)
        await self.release_sequence(macro, InputEvent.key(trigger, 0))
        await asyncio.sleep(0.1)
        self.assertFalse(macro.running)
        self.assertListEqual(self.result, [(EV_KEY, code_a, 1), (EV_KEY, code_a, 0)])

    async def test_raises_error(self):
        Parser.parse("if_single(k(a),)", self.context)  # no error
        self.assertRaises(MacroError, Parser.parse, "if_single(1,)", self.context)
        self.assertRaises(MacroError, Parser.parse, "if_single(,1)", self.context)


if __name__ == "__main__":
    unittest.main()
