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


import unittest

from evdev.ecodes import (
    EV_REL,
    EV_KEY,
    REL_X,
)

from inputremapper.configs.keyboard_layout import keyboard_layout
from inputremapper.injection.macros.parse import Parser
from tests.lib.test_setup import test_setup
from tests.unit.test_macros.macro_test_base import MacroTestBase, DummyMapping


@test_setup
class TestEvent(MacroTestBase):
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

    async def test_event_mouse(self):
        macro = Parser.parse("e(EV_REL, REL_X, 10)", self.context, DummyMapping)

        await macro.run(self.handler)
        self.assertListEqual(self.result, [(EV_REL, REL_X, 10)])
        self.assertEqual(self.count_child_macros(macro), 0)


if __name__ == "__main__":
    unittest.main()
