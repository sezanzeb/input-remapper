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
class TestToggle(MacroTestBase):
    async def test_toggle(self):
        # repeats key(a) as long as macro is toggled
        macro = Parser.parse("toggle(key(a))", self.context, DummyMapping)

        macro.press_trigger()
        macro.release_trigger()
        asyncio.ensure_future(macro.run(self.handler))
        await asyncio.sleep(0.2)
        self.assertGreater(len(self.result), 2)

        code_a = keyboard_layout.get("a")
        self.assertGreater(self.result.count((EV_KEY, code_a, 1)), 2)

        self.assertEqual(self.count_child_macros(macro), 1)
        self.assertEqual(self.count_tasks(macro), 1)

        macro.press_trigger()
        macro.release_trigger()
        result_count = self.result.count((EV_KEY, code_a, 1))
        await asyncio.sleep(0.2)
        # ensure that the macro has stopped
        self.assertEqual(result_count, self.result.count((EV_KEY, code_a, 1)))


if __name__ == "__main__":
    unittest.main()
