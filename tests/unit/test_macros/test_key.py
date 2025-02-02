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
from inputremapper.configs.validation_errors import (
    MacroError,
    SymbolNotAvailableInTargetError,
)
from inputremapper.injection.macros.parse import Parser
from tests.lib.test_setup import test_setup
from tests.unit.test_macros.macro_test_base import DummyMapping, MacroTestBase


@test_setup
class TestKey(MacroTestBase):
    async def test_1(self):
        macro = Parser.parse("key(1)", self.context, DummyMapping, True)
        one_code = keyboard_layout.get("1")

        await macro.run(self.handler)
        self.assertListEqual(
            self.result,
            [(EV_KEY, one_code, 1), (EV_KEY, one_code, 0)],
        )
        self.assertEqual(self.count_child_macros(macro), 0)

    async def test_named_parameter(self):
        macro = Parser.parse("key(symbol=1)", self.context, DummyMapping, True)
        one_code = keyboard_layout.get("1")

        await macro.run(self.handler)
        self.assertListEqual(
            self.result,
            [(EV_KEY, one_code, 1), (EV_KEY, one_code, 0)],
        )
        self.assertEqual(self.count_child_macros(macro), 0)

    async def test_2(self):
        macro = Parser.parse('key(1).key("KEY_A").key(3)', self.context, DummyMapping)

        await macro.run(self.handler)
        self.assertListEqual(
            self.result,
            [
                (EV_KEY, keyboard_layout.get("1"), 1),
                (EV_KEY, keyboard_layout.get("1"), 0),
                (EV_KEY, keyboard_layout.get("a"), 1),
                (EV_KEY, keyboard_layout.get("a"), 0),
                (EV_KEY, keyboard_layout.get("3"), 1),
                (EV_KEY, keyboard_layout.get("3"), 0),
            ],
        )
        self.assertEqual(self.count_child_macros(macro), 0)

    async def test_key_down_up(self):
        code_a = keyboard_layout.get("a")
        code_b = keyboard_layout.get("b")
        macro = Parser.parse(
            "set(foo, b).key_down($foo).key_up($foo).key_up(a).key_down(a)",
            self.context,
            DummyMapping,
        )
        await macro.run(self.handler)
        self.assertListEqual(
            self.result,
            [
                (EV_KEY, code_b, 1),
                (EV_KEY, code_b, 0),
                (EV_KEY, code_a, 0),
                (EV_KEY, code_a, 1),
            ],
        )

    async def test_raises_error(self):
        Parser.parse("k(1).h(k(a)).k(3)", self.context)  # No error
        self.expect_string_in_error("bracket", "key((1)")
        self.expect_string_in_error("bracket", "k(1))")
        self.assertRaises(MacroError, Parser.parse, "k((1).k)", self.context)
        self.assertRaises(MacroError, Parser.parse, "key(foo=a)", self.context)
        self.assertRaises(
            MacroError, Parser.parse, "key(symbol=a, foo=b)", self.context
        )
        self.assertRaises(MacroError, Parser.parse, "k()", self.context)
        self.assertRaises(MacroError, Parser.parse, "key(invalidkey)", self.context)
        self.assertRaises(MacroError, Parser.parse, 'key("invalidkey")', self.context)
        Parser.parse("key(1)", self.context)  # no error
        self.assertRaises(MacroError, Parser.parse, "k(1, 1)", self.context)
        Parser.parse("key($a)", self.context)  # no error
        self.assertRaises(MacroError, Parser.parse, "key(a)key(b)", self.context)
        # wrong target for BTN_A
        self.assertRaises(
            SymbolNotAvailableInTargetError,
            Parser.parse,
            "key(BTN_A)",
            self.context,
            DummyMapping,
        )


if __name__ == "__main__":
    unittest.main()
