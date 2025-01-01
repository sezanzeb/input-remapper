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
import unittest

from evdev.ecodes import EV_KEY

from inputremapper.configs.keyboard_layout import keyboard_layout
from inputremapper.injection.macros.parse import Parser
from tests.lib.test_setup import test_setup
from tests.unit.test_macros.macro_test_base import MacroTestBase, DummyMapping


@test_setup
class TestHold(MacroTestBase):
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


if __name__ == "__main__":
    unittest.main()
