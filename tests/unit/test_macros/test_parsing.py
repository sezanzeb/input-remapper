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


import re
import unittest

from inputremapper.configs.validation_errors import (
    MacroError,
    SymbolNotAvailableInTargetError,
)
from inputremapper.injection.macros.argument import Argument, ArgumentConfig
from inputremapper.injection.macros.parse import Parser
from inputremapper.injection.macros.raw_value import RawValue
from inputremapper.injection.macros.tasks.hold_keys import HoldKeysTask
from inputremapper.injection.macros.tasks.if_tap import IfTapTask
from inputremapper.injection.macros.tasks.key import KeyTask
from inputremapper.injection.macros.variable import Variable
from tests.lib.logger import logger
from tests.lib.test_setup import test_setup
from tests.unit.test_macros.macro_test_base import DummyMapping, MacroTestBase


@test_setup
class TestParsing(MacroTestBase):
    def test_get_macro_argument_names(self):
        self.assertEqual(
            IfTapTask.get_macro_argument_names(),
            ["then", "else", "timeout"],
        )

        self.assertEqual(
            HoldKeysTask.get_macro_argument_names(),
            ["*symbols"],
        )

    def test_get_num_parameters(self):
        self.assertEqual(IfTapTask.get_num_parameters(), (0, 3))
        self.assertEqual(KeyTask.get_num_parameters(), (1, 1))
        self.assertEqual(HoldKeysTask.get_num_parameters(), (0, float("inf")))

    def test_remove_whitespaces(self):
        self.assertEqual(Parser.remove_whitespaces('foo"bar"foo'), 'foo"bar"foo')
        self.assertEqual(Parser.remove_whitespaces('foo" bar"foo'), 'foo" bar"foo')
        self.assertEqual(
            Parser.remove_whitespaces('foo" bar"fo" "o'), 'foo" bar"fo" "o'
        )
        self.assertEqual(
            Parser.remove_whitespaces(' fo o"\nba r "f\noo'), 'foo"\nba r "foo'
        )
        self.assertEqual(Parser.remove_whitespaces(' a " b " c " '), 'a" b "c" ')

        self.assertEqual(Parser.remove_whitespaces('"""""""""'), '"""""""""')
        self.assertEqual(Parser.remove_whitespaces('""""""""'), '""""""""')

        self.assertEqual(Parser.remove_whitespaces("      "), "")
        self.assertEqual(Parser.remove_whitespaces('     " '), '" ')
        self.assertEqual(Parser.remove_whitespaces('     " " '), '" "')

        self.assertEqual(Parser.remove_whitespaces("a# ##b", delimiter="##"), "a###b")
        self.assertEqual(Parser.remove_whitespaces("a###b", delimiter="##"), "a###b")
        self.assertEqual(Parser.remove_whitespaces("a## #b", delimiter="##"), "a## #b")
        self.assertEqual(
            Parser.remove_whitespaces("a## ##b", delimiter="##"), "a## ##b"
        )

    def test_remove_comments(self):
        self.assertEqual(Parser.remove_comments("a#b"), "a")
        self.assertEqual(Parser.remove_comments('"a#b"'), '"a#b"')
        self.assertEqual(Parser.remove_comments('a"#"#b'), 'a"#"')
        self.assertEqual(Parser.remove_comments('a"#""#"#b'), 'a"#""#"')
        self.assertEqual(Parser.remove_comments('#a"#""#"#b'), "")

        self.assertEqual(
            re.sub(
                r"\s",
                "",
                Parser.remove_comments(
                    """
            # a
            b
            # c
            d
        """
                ),
            ),
            "bd",
        )

    async def test_count_brackets(self):
        self.assertEqual(Parser._count_brackets(""), 0)
        self.assertEqual(Parser._count_brackets("()"), 2)
        self.assertEqual(Parser._count_brackets("a()"), 3)
        self.assertEqual(Parser._count_brackets("a(b)"), 4)
        self.assertEqual(Parser._count_brackets("a(b())"), 6)
        self.assertEqual(Parser._count_brackets("a(b(c))"), 7)
        self.assertEqual(Parser._count_brackets("a(b(c))d"), 7)
        self.assertEqual(Parser._count_brackets("a(b(c))d()"), 7)

    def test_split_keyword_arg(self):
        self.assertTupleEqual(Parser._split_keyword_arg("_A=b"), ("_A", "b"))
        self.assertTupleEqual(Parser._split_keyword_arg("a_=1"), ("a_", "1"))
        self.assertTupleEqual(
            Parser._split_keyword_arg("a=repeat(2, KEY_A)"),
            ("a", "repeat(2, KEY_A)"),
        )
        self.assertTupleEqual(Parser._split_keyword_arg('a="=,#+."'), ("a", '"=,#+."'))

    def test_is_this_a_macro(self):
        self.assertTrue(Parser.is_this_a_macro("key(1)"))
        self.assertTrue(Parser.is_this_a_macro("key(1).key(2)"))
        self.assertTrue(Parser.is_this_a_macro("repeat(1, key(1).key(2))"))

        self.assertFalse(Parser.is_this_a_macro("1"))
        self.assertFalse(Parser.is_this_a_macro("key_kp1"))
        self.assertFalse(Parser.is_this_a_macro("btn_left"))
        self.assertFalse(Parser.is_this_a_macro("minus"))
        self.assertFalse(Parser.is_this_a_macro("k"))
        self.assertFalse(Parser.is_this_a_macro(1))
        self.assertFalse(Parser.is_this_a_macro(None))

        self.assertTrue(Parser.is_this_a_macro("a+b"))
        self.assertTrue(Parser.is_this_a_macro("a+b+c"))
        self.assertTrue(Parser.is_this_a_macro("a + b"))
        self.assertTrue(Parser.is_this_a_macro("a + b + c"))

    def test_handle_plus_syntax(self):
        self.assertEqual(Parser.handle_plus_syntax("a + b"), "hold_keys(a,b)")
        self.assertEqual(Parser.handle_plus_syntax("a + b + c"), "hold_keys(a,b,c)")
        self.assertEqual(Parser.handle_plus_syntax(" a+b+c "), "hold_keys(a,b,c)")

        # invalid. The last one with `key` should not have been a parameter
        # of this function to begin with.
        strings = ["+", "a+", "+b", "a\n+\n+\nb", "key(a + b)"]
        for string in strings:
            with self.assertRaises(MacroError):
                logger.info(f'testing "%s"', string)
                Parser.handle_plus_syntax(string)

        self.assertEqual(Parser.handle_plus_syntax("a"), "a")
        self.assertEqual(Parser.handle_plus_syntax("key(a)"), "key(a)")
        self.assertEqual(Parser.handle_plus_syntax(""), "")

    def test_parse_plus_syntax(self):
        macro = Parser.parse("a + b")
        self.assertEqual(macro.code, "hold_keys(a,b)")

        # this is not erroneously recognized as "plus" syntax
        macro = Parser.parse("key(a) # a + b")
        self.assertEqual(macro.code, "key(a)")

    async def test_extract_params(self):
        # splits strings, doesn't try to understand their meaning yet
        def expect(raw, expectation):
            self.assertListEqual(Parser._extract_args(raw), expectation)

        expect("a", ["a"])
        expect("a,b", ["a", "b"])
        expect("a,b,c", ["a", "b", "c"])

        expect("key(a)", ["key(a)"])
        expect("key(a).key(b), key(a)", ["key(a).key(b)", "key(a)"])
        expect("key(a), key(a).key(b)", ["key(a)", "key(a).key(b)"])

        expect(
            'a("foo(1,2,3)", ",,,,,,    "), , ""',
            ['a("foo(1,2,3)", ",,,,,,    ")', "", '""'],
        )

        expect(
            ",1,   ,b,x(,a(),).y().z(),,",
            ["", "1", "", "b", "x(,a(),).y().z()", "", ""],
        )

        expect("repeat(1, key(a))", ["repeat(1, key(a))"])
        expect(
            "repeat(1, key(a)), repeat(1, key(b))",
            ["repeat(1, key(a))", "repeat(1, key(b))"],
        )
        expect(
            "repeat(1, key(a)), repeat(1, key(b)), repeat(1, key(c))",
            ["repeat(1, key(a))", "repeat(1, key(b))", "repeat(1, key(c))"],
        )

        # will be parsed as None
        expect("", [""])
        expect(",", ["", ""])
        expect(",,", ["", "", ""])

    async def test_parse_params(self):
        def test(value, types):
            argument = Argument(
                ArgumentConfig(position=0, name="test", types=types),
                DummyMapping,
            )
            argument.initialize_variable(RawValue(value=value))
            return argument._variable

        self.assertEqual(
            test("", [None, int, float]),
            Variable(None, const=True),
        )

        # strings. If it is wrapped in quotes, don't parse the contents
        self.assertEqual(
            test('"foo"', [str]),
            Variable("foo", const=True),
        )
        self.assertEqual(
            test('"\tf o o\n"', [str]),
            Variable("\tf o o\n", const=True),
        )
        self.assertEqual(
            test('"foo(a,b)"', [str]),
            Variable("foo(a,b)", const=True),
        )
        self.assertEqual(
            test('",,,()"', [str]),
            Variable(",,,()", const=True),
        )

        # strings without quotes only work as long as there is no function call or
        # anything. This is only really acceptable for constants like KEY_A and for
        # variable names, which are not allowed to contain special characters that may
        # have a meaning in the macro syntax.
        self.assertEqual(
            test("foo", [str]),
            Variable("foo", const=True),
        )

        self.assertEqual(
            test("", [str, None]),
            Variable(None, const=True),
        )
        self.assertEqual(
            test("", [str]),
            Variable("", const=True),
        )
        self.assertEqual(
            test("", [None]),
            Variable(None, const=True),
        )
        self.assertEqual(
            test("None", [None]),
            Variable(None, const=True),
        )
        self.assertEqual(
            test('"None"', [str]),
            Variable("None", const=True),
        )

        self.assertEqual(
            test("5", [int]),
            Variable(5, const=True),
        )
        self.assertEqual(
            test("5", [float, int]),
            Variable(5, const=True),
        )
        self.assertEqual(
            test("5.2", [int, float]),
            Variable(5.2, const=True),
        )
        self.assertIsInstance(
            test("$foo", [str]),
            Variable,
        )
        self.assertEqual(
            test("$foo", [str]),
            Variable("foo", const=False),
        )

    async def test_raises_error(self):
        def expect_string_in_error(string: str, macro: str):
            with self.assertRaises(MacroError) as cm:
                Parser.parse(macro, self.context)
            error = str(cm.exception)
            self.assertIn(string, error)

        Parser.parse("k(1).h(k(a)).k(3)", self.context)  # No error
        expect_string_in_error("bracket", "key((1)")
        expect_string_in_error("bracket", "k(1))")
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
        self.assertRaises(MacroError, Parser.parse, "h(1, 1)", self.context)
        self.assertRaises(MacroError, Parser.parse, "h(hold(h(1, 1)))", self.context)
        self.assertRaises(MacroError, Parser.parse, "r(1)", self.context)
        self.assertRaises(MacroError, Parser.parse, "repeat(a, k(1))", self.context)
        Parser.parse("repeat($a, k(1))", self.context)  # no error
        Parser.parse("repeat(2, k(1))", self.context)  # no error
        self.assertRaises(MacroError, Parser.parse, 'repeat("2", k(1))', self.context)
        self.assertRaises(MacroError, Parser.parse, "r(1, 1)", self.context)
        self.assertRaises(MacroError, Parser.parse, "r(k(1), 1)", self.context)
        Parser.parse("r(1, macro=k(1))", self.context)  # no error
        self.assertRaises(MacroError, Parser.parse, "r(a=1, b=k(1))", self.context)
        self.assertRaises(
            MacroError,
            Parser.parse,
            "r(repeats=1, macro=k(1), a=2)",
            self.context,
        )
        self.assertRaises(
            MacroError,
            Parser.parse,
            "r(repeats=1, macro=k(1), repeats=2)",
            self.context,
        )
        self.assertRaises(MacroError, Parser.parse, "modify(asdf, k(a))", self.context)
        Parser.parse("if_tap(, k(a), 1000)", self.context)  # no error
        Parser.parse("if_tap(, k(a), timeout=1000)", self.context)  # no error
        Parser.parse("if_tap(, k(a), $timeout)", self.context)  # no error
        Parser.parse("if_tap(, k(a), timeout=$t)", self.context)  # no error
        Parser.parse("if_tap(, key(a))", self.context)  # no error
        Parser.parse("if_tap(k(a),)", self.context)  # no error
        self.assertRaises(MacroError, Parser.parse, "if_tap(k(a), b)", self.context)
        Parser.parse("if_single(k(a),)", self.context)  # no error
        self.assertRaises(MacroError, Parser.parse, "if_single(1,)", self.context)
        self.assertRaises(MacroError, Parser.parse, "if_single(,1)", self.context)
        Parser.parse("mouse(up, 3)", self.context)  # no error
        Parser.parse("mouse(up, speed=$a)", self.context)  # no error
        self.assertRaises(MacroError, Parser.parse, "mouse(3, up)", self.context)
        Parser.parse("wheel(left, 3)", self.context)  # no error
        self.assertRaises(MacroError, Parser.parse, "wheel(3, left)", self.context)
        Parser.parse("w(2)", self.context)  # no error
        self.assertRaises(MacroError, Parser.parse, "wait(a)", self.context)
        Parser.parse("ifeq(a, 2, k(a),)", self.context)  # no error
        Parser.parse("ifeq(a, 2, , k(a))", self.context)  # no error
        Parser.parse("ifeq(a, 2, None, k(a))", self.context)  # no error
        self.assertRaises(MacroError, Parser.parse, "ifeq(a, 2, 1,)", self.context)
        self.assertRaises(MacroError, Parser.parse, "ifeq(a, 2, , 2)", self.context)
        Parser.parse("if_eq(2, $a, k(a),)", self.context)  # no error
        Parser.parse("if_eq(2, $a, , else=k(a))", self.context)  # no error
        self.assertRaises(MacroError, Parser.parse, "if_eq(2, $a, 1,)", self.context)
        self.assertRaises(MacroError, Parser.parse, "if_eq(2, $a, , 2)", self.context)

        expect_string_in_error("blub", "if_eq(2, $a, key(a), blub=a)")

        expect_string_in_error("foo", "foo(a)")

        self.assertRaises(MacroError, Parser.parse, "set($a, 1)", self.context)
        self.assertRaises(MacroError, Parser.parse, "set(1, 2)", self.context)
        self.assertRaises(MacroError, Parser.parse, "set(+, 2)", self.context)
        self.assertRaises(MacroError, Parser.parse, "set(a(), 2)", self.context)
        self.assertRaises(MacroError, Parser.parse, "set('b,c', 2)", self.context)
        self.assertRaises(MacroError, Parser.parse, 'set("b,c", 2)', self.context)
        Parser.parse("set(A, 2)", self.context)  # no error

        self.assertRaises(MacroError, Parser.parse, "key(a)key(b)", self.context)
        self.assertRaises(MacroError, Parser.parse, "hold(key(a)key(b))", self.context)

        self.assertRaises(
            MacroError, Parser.parse, "hold_keys(a, broken, b)", self.context
        )

        Parser.parse("add(a, 1)", self.context)  # no error
        self.assertRaises(MacroError, Parser.parse, "add(a, b)", self.context)
        self.assertRaises(MacroError, Parser.parse, 'add(a, "1")', self.context)

        Parser.parse("if_capslock(else=key(KEY_A))", self.context)  # no error
        Parser.parse("if_capslock(key(KEY_A), None)", self.context)  # no error
        Parser.parse("if_capslock(key(KEY_A))", self.context)  # no error
        Parser.parse("if_capslock(then=key(KEY_A))", self.context)  # no error
        Parser.parse("if_numlock(else=key(KEY_A))", self.context)  # no error
        Parser.parse("if_numlock(key(KEY_A), None)", self.context)  # no error
        Parser.parse("if_numlock(key(KEY_A))", self.context)  # no error
        Parser.parse("if_numlock(then=key(KEY_A))", self.context)  # no error

        # wrong target for BTN_A
        self.assertRaises(
            SymbolNotAvailableInTargetError,
            Parser.parse,
            "key(BTN_A)",
            self.context,
            DummyMapping,
        )

        # passing a string parameter. This is not a macro, even though
        # it might look like it without the string quotes. Everything with
        # explicit quotes around it has to be treated as a string.
        self.assertRaises(MacroError, Parser.parse, '"modify(a, b)"', self.context)


if __name__ == "__main__":
    unittest.main()
