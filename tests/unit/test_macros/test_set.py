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
from inputremapper.injection.macros.macro import macro_variables
from inputremapper.injection.macros.parse import Parser
from tests.lib.test_setup import test_setup
from tests.unit.test_macros.macro_test_base import MacroTestBase, DummyMapping


@test_setup
class TestSet(MacroTestBase):
    async def test_set_key(self):
        code_b = keyboard_layout.get("b")
        macro = Parser.parse("set(foo, b).key($foo)", self.context, DummyMapping)
        await macro.run(self.handler)
        self.assertListEqual(
            self.result,
            [
                (EV_KEY, code_b, 1),
                (EV_KEY, code_b, 0),
            ],
        )

    async def test_int_is_explicit_string(self):
        await Parser.parse(
            'set( \t"b" \n, "1")',
            self.context,
            DummyMapping,
        ).run(self.handler)
        self.assertEqual(macro_variables.get("b"), "1")

    async def test_int_is_int(self):
        await Parser.parse(
            "set(a, 1)",
            self.context,
            DummyMapping,
        ).run(self.handler)
        self.assertEqual(macro_variables.get("a"), 1)

    async def test_none(self):
        await Parser.parse(
            "set(a, )",
            self.context,
            DummyMapping,
        ).run(self.handler)
        self.assertEqual(macro_variables.get("a"), None)

    async def test_set_case_sensitive_1(self):
        await Parser.parse(
            'set(a, "foo")',
            self.context,
            DummyMapping,
        ).run(self.handler)
        self.assertEqual(macro_variables.get("a"), "foo")
        self.assertEqual(macro_variables.get("A"), None)

    async def test_set_case_sensitive_2(self):
        await Parser.parse(
            'set(A, "foo")',
            self.context,
            DummyMapping,
        ).run(self.handler)
        self.assertEqual(macro_variables.get("A"), "foo")
        self.assertEqual(macro_variables.get("a"), None)

    async def test_raises_error(self):
        self.assertRaises(MacroError, Parser.parse, "set($a, 1)", self.context)
        self.assertRaises(MacroError, Parser.parse, "set(1, 2)", self.context)
        self.assertRaises(MacroError, Parser.parse, "set(+, 2)", self.context)
        self.assertRaises(MacroError, Parser.parse, "set(a(), 2)", self.context)
        self.assertRaises(MacroError, Parser.parse, "set('b,c', 2)", self.context)
        self.assertRaises(MacroError, Parser.parse, 'set("b,c", 2)', self.context)
        Parser.parse("set(A, 2)", self.context)  # no error


if __name__ == "__main__":
    unittest.main()
