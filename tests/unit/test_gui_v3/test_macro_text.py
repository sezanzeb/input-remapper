# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2026 sezanzeb <4t1pzast9@mozmail.com>
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

from inputremapper.gui_v3.macro_text import (
    MacroTextError,
    format_chain,
    parse_text,
    print_chain,
)
from inputremapper.gui_v3.tree import (
    Call,
    Var,
    chain_from_json,
    chain_to_json,
)
from inputremapper.injection.macros.parse import Parser
from tests.lib.test_setup import test_setup

CANONICAL = [
    "key(KEY_A)",
    "key(KEY_A).wait(40)",
    "wait(10, 20)",
    "set(clicking, 1).while_eq($clicking, 1, key(KEY_SPACE).wait(40))",
    "if_eq($mode, 2, key(KEY_B), wait(10))",
    "if_eq($mode, 2, None, key(KEY_B))",
    "repeat(3, key(a).wait(10))",
    "hold_keys(KEY_LEFTCTRL, KEY_C)",
    "parallel(key(a), key(b).wait(5))",
    "if_tap(key(a), key(b), 250)",
    "add(counter, 2)",
    "set(name, hello)",
    'if_eq($name, "1", key(a))',
    "mouse(up, 5)",
    "mouse(up, 5, 2.5)",
    "hold(KEY_A)",
    "mod_tap(KEY_A, KEY_LEFTSHIFT)",
]


@test_setup
class TestMacroText(unittest.TestCase):
    def test_print_parse_round_trip(self):
        for code in CANONICAL:
            with self.subTest(code=code):
                chain = parse_text(code)
                self.assertEqual(print_chain(chain), code)
                self.assertEqual(parse_text(print_chain(chain)), chain)

    def test_printed_output_is_accepted_by_the_engine(self):
        for code in CANONICAL:
            with self.subTest(code=code):
                Parser.parse(print_chain(parse_text(code)), verbose=False)

    def test_json_round_trip(self):
        for code in CANONICAL:
            with self.subTest(code=code):
                chain = parse_text(code)
                self.assertEqual(chain_from_json(chain_to_json(chain)), chain)

    def test_tree_shape(self):
        chain = parse_text(
            "set(clicking, 1).while_eq($clicking, 1, key(KEY_SPACE).wait(40))"
        )
        self.assertEqual(
            chain,
            (
                Call("set", (Var("clicking"), 1)),
                Call(
                    "while_eq",
                    (
                        Var("clicking"),
                        1,
                        (Call("key", ("KEY_SPACE",)), Call("wait", (40,))),
                    ),
                ),
            ),
        )

    def test_aliases_and_keyword_arguments_are_normalized(self):
        self.assertEqual(
            print_chain(parse_text("k(a).w(10)")),
            "key(a).wait(10)",
        )
        self.assertEqual(
            print_chain(parse_text("wait(max_time=20, time=10)")),
            "wait(10, 20)",
        )

    def test_quoted_words_are_the_same_as_bare_words(self):
        self.assertEqual(
            parse_text('set(name, "hello")'), parse_text("set(name, hello)")
        )

    def test_default_arguments_are_dropped(self):
        self.assertEqual(parse_text("mouse(up, 5, 1)"), parse_text("mouse(up, 5)"))

    def test_whitespace_and_comments(self):
        code = """
            key(a)   # tap a
              .wait(10)
        """
        self.assertEqual(print_chain(parse_text(code)), "key(a).wait(10)")

    def test_plus_syntax(self):
        self.assertEqual(print_chain(parse_text("a + b")), "hold_keys(a, b)")

    def test_plain_symbol_is_kept_verbatim(self):
        chain = parse_text("KEY_ESC")
        self.assertEqual(chain, (Call("symbol", ("KEY_ESC",)),))
        self.assertEqual(print_chain(chain), "KEY_ESC")

    def test_unknown_function_survives_as_raw(self):
        chain = parse_text("key(a).future_thing(1, 2).wait(5)")
        self.assertEqual(chain[1], Call("raw", ("future_thing(1,2)",)))
        self.assertEqual(print_chain(chain), "key(a).future_thing(1,2).wait(5)")

    def test_errors(self):
        for code in ["key(a", "wait()", "wait(1, 2, 3)", "key(a)b", "wait(foo=1)"]:
            with self.subTest(code=code), self.assertRaises(MacroTextError):
                parse_text(code)

    def test_format_chain_lays_out_nested_macros(self):
        compact = (
            "set(whipping, 1).key_down(BTN_LEFT).while_eq($whipping, 1, "
            "key(4).wait(700).if_eq($whipping, 1, key(1).wait(1500))).key_up(BTN_LEFT)"
        )
        expected = """set(whipping, 1)
  .key_down(BTN_LEFT)
  .while_eq($whipping, 1,
    key(4)
      .wait(700)
      .if_eq($whipping, 1, key(1).wait(1500)))
  .key_up(BTN_LEFT)"""
        chain = parse_text(compact)
        self.assertEqual(format_chain(chain), expected)
        # It is the same macro: the layout is gone once the engine cleans it.
        self.assertEqual(parse_text(expected), chain)
        self.assertEqual(Parser.clean(expected), Parser.clean(compact))

    def test_format_chain_keeps_short_macros_on_one_line(self):
        for code in CANONICAL:
            chain = parse_text(code)
            self.assertEqual(parse_text(format_chain(chain)), chain, code)
        self.assertEqual(format_chain(parse_text("key(a).wait(10)")), "key(a).wait(10)")
        self.assertEqual(
            format_chain(parse_text("repeat(3, key(a).wait(10))")),
            "repeat(3, key(a).wait(10))",
        )
        self.assertEqual(format_chain(()), "")


if __name__ == "__main__":
    unittest.main()
