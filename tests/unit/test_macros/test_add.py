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

from inputremapper.configs.validation_errors import MacroError
from inputremapper.injection.macros.macro import macro_variables
from inputremapper.injection.macros.parse import Parser
from tests.lib.test_setup import test_setup
from tests.unit.test_macros.macro_test_base import DummyMapping, MacroTestBase


@test_setup
class TestAdd(MacroTestBase):
    async def test_add(self):
        await Parser.parse("set(a, 1).add(a, 1)", self.context, DummyMapping).run(
            self.handler
        )
        self.assertEqual(macro_variables.get("a"), 2)

        await Parser.parse("set(b, 1).add(b, -1)", self.context, DummyMapping).run(
            self.handler
        )
        self.assertEqual(macro_variables.get("b"), 0)

        await Parser.parse("set(c, -1).add(c, 500)", self.context, DummyMapping).run(
            self.handler
        )
        self.assertEqual(macro_variables.get("c"), 499)

        await Parser.parse("add(d, 500)", self.context, DummyMapping).run(self.handler)
        self.assertEqual(macro_variables.get("d"), 500)

    async def test_add_invalid(self):
        # For invalid input it should do nothing (except to log to the console)
        await Parser.parse('set(e, "foo").add(e, 1)', self.context, DummyMapping).run(
            self.handler
        )
        self.assertEqual(macro_variables.get("e"), "foo")

        await Parser.parse('set(e, "2").add(e, 3)', self.context, DummyMapping).run(
            self.handler
        )
        self.assertEqual(macro_variables.get("e"), "2")

    async def test_raises_error(self):
        Parser.parse("add(a, 1)", self.context)  # no error
        self.assertRaises(MacroError, Parser.parse, "add(a, b)", self.context)
        self.assertRaises(MacroError, Parser.parse, 'add(a, "1")', self.context)


if __name__ == "__main__":
    unittest.main()
