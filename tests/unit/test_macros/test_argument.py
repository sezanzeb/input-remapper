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

from inputremapper.configs.validation_errors import (
    MacroError,
)
from inputremapper.injection.macros.argument import Argument, ArgumentConfig
from inputremapper.injection.macros.macro import Macro, macro_variables
from inputremapper.injection.macros.raw_value import RawValue
from inputremapper.injection.macros.variable import Variable
from tests.lib.test_setup import test_setup
from tests.unit.test_macros.macro_test_base import DummyMapping, MacroTestBase


@test_setup
class TestArgument(MacroTestBase):
    def test_resolve(self):
        self.assertEqual(Variable("a", const=True).get_value(), "a")
        self.assertEqual(Variable(1, const=True).get_value(), 1)
        self.assertEqual(Variable(None, const=True).get_value(), None)

        # $ is part of a custom string here
        self.assertEqual(Variable('"$a"', const=True).get_value(), '"$a"')
        self.assertEqual(Variable("'$a'", const=True).get_value(), "'$a'")
        self.assertEqual(Variable("$a", const=True).get_value(), "$a")

        variable = Variable("a", const=False)
        self.assertEqual(variable.get_value(), None)
        macro_variables["a"] = 1
        self.assertEqual(variable.get_value(), 1)

    def test_type_check(self):
        def test(value, types, name, position):
            argument = Argument(
                ArgumentConfig(
                    types=types,
                    name=name,
                    position=position,
                ),
                DummyMapping(),
            )
            argument.initialize_variable(RawValue(value=value))
            return argument.get_value()

        def test_variable(variable, types, name, position):
            argument = Argument(
                ArgumentConfig(
                    types=types,
                    name=name,
                    position=position,
                ),
                DummyMapping(),
            )
            argument._variable = variable
            return argument.get_value()

        # allows params that can be cast to the target type
        self.assertEqual(test("1", [str, None], "foo", 0), "1")
        self.assertEqual(test("1.2", [str], "foo", 2), "1.2")

        self.assertRaises(
            MacroError,
            lambda: test("1.2", [int], "foo", 3),
        )
        self.assertRaises(MacroError, lambda: test("a", [None], "foo", 0))
        self.assertRaises(MacroError, lambda: test("a", [int], "foo", 1))
        self.assertRaises(
            MacroError,
            lambda: test("a", [int, float], "foo", 2),
        )
        self.assertRaises(
            MacroError,
            lambda: test("a", [int, None], "foo", 3),
        )
        self.assertEqual(test("a", [int, float, None, str], "foo", 4), "a")

        # variables are expected to be of the Variable type here, not a $string
        self.assertRaises(
            MacroError,
            lambda: test("$a", [int], "foo", 4),
        )

        # We don't cast values that were explicitly set as strings back into numbers.
        variable = Variable("a", const=False)
        variable.set_value("5")
        self.assertRaises(
            MacroError,
            lambda: test_variable(variable, [int], "foo", 4),
        )

        self.assertRaises(
            MacroError,
            lambda: test("a", [Macro], "foo", 0),
        )
        self.assertRaises(MacroError, lambda: test("1", [Macro], "foo", 0))

    def test_validate_variable_name(self):
        self.assertRaises(
            MacroError,
            lambda: Variable("1a", const=False).validate_variable_name(),
        )
        self.assertRaises(
            MacroError,
            lambda: Variable("$a", const=False).validate_variable_name(),
        )
        self.assertRaises(
            MacroError,
            lambda: Variable("a()", const=False).validate_variable_name(),
        )
        self.assertRaises(
            MacroError,
            lambda: Variable("1", const=False).validate_variable_name(),
        )
        self.assertRaises(
            MacroError,
            lambda: Variable("+", const=False).validate_variable_name(),
        )
        self.assertRaises(
            MacroError,
            lambda: Variable("-", const=False).validate_variable_name(),
        )
        self.assertRaises(
            MacroError,
            lambda: Variable("*", const=False).validate_variable_name(),
        )
        self.assertRaises(
            MacroError,
            lambda: Variable("a,b", const=False).validate_variable_name(),
        )
        self.assertRaises(
            MacroError,
            lambda: Variable("a,b", const=False).validate_variable_name(),
        )
        self.assertRaises(
            MacroError,
            lambda: Variable("#", const=False).validate_variable_name(),
        )
        self.assertRaises(
            MacroError,
            lambda: Variable(1, const=False).validate_variable_name(),
        )
        self.assertRaises(
            MacroError,
            lambda: Variable(None, const=False).validate_variable_name(),
        )
        self.assertRaises(
            MacroError,
            lambda: Variable([], const=False).validate_variable_name(),
        )
        self.assertRaises(
            MacroError,
            lambda: Variable((), const=False).validate_variable_name(),
        )

        # doesn't raise
        Variable("a", const=False).validate_variable_name()
        Variable("_a", const=False).validate_variable_name()
        Variable("_A", const=False).validate_variable_name()
        Variable("A", const=False).validate_variable_name()
        Variable("Abcd", const=False).validate_variable_name()
        Variable("Abcd_", const=False).validate_variable_name()
        Variable("Abcd_1234", const=False).validate_variable_name()
        Variable("Abcd1234_", const=False).validate_variable_name()


if __name__ == "__main__":
    unittest.main()
