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

from evdev.ecodes import (
    EV_KEY,
    KEY_A,
    KEY_B,
    KEY_C,
    KEY_D,
)

from inputremapper.injection.macros.parse import Parser
from tests.lib.test_setup import test_setup
from tests.unit.test_macros.macro_test_base import DummyMapping, MacroTestBase


@test_setup
class TestParallel(MacroTestBase):
    async def test_1_child_macro(self):
        macro = Parser.parse(
            "parallel(key(a))",
            self.context,
            DummyMapping(),
            True,
        )
        self.assertEqual(len(macro.tasks[0].child_macros), 1)
        await macro.run(self.handler)
        self.assertEqual(self.result, [(EV_KEY, KEY_A, 1), (EV_KEY, KEY_A, 0)])

    async def test_4_child_macros(self):
        macro = Parser.parse(
            "parallel(key(a), key(b), key(c), key(d))",
            self.context,
            DummyMapping(),
            True,
        )
        self.assertEqual(len(macro.tasks[0].child_macros), 4)
        await macro.run(self.handler)
        self.assertIn((EV_KEY, KEY_A, 0), self.result)
        self.assertIn((EV_KEY, KEY_B, 0), self.result)
        self.assertIn((EV_KEY, KEY_C, 0), self.result)
        self.assertIn((EV_KEY, KEY_D, 0), self.result)

    async def test_one_wait_takes_longer(self):
        mapping = DummyMapping()
        mapping.macro_key_sleep_ms = 0
        macro = Parser.parse(
            "parallel(wait(100), wait(10).key(b)).key(c)",
            self.context,
            mapping,
            True,
        )

        asyncio.ensure_future(macro.run(self.handler))
        await asyncio.sleep(0.06)
        # The wait(10).key(b) macro is already done, but KEY_C is not yet injected
        self.assertEqual(len(self.result), 2)
        self.assertIn((EV_KEY, KEY_B, 1), self.result)
        self.assertIn((EV_KEY, KEY_B, 0), self.result)

        # Both need to complete for it to continue to key(c)
        await asyncio.sleep(0.06)
        self.assertEqual(len(self.result), 4)
        self.assertIn((EV_KEY, KEY_C, 1), self.result)
        self.assertIn((EV_KEY, KEY_C, 0), self.result)

    async def test_parallel_hold(self):
        mapping = DummyMapping()
        mapping.macro_key_sleep_ms = 0
        macro = Parser.parse(
            "parallel(hold_keys(a), hold_keys(b)).key(c)",
            self.context,
            mapping,
            True,
        )

        macro.press_trigger()
        asyncio.ensure_future(macro.run(self.handler))
        await asyncio.sleep(0.05)
        self.assertIn((EV_KEY, KEY_A, 1), self.result)
        self.assertIn((EV_KEY, KEY_B, 1), self.result)
        self.assertEqual(len(self.result), 2)

        macro.release_trigger()
        await asyncio.sleep(0.05)
        self.assertIn((EV_KEY, KEY_A, 0), self.result)
        self.assertIn((EV_KEY, KEY_B, 0), self.result)
        self.assertIn((EV_KEY, KEY_C, 1), self.result)
        self.assertIn((EV_KEY, KEY_C, 0), self.result)
        self.assertEqual(len(self.result), 6)


if __name__ == "__main__":
    unittest.main()
