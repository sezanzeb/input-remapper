#!/usr/bin/python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2022 sezanzeb <proxima@sezanzeb.de>
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
from evdev._ecodes import EV_ABS, ABS_Y

from tests.test import logger, quick_cleanup, new_event

import time
import unittest
import re
import asyncio
import multiprocessing
from unittest import mock

from evdev.ecodes import (
    EV_REL,
    EV_KEY,
    REL_Y,
    REL_X,
    REL_WHEEL,
    REL_HWHEEL,
    REL_WHEEL_HI_RES,
    REL_HWHEEL_HI_RES,
    KEY_A,
    KEY_B,
    KEY_C,
    KEY_E,
)

from inputremapper.injection.macros.macro import (
    Macro,
    _type_check,
    macro_variables,
    _type_check_variablename,
    _resolve,
    Variable,
)
from inputremapper.injection.macros.parse import (
    parse,
    _extract_args,
    is_this_a_macro,
    _parse_recurse,
    handle_plus_syntax,
    _count_brackets,
    _split_keyword_arg,
    remove_whitespaces,
    remove_comments,
    get_macro_argument_names,
    get_num_parameters,
)
from inputremapper.exceptions import MacroParsingError
from inputremapper.injection.context import Context
from inputremapper.configs.global_config import global_config
from inputremapper.configs.preset import Preset
from inputremapper.configs.system_mapping import system_mapping
from inputremapper.utils import PRESS, RELEASE


class MacroTestBase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.result = []

        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            # suddenly "There is no current event loop in thread 'MainThread'"
            # errors started to appear
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        self.context = Context(Preset())

    def tearDown(self):
        self.result = []
        quick_cleanup()

    def handler(self, ev_type, code, value):
        """Where macros should write codes to."""
        print(f"\033[90mmacro wrote{(ev_type, code, value)}\033[0m")
        self.result.append((ev_type, code, value))

    async def trigger_sequence(self, macro: Macro, event):
        for listener in self.context.listeners:
            asyncio.ensure_future(listener(event))
            await asyncio.sleep(
                0
            )  # this still might cause race conditions and the test to fail

        macro.press_trigger()
        if macro.running:
            return
        asyncio.ensure_future(macro.run(self.handler))

    async def release_sequence(self, macro, event):
        for listener in self.context.listeners:
            asyncio.ensure_future(listener(event))
            await asyncio.sleep(
                0
            )  # this still might cause race conditions and the test to fail

        if macro.is_holding:
            macro.release_trigger()


class DummyMapping:
    macro_key_sleep_ms = 10
    rate = 60


class TestMacros(MacroTestBase):
    async def test_named_parameter(self):
        result = []

        def patch(_, a, b, c, d=400):
            result.append((a, b, c, d))

        functions = {"key": patch}
        with mock.patch("inputremapper.injection.macros.parse.FUNCTIONS", functions):
            await parse("key(1, d=4, b=2, c=3)", self.context, DummyMapping).run(
                self.handler
            )
            await parse("key(1, b=2, c=3)", self.context, DummyMapping).run(
                self.handler
            )
            self.assertListEqual(result, [(1, 2, 3, 4), (1, 2, 3, 400)])

    def test_get_macro_argument_names(self):
        self.assertEqual(
            get_macro_argument_names(Macro.add_if_tap),
            ["then", "else", "timeout"],
        )

        self.assertEqual(
            get_macro_argument_names(Macro.add_hold_keys),
            ["*symbols"],
        )

    def test_get_num_parameters(self):
        self.assertEqual(get_num_parameters(Macro.add_if_tap), (0, 3))
        self.assertEqual(get_num_parameters(Macro.add_key), (1, 1))
        self.assertEqual(get_num_parameters(Macro.add_hold_keys), (0, float("inf")))

    def test_remove_whitespaces(self):
        self.assertEqual(remove_whitespaces('foo"bar"foo'), 'foo"bar"foo')
        self.assertEqual(remove_whitespaces('foo" bar"foo'), 'foo" bar"foo')
        self.assertEqual(remove_whitespaces('foo" bar"fo" "o'), 'foo" bar"fo" "o')
        self.assertEqual(remove_whitespaces(' fo o"\nba r "f\noo'), 'foo"\nba r "foo')
        self.assertEqual(remove_whitespaces(' a " b " c " '), 'a" b "c" ')

        self.assertEqual(remove_whitespaces('"""""""""'), '"""""""""')
        self.assertEqual(remove_whitespaces('""""""""'), '""""""""')

        self.assertEqual(remove_whitespaces("      "), "")
        self.assertEqual(remove_whitespaces('     " '), '" ')
        self.assertEqual(remove_whitespaces('     " " '), '" "')

        self.assertEqual(remove_whitespaces("a# ##b", delimiter="##"), "a###b")
        self.assertEqual(remove_whitespaces("a###b", delimiter="##"), "a###b")
        self.assertEqual(remove_whitespaces("a## #b", delimiter="##"), "a## #b")
        self.assertEqual(remove_whitespaces("a## ##b", delimiter="##"), "a## ##b")

    def test_remove_comments(self):
        self.assertEqual(remove_comments("a#b"), "a")
        self.assertEqual(remove_comments('"a#b"'), '"a#b"')
        self.assertEqual(remove_comments('a"#"#b'), 'a"#"')
        self.assertEqual(remove_comments('a"#""#"#b'), 'a"#""#"')
        self.assertEqual(remove_comments('#a"#""#"#b'), "")

        self.assertEqual(
            re.sub(
                r"\s",
                "",
                remove_comments(
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
        self.assertEqual(_count_brackets(""), 0)
        self.assertEqual(_count_brackets("()"), 2)
        self.assertEqual(_count_brackets("a()"), 3)
        self.assertEqual(_count_brackets("a(b)"), 4)
        self.assertEqual(_count_brackets("a(b())"), 6)
        self.assertEqual(_count_brackets("a(b(c))"), 7)
        self.assertEqual(_count_brackets("a(b(c))d"), 7)
        self.assertEqual(_count_brackets("a(b(c))d()"), 7)

    def test_resolve(self):
        self.assertEqual(_resolve("a"), "a")
        self.assertEqual(_resolve(1), 1)
        self.assertEqual(_resolve(None), None)

        # $ is part of a custom string here
        self.assertEqual(_resolve('"$a"'), '"$a"')
        self.assertEqual(_resolve("'$a'"), "'$a'")

        # variables are expected to be of the Variable type here, not a $string
        self.assertEqual(_resolve("$a"), "$a")
        variable = Variable("a")
        self.assertEqual(_resolve(variable), None)
        macro_variables["a"] = 1
        self.assertEqual(_resolve(variable), 1)

    def test_type_check(self):
        # allows params that can be cast to the target type
        self.assertEqual(_type_check(1, [str, None], "foo", 0), "1")
        self.assertEqual(_type_check("1", [int, None], "foo", 1), 1)
        self.assertEqual(_type_check(1.2, [str], "foo", 2), "1.2")

        self.assertRaises(
            MacroParsingError, lambda: _type_check("1.2", [int], "foo", 3)
        )
        self.assertRaises(MacroParsingError, lambda: _type_check("a", [None], "foo", 0))
        self.assertRaises(MacroParsingError, lambda: _type_check("a", [int], "foo", 1))
        self.assertRaises(
            MacroParsingError, lambda: _type_check("a", [int, float], "foo", 2)
        )
        self.assertRaises(
            MacroParsingError, lambda: _type_check("a", [int, None], "foo", 3)
        )
        self.assertEqual(_type_check("a", [int, float, None, str], "foo", 4), "a")

        # variables are expected to be of the Variable type here, not a $string
        self.assertRaises(MacroParsingError, lambda: _type_check("$a", [int], "foo", 4))
        variable = Variable("a")
        self.assertEqual(_type_check(variable, [int], "foo", 4), variable)

        self.assertRaises(
            MacroParsingError, lambda: _type_check("a", [Macro], "foo", 0)
        )
        self.assertRaises(MacroParsingError, lambda: _type_check(1, [Macro], "foo", 0))
        self.assertEqual(_type_check("1", [Macro, int], "foo", 4), 1)

    def test_type_check_variablename(self):
        self.assertRaises(MacroParsingError, lambda: _type_check_variablename("1a"))
        self.assertRaises(MacroParsingError, lambda: _type_check_variablename("$a"))
        self.assertRaises(MacroParsingError, lambda: _type_check_variablename("a()"))
        self.assertRaises(MacroParsingError, lambda: _type_check_variablename("1"))
        self.assertRaises(MacroParsingError, lambda: _type_check_variablename("+"))
        self.assertRaises(MacroParsingError, lambda: _type_check_variablename("-"))
        self.assertRaises(MacroParsingError, lambda: _type_check_variablename("*"))
        self.assertRaises(MacroParsingError, lambda: _type_check_variablename("a,b"))
        self.assertRaises(MacroParsingError, lambda: _type_check_variablename("a,b"))
        self.assertRaises(MacroParsingError, lambda: _type_check_variablename("#"))
        self.assertRaises(MacroParsingError, lambda: _type_check_variablename(1))
        self.assertRaises(MacroParsingError, lambda: _type_check_variablename(None))
        self.assertRaises(MacroParsingError, lambda: _type_check_variablename([]))
        self.assertRaises(MacroParsingError, lambda: _type_check_variablename(()))

        # doesn't raise
        _type_check_variablename("a")
        _type_check_variablename("_a")
        _type_check_variablename("_A")
        _type_check_variablename("A")
        _type_check_variablename("Abcd")
        _type_check_variablename("Abcd_")
        _type_check_variablename("Abcd_1234")
        _type_check_variablename("Abcd1234_")

    def test_split_keyword_arg(self):
        self.assertTupleEqual(_split_keyword_arg("_A=b"), ("_A", "b"))
        self.assertTupleEqual(_split_keyword_arg("a_=1"), ("a_", "1"))
        self.assertTupleEqual(
            _split_keyword_arg("a=repeat(2, KEY_A)"), ("a", "repeat(2, KEY_A)")
        )
        self.assertTupleEqual(_split_keyword_arg('a="=,#+."'), ("a", '"=,#+."'))

    def test_is_this_a_macro(self):
        self.assertTrue(is_this_a_macro("key(1)"))
        self.assertTrue(is_this_a_macro("key(1).key(2)"))
        self.assertTrue(is_this_a_macro("repeat(1, key(1).key(2))"))

        self.assertFalse(is_this_a_macro("1"))
        self.assertFalse(is_this_a_macro("key_kp1"))
        self.assertFalse(is_this_a_macro("btn_left"))
        self.assertFalse(is_this_a_macro("minus"))
        self.assertFalse(is_this_a_macro("k"))
        self.assertFalse(is_this_a_macro(1))
        self.assertFalse(is_this_a_macro(None))

        self.assertTrue(is_this_a_macro("a+b"))
        self.assertTrue(is_this_a_macro("a+b+c"))
        self.assertTrue(is_this_a_macro("a + b"))
        self.assertTrue(is_this_a_macro("a + b + c"))

    def test_handle_plus_syntax(self):
        self.assertEqual(handle_plus_syntax("a + b"), "modify(a,modify(b,hold()))")
        self.assertEqual(
            handle_plus_syntax("a + b + c"), "modify(a,modify(b,modify(c,hold())))"
        )
        self.assertEqual(
            handle_plus_syntax(" a+b+c "), "modify(a,modify(b,modify(c,hold())))"
        )

        # invalid
        strings = ["+", "a+", "+b", "key(a + b)"]
        for string in strings:
            with self.assertRaises(MacroParsingError):
                logger.info(f'testing "%s"', string)
                handle_plus_syntax(string)

        self.assertEqual(handle_plus_syntax("a"), "a")
        self.assertEqual(handle_plus_syntax("key(a)"), "key(a)")
        self.assertEqual(handle_plus_syntax(""), "")

    def test_parse_plus_syntax(self):
        macro = parse("a + b")
        self.assertEqual(macro.code, "modify(a,modify(b,hold()))")

        # this is not erroneously recognized as "plus" syntax
        macro = parse("key(a) # a + b")
        self.assertEqual(macro.code, "key(a)")

    async def test_run_plus_syntax(self):
        macro = parse("a + b + c + d", self.context, DummyMapping)

        macro.press_trigger()
        asyncio.ensure_future(macro.run(self.handler))
        await asyncio.sleep(0.2)
        self.assertTrue(macro.is_holding())

        # starting from the left, presses each one down
        self.assertEqual(self.result[0], (EV_KEY, system_mapping.get("a"), 1))
        self.assertEqual(self.result[1], (EV_KEY, system_mapping.get("b"), 1))
        self.assertEqual(self.result[2], (EV_KEY, system_mapping.get("c"), 1))
        self.assertEqual(self.result[3], (EV_KEY, system_mapping.get("d"), 1))

        # and then releases starting with the previously pressed key
        macro.release_trigger()
        await asyncio.sleep(0.2)
        self.assertFalse(macro.is_holding())
        self.assertEqual(self.result[4], (EV_KEY, system_mapping.get("d"), 0))
        self.assertEqual(self.result[5], (EV_KEY, system_mapping.get("c"), 0))
        self.assertEqual(self.result[6], (EV_KEY, system_mapping.get("b"), 0))
        self.assertEqual(self.result[7], (EV_KEY, system_mapping.get("a"), 0))

    async def test_extract_params(self):
        # splits strings, doesn't try to understand their meaning yet
        def expect(raw, expectation):
            self.assertListEqual(_extract_args(raw), expectation)

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
        self.assertEqual(_parse_recurse("", self.context, DummyMapping), None)

        # strings. If it is wrapped in quotes, don't parse the contents
        self.assertEqual(_parse_recurse('"foo"', self.context, DummyMapping), "foo")
        self.assertEqual(
            _parse_recurse('"\tf o o\n"', self.context, DummyMapping), "\tf o o\n"
        )
        self.assertEqual(
            _parse_recurse('"foo(a,b)"', self.context, DummyMapping), "foo(a,b)"
        )
        self.assertEqual(_parse_recurse('",,,()"', self.context, DummyMapping), ",,,()")

        # strings without quotes only work as long as there is no function call or
        # anything. This is only really acceptable for constants like KEY_A and for
        # variable names, which are not allowed to contain special characters that may
        # have a meaning in the macro syntax.
        self.assertEqual(_parse_recurse("foo", self.context, DummyMapping), "foo")

        self.assertEqual(_parse_recurse("5", self.context, DummyMapping), 5)
        self.assertEqual(_parse_recurse("5.2", self.context, DummyMapping), 5.2)
        self.assertIsInstance(
            _parse_recurse("$foo", self.context, DummyMapping), Variable
        )
        self.assertEqual(_parse_recurse("$foo", self.context, DummyMapping).name, "foo")

    async def test_0(self):
        macro = parse("key(1)", self.context, DummyMapping)
        one_code = system_mapping.get("1")

        await macro.run(self.handler)
        self.assertListEqual(
            self.result, [(EV_KEY, one_code, 1), (EV_KEY, one_code, 0)]
        )
        self.assertEqual(len(macro.child_macros), 0)

    async def test_1(self):
        macro = parse('key(1).key("KEY_A").key(3)', self.context, DummyMapping)

        await macro.run(self.handler)
        self.assertListEqual(
            self.result,
            [
                (EV_KEY, system_mapping.get("1"), 1),
                (EV_KEY, system_mapping.get("1"), 0),
                (EV_KEY, system_mapping.get("a"), 1),
                (EV_KEY, system_mapping.get("a"), 0),
                (EV_KEY, system_mapping.get("3"), 1),
                (EV_KEY, system_mapping.get("3"), 0),
            ],
        )
        self.assertEqual(len(macro.child_macros), 0)

    async def test_raises_error(self):

        # passing a string parameter. This is not a macro, even though
        # it might look like it without the string quotes.
        self.assertRaises(MacroParsingError, parse, '"modify(a, b)"', self.context)
        parse("k(1).h(k(a)).k(3)", self.context)  # No error
        with self.assertRaises(MacroParsingError) as cm:
            parse("k(1))", self.context)
        error = str(cm.exception)
        self.assertIn("bracket", error)
        with self.assertRaises(MacroParsingError) as cm:
            parse("key((1)", self.context)
        error = str(cm.exception)
        self.assertIn("bracket", error)
        self.assertRaises(MacroParsingError, parse, "k((1).k)", self.context)
        self.assertRaises(MacroParsingError, parse, "k()", self.context)
        parse("key(1)", self.context)  # no error
        self.assertRaises(MacroParsingError, parse, "k(1, 1)", self.context)
        parse("key($a)", self.context)  # no error
        self.assertRaises(MacroParsingError, parse, "h(1, 1)", self.context)
        self.assertRaises(MacroParsingError, parse, "h(hold(h(1, 1)))", self.context)
        self.assertRaises(MacroParsingError, parse, "r(1)", self.context)
        self.assertRaises(MacroParsingError, parse, "repeat(a, k(1))", self.context)
        parse("repeat($a, k(1))", self.context)  # no error
        self.assertRaises(MacroParsingError, parse, "r(1, 1)", self.context)
        self.assertRaises(MacroParsingError, parse, "r(k(1), 1)", self.context)
        parse("r(1, macro=k(1))", self.context)  # no error
        self.assertRaises(MacroParsingError, parse, "r(a=1, b=k(1))", self.context)
        self.assertRaises(
            MacroParsingError, parse, "r(repeats=1, macro=k(1), a=2)", self.context
        )
        self.assertRaises(
            MacroParsingError,
            parse,
            "r(repeats=1, macro=k(1), repeats=2)",
            self.context,
        )
        self.assertRaises(MacroParsingError, parse, "modify(asdf, k(a))", self.context)
        parse("if_tap(, k(a), 1000)", self.context)  # no error
        parse("if_tap(, k(a), timeout=1000)", self.context)  # no error
        parse("if_tap(, k(a), $timeout)", self.context)  # no error
        parse("if_tap(, k(a), timeout=$t)", self.context)  # no error
        parse("if_tap(, key(a))", self.context)  # no error
        parse("if_tap(k(a),)", self.context)  # no error
        self.assertRaises(MacroParsingError, parse, "if_tap(k(a), b)", self.context)
        parse("if_single(k(a),)", self.context)  # no error
        self.assertRaises(MacroParsingError, parse, "if_single(1,)", self.context)
        self.assertRaises(MacroParsingError, parse, "if_single(,1)", self.context)
        parse("mouse(up, 3)", self.context)  # no error
        parse("mouse(up, speed=$a)", self.context)  # no error
        self.assertRaises(MacroParsingError, parse, "mouse(3, up)", self.context)
        parse("wheel(left, 3)", self.context)  # no error
        self.assertRaises(MacroParsingError, parse, "wheel(3, left)", self.context)
        parse("w(2)", self.context)  # no error
        self.assertRaises(MacroParsingError, parse, "wait(a)", self.context)
        parse("ifeq(a, 2, k(a),)", self.context)  # no error
        parse("ifeq(a, 2, , k(a))", self.context)  # no error
        self.assertRaises(MacroParsingError, parse, "ifeq(a, 2, 1,)", self.context)
        self.assertRaises(MacroParsingError, parse, "ifeq(a, 2, , 2)", self.context)
        parse("if_eq(2, $a, k(a),)", self.context)  # no error
        parse("if_eq(2, $a, , else=k(a))", self.context)  # no error
        self.assertRaises(MacroParsingError, parse, "if_eq(2, $a, 1,)", self.context)
        self.assertRaises(MacroParsingError, parse, "if_eq(2, $a, , 2)", self.context)
        with self.assertRaises(MacroParsingError) as cm:
            parse("foo(a)", self.context)
        error = str(cm.exception)
        self.assertIn("unknown", error.lower())
        self.assertIn("foo", error)

        self.assertRaises(MacroParsingError, parse, "set($a, 1)", self.context)
        self.assertRaises(MacroParsingError, parse, "set(1, 2)", self.context)
        self.assertRaises(MacroParsingError, parse, "set(+, 2)", self.context)
        self.assertRaises(MacroParsingError, parse, "set(a(), 2)", self.context)
        self.assertRaises(MacroParsingError, parse, "set('b,c', 2)", self.context)
        self.assertRaises(MacroParsingError, parse, 'set("b,c", 2)', self.context)
        parse("set(A, 2)", self.context)  # no error

    async def test_key(self):
        code_a = system_mapping.get("a")
        code_b = system_mapping.get("b")
        macro = parse("set(foo, b).key($foo).key(a)", self.context, DummyMapping)
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

    async def test_modify(self):
        code_a = system_mapping.get("a")
        code_b = system_mapping.get("b")
        code_c = system_mapping.get("c")
        macro = parse(
            "set(foo, b).modify($foo, modify(a, key(c)))", self.context, DummyMapping
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

    async def test_hold_variable(self):
        code_a = system_mapping.get("a")
        macro = parse("set(foo, a).hold($foo)", self.context, DummyMapping)
        await macro.run(self.handler)
        self.assertListEqual(
            self.result,
            [
                (EV_KEY, code_a, 1),
                (EV_KEY, code_a, 0),
            ],
        )

    async def test_hold_keys(self):
        macro = parse("set(foo, b).hold_keys(a, $foo, c)", self.context, DummyMapping)
        # press first
        macro.press_trigger()
        # then run, just like how it is going to happen during runtime
        asyncio.ensure_future(macro.run(self.handler))

        code_a = system_mapping.get("a")
        code_b = system_mapping.get("b")
        code_c = system_mapping.get("c")

        await asyncio.sleep(0.2)
        self.assertListEqual(
            self.result,
            [
                (EV_KEY, code_a, 1),
                (EV_KEY, code_b, 1),
                (EV_KEY, code_c, 1),
            ],
        )

        macro.release_trigger()

        await asyncio.sleep(0.2)
        self.assertListEqual(
            self.result,
            [
                (EV_KEY, code_a, 1),
                (EV_KEY, code_b, 1),
                (EV_KEY, code_c, 1),
                (EV_KEY, code_c, 0),
                (EV_KEY, code_b, 0),
                (EV_KEY, code_a, 0),
            ],
        )

    async def test_hold(self):
        # repeats key(a) as long as the key is held down
        macro = parse("key(1).hold(key(a)).key(3)", self.context, DummyMapping)

        """down"""

        macro.press_trigger()
        await asyncio.sleep(0.05)
        self.assertTrue(macro.is_holding())

        macro.press_trigger()  # redundantly calling doesn't break anything
        asyncio.ensure_future(macro.run(self.handler))
        await asyncio.sleep(0.2)
        self.assertTrue(macro.is_holding())
        self.assertGreater(len(self.result), 2)

        """up"""

        macro.release_trigger()
        await asyncio.sleep(0.05)
        self.assertFalse(macro.is_holding())

        self.assertEqual(self.result[0], (EV_KEY, system_mapping.get("1"), 1))
        self.assertEqual(self.result[-1], (EV_KEY, system_mapping.get("3"), 0))

        code_a = system_mapping.get("a")
        self.assertGreater(self.result.count((EV_KEY, code_a, 1)), 2)

        self.assertEqual(len(macro.child_macros), 1)

    async def test_dont_hold(self):
        macro = parse("key(1).hold(key(a)).key(3)", self.context, DummyMapping)

        asyncio.ensure_future(macro.run(self.handler))
        await asyncio.sleep(0.2)
        self.assertFalse(macro.is_holding())
        # press_trigger was never called, so the macro completes right away
        # and the child macro of hold is never called.
        self.assertEqual(len(self.result), 4)

        self.assertEqual(self.result[0], (EV_KEY, system_mapping.get("1"), 1))
        self.assertEqual(self.result[-1], (EV_KEY, system_mapping.get("3"), 0))

        self.assertEqual(len(macro.child_macros), 1)

    async def test_just_hold(self):
        macro = parse("key(1).hold().key(3)", self.context, DummyMapping)

        """down"""

        macro.press_trigger()
        asyncio.ensure_future(macro.run(self.handler))
        await (asyncio.sleep(0.1))
        self.assertTrue(macro.is_holding())
        self.assertEqual(len(self.result), 2)
        await (asyncio.sleep(0.1))
        # doesn't do fancy stuff, is blocking until the release
        self.assertEqual(len(self.result), 2)

        """up"""

        macro.release_trigger()
        await (asyncio.sleep(0.05))
        self.assertFalse(macro.is_holding())
        self.assertEqual(len(self.result), 4)

        self.assertEqual(self.result[0], (EV_KEY, system_mapping.get("1"), 1))
        self.assertEqual(self.result[-1], (EV_KEY, system_mapping.get("3"), 0))

        self.assertEqual(len(macro.child_macros), 0)

    async def test_dont_just_hold(self):
        macro = parse("key(1).hold().key(3)", self.context, DummyMapping)

        asyncio.ensure_future(macro.run(self.handler))
        await (asyncio.sleep(0.1))
        self.assertFalse(macro.is_holding())
        # since press_trigger was never called it just does the macro
        # completely
        self.assertEqual(len(self.result), 4)

        self.assertEqual(self.result[0], (EV_KEY, system_mapping.get("1"), 1))
        self.assertEqual(self.result[-1], (EV_KEY, system_mapping.get("3"), 0))

        self.assertEqual(len(macro.child_macros), 0)

    async def test_hold_down(self):
        # writes down and waits for the up event until the key is released
        macro = parse("hold(a)", self.context, DummyMapping)
        self.assertEqual(len(macro.child_macros), 0)

        """down"""

        macro.press_trigger()
        await (asyncio.sleep(0.05))
        self.assertTrue(macro.is_holding())

        asyncio.ensure_future(macro.run(self.handler))
        macro.press_trigger()  # redundantly calling doesn't break anything
        await asyncio.sleep(0.2)
        self.assertTrue(macro.is_holding())
        self.assertEqual(len(self.result), 1)
        self.assertEqual(self.result[0], (EV_KEY, system_mapping.get("a"), 1))

        """up"""

        macro.release_trigger()
        await (asyncio.sleep(0.05))
        self.assertFalse(macro.is_holding())

        self.assertEqual(len(self.result), 2)
        self.assertEqual(self.result[0], (EV_KEY, system_mapping.get("a"), 1))
        self.assertEqual(self.result[1], (EV_KEY, system_mapping.get("a"), 0))

    async def test_2(self):
        start = time.time()
        repeats = 20

        macro = parse(
            f"repeat({repeats}, key(k)).repeat(1, key(k))", self.context, DummyMapping
        )
        k_code = system_mapping.get("k")

        await macro.run(self.handler)
        keystroke_sleep = DummyMapping.macro_key_sleep_ms
        sleep_time = 2 * repeats * keystroke_sleep / 1000
        self.assertGreater(time.time() - start, sleep_time * 0.9)
        self.assertLess(time.time() - start, sleep_time * 1.2)

        self.assertListEqual(
            self.result, [(EV_KEY, k_code, 1), (EV_KEY, k_code, 0)] * (repeats + 1)
        )

        self.assertEqual(len(macro.child_macros), 2)
        self.assertEqual(len(macro.child_macros[0].child_macros), 0)

    async def test_3(self):
        start = time.time()
        macro = parse("repeat(3, key(m).w(100))", self.context, DummyMapping)
        m_code = system_mapping.get("m")
        await macro.run(self.handler)

        keystroke_time = 6 * DummyMapping.macro_key_sleep_ms
        total_time = keystroke_time + 300
        total_time /= 1000

        self.assertGreater(time.time() - start, total_time * 0.9)
        self.assertLess(time.time() - start, total_time * 1.2)
        self.assertListEqual(
            self.result,
            [
                (EV_KEY, m_code, 1),
                (EV_KEY, m_code, 0),
                (EV_KEY, m_code, 1),
                (EV_KEY, m_code, 0),
                (EV_KEY, m_code, 1),
                (EV_KEY, m_code, 0),
            ],
        )
        self.assertEqual(len(macro.child_macros), 1)
        self.assertEqual(len(macro.child_macros[0].child_macros), 0)

    async def test_4(self):
        macro = parse(
            "  repeat(2,\nkey(\nr ).key(minus\n )).key(m)  ", self.context, DummyMapping
        )

        r = system_mapping.get("r")
        minus = system_mapping.get("minus")
        m = system_mapping.get("m")

        await macro.run(self.handler)
        self.assertListEqual(
            self.result,
            [
                (EV_KEY, r, 1),
                (EV_KEY, r, 0),
                (EV_KEY, minus, 1),
                (EV_KEY, minus, 0),
                (EV_KEY, r, 1),
                (EV_KEY, r, 0),
                (EV_KEY, minus, 1),
                (EV_KEY, minus, 0),
                (EV_KEY, m, 1),
                (EV_KEY, m, 0),
            ],
        )
        self.assertEqual(len(macro.child_macros), 1)
        self.assertEqual(len(macro.child_macros[0].child_macros), 0)

    async def test_5(self):
        start = time.time()
        macro = parse(
            "w(200).repeat(2,modify(w,\nrepeat(2,\tkey(BtN_LeFt))).w(10).key(k))",
            self.context,
            DummyMapping,
        )

        self.assertEqual(len(macro.child_macros), 1)
        self.assertEqual(len(macro.child_macros[0].child_macros), 1)

        w = system_mapping.get("w")
        left = system_mapping.get("bTn_lEfT")
        k = system_mapping.get("k")

        await macro.run(self.handler)

        num_pauses = 8 + 6 + 4
        keystroke_time = num_pauses * DummyMapping.macro_key_sleep_ms
        wait_time = 220
        total_time = (keystroke_time + wait_time) / 1000

        self.assertLess(time.time() - start, total_time * 1.2)
        self.assertGreater(time.time() - start, total_time * 0.9)
        expected = [(EV_KEY, w, 1)]
        expected += [(EV_KEY, left, 1), (EV_KEY, left, 0)] * 2
        expected += [(EV_KEY, w, 0)]
        expected += [(EV_KEY, k, 1), (EV_KEY, k, 0)]
        expected *= 2
        self.assertListEqual(self.result, expected)

    async def test_6(self):
        # does nothing without .run
        macro = parse("key(a).repeat(3, key(b))", self.context)
        self.assertIsInstance(macro, Macro)
        self.assertListEqual(self.result, [])

    async def test_duplicate_run(self):
        # it won't restart the macro, because that may screw up the
        # internal state (in particular the _trigger_release_event).
        # I actually don't know at all what kind of bugs that might produce,
        # lets just avoid it. It might cause it to be held down forever.
        a = system_mapping.get("a")
        b = system_mapping.get("b")
        c = system_mapping.get("c")

        macro = parse("key(a).modify(b, hold()).key(c)", self.context, DummyMapping)
        asyncio.ensure_future(macro.run(self.handler))
        self.assertFalse(macro.is_holding())

        asyncio.ensure_future(macro.run(self.handler))  # ignored
        self.assertFalse(macro.is_holding())

        macro.press_trigger()
        await asyncio.sleep(0.2)
        self.assertTrue(macro.is_holding())

        asyncio.ensure_future(macro.run(self.handler))  # ignored
        self.assertTrue(macro.is_holding())

        macro.release_trigger()
        await asyncio.sleep(0.2)
        self.assertFalse(macro.is_holding())

        expected = [
            (EV_KEY, a, 1),
            (EV_KEY, a, 0),
            (EV_KEY, b, 1),
            (EV_KEY, b, 0),
            (EV_KEY, c, 1),
            (EV_KEY, c, 0),
        ]
        self.assertListEqual(self.result, expected)

        """not ignored, since previous run is over"""

        asyncio.ensure_future(macro.run(self.handler))
        macro.press_trigger()
        await asyncio.sleep(0.2)
        self.assertTrue(macro.is_holding())
        macro.release_trigger()
        await asyncio.sleep(0.2)
        self.assertFalse(macro.is_holding())

        expected = [
            (EV_KEY, a, 1),
            (EV_KEY, a, 0),
            (EV_KEY, b, 1),
            (EV_KEY, b, 0),
            (EV_KEY, c, 1),
            (EV_KEY, c, 0),
        ] * 2
        self.assertListEqual(self.result, expected)

    async def test_mouse(self):
        wheel_speed = 60
        macro_1 = parse("mouse(up, 4)", self.context, DummyMapping)
        macro_2 = parse(f"wheel(left, {wheel_speed})", self.context, DummyMapping)
        macro_1.press_trigger()
        macro_2.press_trigger()
        asyncio.ensure_future(macro_1.run(self.handler))
        asyncio.ensure_future(macro_2.run(self.handler))

        sleep = 0.1
        await (asyncio.sleep(sleep))
        self.assertTrue(macro_1.is_holding())
        self.assertTrue(macro_2.is_holding())
        macro_1.release_trigger()
        macro_2.release_trigger()

        self.assertIn((EV_REL, REL_Y, -4), self.result)
        expected_wheel_hi_res_event_count = sleep * DummyMapping.rate
        expected_wheel_event_count = int(expected_wheel_hi_res_event_count / 120 * wheel_speed)
        actual_wheel_event_count = self.result.count((EV_REL, REL_HWHEEL, 1))
        actual_wheel_hi_res_event_count = self.result.count((EV_REL, REL_HWHEEL_HI_RES, wheel_speed))
        # this seems to have a tendency of injecting less wheel events,
        # especially if the sleep is short
        self.assertGreater(actual_wheel_event_count, expected_wheel_event_count * 0.8)
        self.assertLess(actual_wheel_event_count, expected_wheel_event_count * 1.1)
        self.assertGreater(actual_wheel_hi_res_event_count, expected_wheel_hi_res_event_count * 0.8)
        self.assertLess(actual_wheel_hi_res_event_count, expected_wheel_hi_res_event_count * 1.1)

    async def test_event_1(self):
        macro = parse("e(EV_KEY, KEY_A, 1)", self.context, DummyMapping)
        a_code = system_mapping.get("a")

        await macro.run(self.handler)
        self.assertListEqual(self.result, [(EV_KEY, a_code, 1)])
        self.assertEqual(len(macro.child_macros), 0)

    async def test_event_2(self):
        macro = parse(
            "repeat(1, event(type=5421, code=324, value=154))",
            self.context,
            DummyMapping,
        )
        code = 324

        await macro.run(self.handler)
        self.assertListEqual(self.result, [(5421, code, 154)])
        self.assertEqual(len(macro.child_macros), 1)

    async def test_macro_breaks(self):
        # the first parameter for `repeat` requires an integer, not "foo",
        # which makes `repeat` throw
        macro = parse(
            'set(a, "foo").repeat($a, key(KEY_A)).key(KEY_B)',
            self.context,
            DummyMapping,
        )
        await macro.run(self.handler)

        # .run() it will not throw because repeat() breaks, and it will properly set
        # it to stopped
        self.assertFalse(macro.running)

        # key(KEY_B) is not executed, the macro stops
        self.assertListEqual(self.result, [])

    async def test_set(self):
        await parse('set(a, "foo")', self.context, DummyMapping).run(self.handler)
        self.assertEqual(macro_variables.get("a"), "foo")

        await parse('set( \t"b" \n, "1")', self.context, DummyMapping).run(self.handler)
        self.assertEqual(macro_variables.get("b"), "1")

        await parse("set(a, 1)", self.context, DummyMapping).run(self.handler)
        self.assertEqual(macro_variables.get("a"), 1)

        await parse("set(a, )", self.context, DummyMapping).run(self.handler)
        self.assertEqual(macro_variables.get("a"), None)

    async def test_multiline_macro_and_comments(self):
        # the parser is not confused by the code in the comments and can use hashtags
        # in strings in the actual code
        comment = '# repeat(1,key(KEY_D)).set(a,"#b")'
        macro = parse(
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


class TestIfEq(MacroTestBase):
    async def test_ifeq_runs(self):
        # deprecated ifeq function, but kept for compatibility reasons
        macro = parse(
            "set(foo, 2).ifeq(foo, 2, key(a), key(b))", self.context, DummyMapping
        )
        code_a = system_mapping.get("a")
        code_b = system_mapping.get("b")

        await macro.run(self.handler)
        self.assertListEqual(self.result, [(EV_KEY, code_a, 1), (EV_KEY, code_a, 0)])
        self.assertEqual(len(macro.child_macros), 2)

    async def test_ifeq_none(self):
        # first param none
        macro = parse("set(foo, 2).ifeq(foo, 2, , key(b))", self.context, DummyMapping)
        self.assertEqual(len(macro.child_macros), 1)
        code_b = system_mapping.get("b")
        await macro.run(self.handler)
        self.assertListEqual(self.result, [])

        # second param none
        macro = parse("set(foo, 2).ifeq(foo, 2, key(a),)", self.context, DummyMapping)
        self.assertEqual(len(macro.child_macros), 1)
        code_a = system_mapping.get("a")
        await macro.run(self.handler)
        self.assertListEqual(self.result, [(EV_KEY, code_a, 1), (EV_KEY, code_a, 0)])

    async def test_ifeq_unknown_key(self):
        macro = parse("ifeq(qux, 2, key(a), key(b))", self.context, DummyMapping)
        code_a = system_mapping.get("a")
        code_b = system_mapping.get("b")

        await macro.run(self.handler)
        self.assertListEqual(self.result, [(EV_KEY, code_b, 1), (EV_KEY, code_b, 0)])
        self.assertEqual(len(macro.child_macros), 2)

    async def test_if_eq(self):
        """new version of ifeq"""
        code_a = system_mapping.get("a")
        code_b = system_mapping.get("b")
        a_press = [(EV_KEY, code_a, 1), (EV_KEY, code_a, 0)]
        b_press = [(EV_KEY, code_b, 1), (EV_KEY, code_b, 0)]

        async def test(macro, expected):
            # cleanup
            macro_variables._clear()
            self.assertIsNone(macro_variables.get("a"))
            self.result.clear()

            # test
            macro = parse(macro, self.context, DummyMapping)
            await macro.run(self.handler)
            self.assertListEqual(self.result, expected)

        await test("if_eq(1, 1, key(a), key(b))", a_press)
        await test("if_eq(1, 2, key(a), key(b))", b_press)
        await test("if_eq(value_1=1, value_2=1, then=key(a), else=key(b))", a_press)
        await test('set(a, "foo").if_eq($a, "foo", key(a), key(b))', a_press)
        await test('set(a, "foo").if_eq("foo", $a, key(a), key(b))', a_press)
        await test('set(a, "foo").if_eq("foo", $a, , key(b))', [])
        await test('set(a, "qux").if_eq("foo", $a, key(a), key(b))', b_press)
        await test('set(a, "qux").if_eq($a, "foo", key(a), key(b))', b_press)
        await test('set(a, "qux").if_eq($a, "foo", key(a), )', [])
        await test('set(a, "x").set(b, "y").if_eq($b, $a, key(a), key(b))', b_press)
        await test('set(a, "x").set(b, "y").if_eq($b, $a, key(a), )', [])
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
        macro = parse("if_eq($foo, 3, key(a), key(b))", self.context, DummyMapping)
        code_a = system_mapping.get("a")
        code_b = system_mapping.get("b")

        self.assertEqual(len(macro.child_macros), 2)

        def set_foo(value):
            # will write foo = 2 into the shared dictionary of macros
            macro_2 = parse(f"set(foo, {value})", self.context, DummyMapping)
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


class TestIfSingle(MacroTestBase):
    async def test_if_single(self):
        macro = parse("if_single(key(x), key(y))", self.context, DummyMapping)
        self.assertEqual(len(macro.child_macros), 2)

        a = system_mapping.get("a")

        x = system_mapping.get("x")
        y = system_mapping.get("y")

        await self.trigger_sequence(macro, new_event(EV_KEY, a, 1))
        await asyncio.sleep(0.1)
        await self.release_sequence(macro, new_event(EV_KEY, a, 0))
        # the key that triggered the macro is released
        await asyncio.sleep(0.1)

        self.assertListEqual(self.result, [(EV_KEY, x, 1), (EV_KEY, x, 0)])
        self.assertFalse(macro.running)

    async def test_if_single_ignores_releases(self):
        # the timeout won't break the macro, everything happens well within that
        # timeframe.
        macro = parse(
            "if_single(key(x), else=key(y), timeout=100000)", self.context, DummyMapping
        )
        self.assertEqual(len(macro.child_macros), 2)

        a = system_mapping.get("a")
        b = system_mapping.get("b")

        x = system_mapping.get("x")
        y = system_mapping.get("y")

        # pressing the macro key
        await self.trigger_sequence(macro, new_event(EV_KEY, a, 1))
        await asyncio.sleep(0.05)

        # if_single only looks out for newly pressed keys,
        # it doesn't care if keys were released that have been
        # pressed before if_single. This was decided because it is a lot
        # less tricky and more fluently to use if you type fast
        for listener in self.context.listeners:
            asyncio.ensure_future(listener(new_event(EV_KEY, b, 0)))
        await asyncio.sleep(0.05)
        self.assertListEqual(self.result, [])

        # releasing the actual key triggers if_single
        await asyncio.sleep(0.05)
        await self.release_sequence(macro, new_event(EV_KEY, a, 0))
        await asyncio.sleep(0.05)
        self.assertListEqual(self.result, [(EV_KEY, x, 1), (EV_KEY, x, 0)])
        self.assertFalse(macro.running)

    async def test_if_not_single(self):
        # Will run the `else` macro if another key is pressed.
        # Also works if if_single is a child macro, i.e. the event is passed to it
        # from the outside macro correctly.
        macro = parse(
            "repeat(1, if_single(then=key(x), else=key(y)))", self.context, DummyMapping
        )
        self.assertEqual(len(macro.child_macros), 1)
        self.assertEqual(len(macro.child_macros[0].child_macros), 2)

        a = system_mapping.get("a")
        b = system_mapping.get("b")

        x = system_mapping.get("x")
        y = system_mapping.get("y")

        # press the trigger key
        await self.trigger_sequence(macro, new_event(EV_KEY, a, 1))
        await asyncio.sleep(0.1)
        # press another key
        for listener in self.context.listeners:
            asyncio.ensure_future(listener(new_event(EV_KEY, b, 1)))
        await asyncio.sleep(0.1)

        self.assertListEqual(self.result, [(EV_KEY, y, 1), (EV_KEY, y, 0)])
        self.assertFalse(macro.running)

    async def test_if_not_single_none(self):
        macro = parse("if_single(key(x),)", self.context, DummyMapping)
        self.assertEqual(len(macro.child_macros), 1)

        a = system_mapping.get("a")
        b = system_mapping.get("b")

        x = system_mapping.get("x")

        # press trigger key
        await self.trigger_sequence(macro, new_event(EV_KEY, a, 1))
        await asyncio.sleep(0.1)
        # press another key
        for listener in self.context.listeners:
            asyncio.ensure_future(listener(new_event(EV_KEY, b, 1)))
        await asyncio.sleep(0.1)

        self.assertListEqual(self.result, [])
        self.assertFalse(macro.running)

    async def test_if_single_times_out(self):
        macro = parse(
            "set(t, 300).if_single(key(x), key(y), timeout=$t)",
            self.context,
            DummyMapping,
        )
        self.assertEqual(len(macro.child_macros), 2)

        a = system_mapping.get("a")
        y = system_mapping.get("y")

        await self.trigger_sequence(macro, new_event(EV_KEY, a, 1))

        # no timeout yet
        await asyncio.sleep(0.2)
        self.assertListEqual(self.result, [])
        self.assertTrue(macro.running)

        # times out now
        await asyncio.sleep(0.2)
        self.assertListEqual(self.result, [(EV_KEY, y, 1), (EV_KEY, y, 0)])
        self.assertFalse(macro.running)

    async def test_if_single_ignores_joystick(self):
        """triggers else + delayed_handle_keycode"""
        # Integration test style for if_single.
        # If a joystick that is mapped to a button is moved, if_single stops
        macro = parse("if_single(k(a), k(KEY_LEFTSHIFT))", self.context, DummyMapping)
        code_shift = system_mapping.get("KEY_LEFTSHIFT")
        code_a = system_mapping.get("a")
        trigger = 1

        await self.trigger_sequence(macro, new_event(EV_KEY, trigger, 1))
        await asyncio.sleep(0.1)
        for listener in self.context.listeners:
            asyncio.ensure_future(listener(new_event(EV_ABS, ABS_Y, 10)))
        await asyncio.sleep(0.1)
        await self.release_sequence(macro, new_event(EV_KEY, trigger, 0))
        await asyncio.sleep(0.1)
        self.assertFalse(macro.running)
        self.assertListEqual(self.result, [(EV_KEY, code_a, 1), (EV_KEY, code_a, 0)])


class TestIfTap(MacroTestBase):
    async def test_if_tap(self):
        macro = parse("if_tap(key(x), key(y), 100)", self.context, DummyMapping)
        self.assertEqual(len(macro.child_macros), 2)

        x = system_mapping.get("x")
        y = system_mapping.get("y")

        # this is the regular routine of how a macro is started. the tigger is pressed
        # already when the macro runs, and released during if_tap within the timeout.
        macro.press_trigger()
        asyncio.ensure_future(macro.run(self.handler))
        await asyncio.sleep(0.05)
        macro.release_trigger()
        await asyncio.sleep(0.05)

        self.assertListEqual(self.result, [(EV_KEY, x, 1), (EV_KEY, x, 0)])
        self.assertFalse(macro.running)

    async def test_if_tap_2(self):
        # when the press arrives shortly after run.
        # a tap will happen within the timeout even if the tigger is not pressed when
        # it does into if_tap
        macro = parse("if_tap(key(a), key(b), 100)", self.context, DummyMapping)
        asyncio.ensure_future(macro.run(self.handler))

        await asyncio.sleep(0.01)
        macro.press_trigger()
        await asyncio.sleep(0.01)
        macro.release_trigger()
        await asyncio.sleep(0.2)
        self.assertListEqual(self.result, [(EV_KEY, KEY_A, 1), (EV_KEY, KEY_A, 0)])
        self.assertFalse(macro.running)
        self.result.clear()

    async def test_if_double_tap(self):
        macro = parse(
            "if_tap(if_tap(key(a), key(b), 100), key(c), 100)",
            self.context,
            DummyMapping,
        )
        self.assertEqual(len(macro.child_macros), 2)
        self.assertEqual(len(macro.child_macros[0].child_macros), 2)

        asyncio.ensure_future(macro.run(self.handler))

        # first tap
        macro.press_trigger()
        await asyncio.sleep(0.05)
        macro.release_trigger()

        # second tap
        await asyncio.sleep(0.04)
        macro.press_trigger()
        await asyncio.sleep(0.04)
        macro.release_trigger()

        await asyncio.sleep(0.05)
        self.assertListEqual(self.result, [(EV_KEY, KEY_A, 1), (EV_KEY, KEY_A, 0)])
        self.assertFalse(macro.running)
        self.result.clear()

        """If the second tap takes too long, runs else there"""

        asyncio.ensure_future(macro.run(self.handler))

        # first tap
        macro.press_trigger()
        await asyncio.sleep(0.05)
        macro.release_trigger()

        # second tap
        await asyncio.sleep(0.06)
        macro.press_trigger()
        await asyncio.sleep(0.06)
        macro.release_trigger()

        await asyncio.sleep(0.05)
        self.assertListEqual(self.result, [(EV_KEY, KEY_B, 1), (EV_KEY, KEY_B, 0)])
        self.assertFalse(macro.running)
        self.result.clear()

    async def test_if_tap_none(self):
        # first param none
        macro = parse("if_tap(, key(y), 100)", self.context, DummyMapping)
        self.assertEqual(len(macro.child_macros), 1)
        y = system_mapping.get("y")
        macro.press_trigger()
        asyncio.ensure_future(macro.run(self.handler))
        await asyncio.sleep(0.05)
        macro.release_trigger()
        await asyncio.sleep(0.05)
        self.assertListEqual(self.result, [])

        # second param none
        macro = parse("if_tap(key(y), , 50)", self.context)
        self.assertEqual(len(macro.child_macros), 1)
        y = system_mapping.get("y")
        macro.press_trigger()
        asyncio.ensure_future(macro.run(self.handler))
        await asyncio.sleep(0.1)
        macro.release_trigger()
        await asyncio.sleep(0.05)
        self.assertListEqual(self.result, [])

        self.assertFalse(macro.running)

    async def test_if_not_tap(self):
        macro = parse("if_tap(key(x), key(y), 50)", self.context, DummyMapping)
        self.assertEqual(len(macro.child_macros), 2)

        x = system_mapping.get("x")
        y = system_mapping.get("y")

        macro.press_trigger()
        asyncio.ensure_future(macro.run(self.handler))
        await asyncio.sleep(0.1)
        macro.release_trigger()
        await asyncio.sleep(0.05)

        self.assertListEqual(self.result, [(EV_KEY, y, 1), (EV_KEY, y, 0)])
        self.assertFalse(macro.running)

    async def test_if_not_tap_named(self):
        macro = parse("if_tap(key(x), key(y), timeout=50)", self.context, DummyMapping)
        self.assertEqual(len(macro.child_macros), 2)

        x = system_mapping.get("x")
        y = system_mapping.get("y")

        macro.press_trigger()
        asyncio.ensure_future(macro.run(self.handler))
        await asyncio.sleep(0.1)
        macro.release_trigger()
        await asyncio.sleep(0.05)

        self.assertListEqual(self.result, [(EV_KEY, y, 1), (EV_KEY, y, 0)])
        self.assertFalse(macro.running)


if __name__ == "__main__":
    unittest.main()
