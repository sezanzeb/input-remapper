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
import multiprocessing
import unittest

from evdev.ecodes import (
    EV_KEY,
)

from inputremapper.configs.keyboard_layout import keyboard_layout
from inputremapper.injection.macros.macro import macro_variables
from inputremapper.injection.macros.parse import Parser
from tests.lib.logger import logger
from tests.lib.test_setup import test_setup
from tests.unit.test_macros.macro_test_base import DummyMapping, MacroTestBase


@test_setup
class TestIfEq(MacroTestBase):
    async def test_ifeq_runs(self):
        # deprecated ifeq function, but kept for compatibility reasons
        macro = Parser.parse(
            "set(foo, 2).ifeq(foo, 2, key(a), key(b))",
            self.context,
            DummyMapping,
        )
        code_a = keyboard_layout.get("a")
        code_b = keyboard_layout.get("b")

        await macro.run(self.handler)
        self.assertListEqual(self.result, [(EV_KEY, code_a, 1), (EV_KEY, code_a, 0)])
        self.assertEqual(self.count_child_macros(macro), 2)

    async def test_ifeq_none(self):
        code_a = keyboard_layout.get("a")

        # first param None
        macro = Parser.parse(
            "set(foo, 2).ifeq(foo, 2, None, key(b))", self.context, DummyMapping
        )
        self.assertEqual(self.count_child_macros(macro), 1)
        await macro.run(self.handler)
        self.assertListEqual(self.result, [])

        # second param None
        self.result = []
        macro = Parser.parse(
            "set(foo, 2).ifeq(foo, 2, key(a), None)", self.context, DummyMapping
        )
        self.assertEqual(self.count_child_macros(macro), 1)
        await macro.run(self.handler)
        self.assertListEqual(self.result, [(EV_KEY, code_a, 1), (EV_KEY, code_a, 0)])

        """Old syntax, use None instead"""

        # first param ""
        self.result = []
        macro = Parser.parse(
            "set(foo, 2).ifeq(foo, 2, , key(b))", self.context, DummyMapping
        )
        self.assertEqual(self.count_child_macros(macro), 1)
        await macro.run(self.handler)
        self.assertListEqual(self.result, [])

        # second param ""
        self.result = []
        macro = Parser.parse(
            "set(foo, 2).ifeq(foo, 2, key(a), )", self.context, DummyMapping
        )
        self.assertEqual(self.count_child_macros(macro), 1)
        await macro.run(self.handler)
        self.assertListEqual(self.result, [(EV_KEY, code_a, 1), (EV_KEY, code_a, 0)])

    async def test_ifeq_unknown_key(self):
        macro = Parser.parse("ifeq(qux, 2, key(a), key(b))", self.context, DummyMapping)
        code_a = keyboard_layout.get("a")
        code_b = keyboard_layout.get("b")

        await macro.run(self.handler)
        self.assertListEqual(self.result, [(EV_KEY, code_b, 1), (EV_KEY, code_b, 0)])
        self.assertEqual(self.count_child_macros(macro), 2)

    async def test_if_eq(self):
        """new version of ifeq"""
        code_a = keyboard_layout.get("a")
        code_b = keyboard_layout.get("b")
        a_press = [(EV_KEY, code_a, 1), (EV_KEY, code_a, 0)]
        b_press = [(EV_KEY, code_b, 1), (EV_KEY, code_b, 0)]

        async def test(macro, expected):
            """Run the macro and compare the injections with an expectation."""
            logger.info("Testing %s", macro)
            # cleanup
            macro_variables._clear()
            self.assertIsNone(macro_variables.get("a"))
            self.result.clear()

            # test
            macro = Parser.parse(macro, self.context, DummyMapping)
            await macro.run(self.handler)
            self.assertListEqual(self.result, expected)

        await test("if_eq(1, 1, key(a), key(b))", a_press)
        await test("if_eq(1, 2, key(a), key(b))", b_press)
        await test("if_eq(value_1=1, value_2=1, then=key(a), else=key(b))", a_press)
        await test('set(a, "foo").if_eq($a, "foo", key(a), key(b))', a_press)
        await test('set(a, "foo").if_eq("foo", $a, key(a), key(b))', a_press)
        await test('set(a, "foo").if_eq("foo", $a, , key(b))', [])
        await test('set(a, "foo").if_eq("foo", $a, None, key(b))', [])
        await test('set(a, "qux").if_eq("foo", $a, key(a), key(b))', b_press)
        await test('set(a, "qux").if_eq($a, "foo", key(a), key(b))', b_press)
        await test('set(a, "qux").if_eq($a, "foo", key(a), )', [])
        await test('set(a, "x").set(b, "y").if_eq($b, $a, key(a), key(b))', b_press)
        await test('set(a, "x").set(b, "y").if_eq($b, $a, key(a), )', [])
        await test('set(a, "x").set(b, "y").if_eq($b, $a, key(a), None)', [])
        await test('set(a, "x").set(b, "y").if_eq($b, $a, key(a), else=None)', [])
        await test('set(a, "x").set(b, "x").if_eq($b, $a, key(a), key(b))', a_press)
        await test('set(a, "x").set(b, "x").if_eq($b, $a, , key(b))', [])
        await test("if_eq($q, $w, key(a), else=key(b))", a_press)  # both None
        await test("set(q, 1).if_eq($q, $w, key(a), else=key(b))", b_press)
        await test("set(q, 1).set(w, 1).if_eq($q, $w, key(a), else=key(b))", a_press)
        await test('set(q, " a b ").if_eq($q, " a b ", key(a), key(b))', a_press)
        await test('if_eq("\t", "\n", key(a), key(b))', b_press)

        # treats values in quotes as strings, not as code
        await test('set(q, "$a").if_eq($q, "$a", key(a), key(b))', a_press)
        await test('set(q, "a,b").if_eq("a,b", $q, key(a), key(b))', a_press)
        await test('set(q, "c(1, 2)").if_eq("c(1, 2)", $q, key(a), key(b))', a_press)
        await test('set(q, "c(1, 2)").if_eq("c(1, 2)", "$q", key(a), key(b))', b_press)
        await test('if_eq("value_1=1", 1, key(a), key(b))', b_press)

        # won't compare strings and int, be similar to python
        await test('set(a, "1").if_eq($a, 1, key(a), key(b))', b_press)
        await test('set(a, 1).if_eq($a, "1", key(a), key(b))', b_press)

    async def test_if_eq_runs_multiprocessed(self):
        """ifeq on variables that have been set in other processes works."""
        macro = Parser.parse(
            "if_eq($foo, 3, key(a), key(b))", self.context, DummyMapping
        )
        code_a = keyboard_layout.get("a")
        code_b = keyboard_layout.get("b")

        self.assertEqual(self.count_child_macros(macro), 2)

        def set_foo(value):
            # will write foo = 2 into the shared dictionary of macros
            macro_2 = Parser.parse(f"set(foo, {value})", self.context, DummyMapping)
            loop = asyncio.new_event_loop()
            loop.run_until_complete(macro_2.run(lambda: None))

        """foo is not 3"""

        process = multiprocessing.Process(target=set_foo, args=(2,))
        process.start()
        process.join()
        await macro.run(self.handler)
        self.assertListEqual(self.result, [(EV_KEY, code_b, 1), (EV_KEY, code_b, 0)])

        """foo is 3"""

        process = multiprocessing.Process(target=set_foo, args=(3,))
        process.start()
        process.join()
        await macro.run(self.handler)
        self.assertListEqual(
            self.result,
            [
                (EV_KEY, code_b, 1),
                (EV_KEY, code_b, 0),
                (EV_KEY, code_a, 1),
                (EV_KEY, code_a, 0),
            ],
        )


if __name__ == "__main__":
    unittest.main()
