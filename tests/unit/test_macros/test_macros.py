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
import time
import unittest

from evdev.ecodes import (
    EV_KEY,
)

from inputremapper.configs.keyboard_layout import keyboard_layout
from inputremapper.injection.macros.macro import Macro
from inputremapper.injection.macros.parse import Parser
from tests.lib.test_setup import test_setup
from tests.unit.test_macros.macro_test_base import MacroTestBase, DummyMapping


@test_setup
class TestMacros(MacroTestBase):
    async def test_newlines(self):
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

    async def test_various(self):
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

    async def test_not_run(self):
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


if __name__ == "__main__":
    unittest.main()
