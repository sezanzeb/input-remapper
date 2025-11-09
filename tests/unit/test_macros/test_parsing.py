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


import re
import unittest

from evdev.ecodes import EV_KEY, KEY_A, KEY_B, KEY_C, KEY_E

from inputremapper.configs.validation_errors import (
    MacroError,
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
                logger.info('testing "%s"', string)
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

    async def test_string_not_a_macro(self):
        # passing a string parameter. This is not a macro, even though
        # it might look like it without the string quotes. Everything with
        # explicit quotes around it has to be treated as a string.
        self.assertRaises(MacroError, Parser.parse, '"modify(a, b)"', self.context)

    async def test_multiline_macro_and_comments(self):
        # the parser is not confused by the code in the comments and can use hashtags
        # in strings in the actual code
        comment = '# repeat(1,key(KEY_D)).set(a,"#b")'
        macro = Parser.parse(
            f"""
            {comment}
            key(KEY_A).{comment}
            key(KEY_B). {comment}
            repeat({comment}
                1, {comment}
                key(KEY_C){comment}
            ). {comment}
            {comment}
            set(a, "#").{comment}
            if_eq($a, "#", key(KEY_E), key(KEY_F)) {comment}
            {comment}
        """,
            self.context,
            DummyMapping,
        )
        await macro.run(self.handler)
        self.assertListEqual(
            self.result,
            [
                (EV_KEY, KEY_A, 1),
                (EV_KEY, KEY_A, 0),
                (EV_KEY, KEY_B, 1),
                (EV_KEY, KEY_B, 0),
                (EV_KEY, KEY_C, 1),
                (EV_KEY, KEY_C, 0),
                (EV_KEY, KEY_E, 1),
                (EV_KEY, KEY_E, 0),
            ],
        )

    async def test_child_macro_count(self):
        # It correctly keeps track of child-macros for both positional and keyword-args
        macro = Parser.parse(
            "hold(macro=hold(hold())).repeat(1, macro=repeat(1, hold()))",
            self.context,
            DummyMapping,
            True,
        )
        self.assertEqual(self.count_child_macros(macro), 4)
        self.assertEqual(self.count_tasks(macro), 6)


if __name__ == "__main__":
    unittest.main()
