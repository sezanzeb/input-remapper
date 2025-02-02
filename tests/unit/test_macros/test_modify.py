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


import unittest

from evdev.ecodes import EV_KEY

from inputremapper.configs.keyboard_layout import keyboard_layout
from inputremapper.configs.validation_errors import MacroError
from inputremapper.injection.macros.parse import Parser
from tests.lib.test_setup import test_setup
from tests.unit.test_macros.macro_test_base import MacroTestBase, DummyMapping


@test_setup
class TestModify(MacroTestBase):
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

    async def test_raises_error(self):
        self.assertRaises(MacroError, Parser.parse, "modify(asdf, k(a))", self.context)


if __name__ == "__main__":
    unittest.main()
