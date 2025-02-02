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
from inputremapper.injection.macros.argument import ArgumentConfig
from inputremapper.injection.macros.macro import macro_variables
from inputremapper.injection.macros.parse import Parser
from inputremapper.injection.macros.raw_value import RawValue
from inputremapper.injection.macros.task import Task
from tests.unit.test_macros.macro_test_base import DummyMapping, MacroTestBase


class TestDynamicTypes(MacroTestBase):
    # "Dynamic" meaning const=False
    async def test_set_type_int(self):
        await Parser.parse(
            "set(a, 1)",
            self.context,
            DummyMapping,
            True,
        ).run(lambda *_, **__: None)
        self.assertEqual(macro_variables.get("a"), 1)
        # assertEqual(1.0, 1) passes, so check for the type to be sure:
        self.assertIsInstance(macro_variables.get("a"), int)

    async def test_set_type_float(self):
        await Parser.parse(
            "set(a, 2.2)",
            self.context,
            DummyMapping,
            True,
        ).run(lambda *_, **__: None)
        self.assertEqual(macro_variables.get("a"), 2.2)

    async def test_set_type_str(self):
        await Parser.parse(
            'set(a, "3")',
            self.context,
            DummyMapping,
            True,
        ).run(lambda *_, **__: None)
        self.assertEqual(macro_variables.get("a"), "3")

    def make_test_task(self, types):
        # Make a new test task, with a different types array each time.
        class TestTask(Task):
            argument_configs = [
                ArgumentConfig(
                    name="testvalue",
                    position=0,
                    types=types,
                )
            ]

        return TestTask(
            [RawValue("$a")],
            {},
            self.context,
            DummyMapping,
        )

    async def test_dynamic_int_parsing(self):
        # set(a, 4) was used. Could be meant as an integer, or as a string
        # (just like how key(KEY_A) doesn't require string quotes to be a string)
        macro_variables["a"] = 4

        test_task = self.make_test_task([str, int])
        self.assertEqual(test_task.get_argument("testvalue").get_value(), 4)

        test_task = self.make_test_task([int])
        self.assertEqual(test_task.get_argument("testvalue").get_value(), 4)

        # Now that ints are not allowed, it will be used as a string
        test_task = self.make_test_task([str])
        self.assertEqual(test_task.get_argument("testvalue").get_value(), "4")

    async def test_dynamic_float_parsing(self):
        # set(a, 5.5) was used.
        macro_variables["a"] = 5.5

        test_task = self.make_test_task([str, float])
        self.assertEqual(test_task.get_argument("testvalue").get_value(), 5.5)

        test_task = self.make_test_task([float])
        self.assertEqual(test_task.get_argument("testvalue").get_value(), 5.5)

        test_task = self.make_test_task([str])
        self.assertEqual(test_task.get_argument("testvalue").get_value(), "5.5")

    async def test_no_float_allowed(self):
        # set(a, 6.6) was used.
        macro_variables["a"] = 6.6

        test_task = self.make_test_task([str, int])
        self.assertEqual(test_task.get_argument("testvalue").get_value(), "6.6")

        test_task = self.make_test_task([int])
        self.assertRaises(
            MacroError,
            lambda: test_task.get_argument("testvalue").get_value(),
        )

    async def test_force_string_float(self):
        # set(a, "7.7") was used. Since quotes are explicitly added, the variable is
        # not intended to be used as a float.
        macro_variables["a"] = "7.7"

        test_task = self.make_test_task([str, float])
        self.assertEqual(test_task.get_argument("testvalue").get_value(), "7.7")

        test_task = self.make_test_task([float])
        self.assertRaises(
            MacroError,
            lambda: test_task.get_argument("testvalue").get_value(),
        )

    async def test_force_string_int(self):
        # set(a, "8") was used.
        macro_variables["a"] = "8"

        test_task = self.make_test_task([int, str])
        self.assertEqual(test_task.get_argument("testvalue").get_value(), "8")

        test_task = self.make_test_task([int])
        self.assertRaises(
            MacroError,
            lambda: test_task.get_argument("testvalue").get_value(),
        )


if __name__ == "__main__":
    unittest.main()
