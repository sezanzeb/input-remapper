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

from inputremapper.gui_v3.block_ops import (
    ChainPath,
    can_move,
    default_call,
    first_gap,
    get_chain,
    insert_call,
    move_call,
    remove_call,
    remove_spread_arg,
    set_arg,
)
from inputremapper.gui_v3.macro_text import parse_text, print_chain
from inputremapper.gui_v3.schema import SCHEMA
from inputremapper.gui_v3.tree import Call, Var


def text(chain: tuple[Call, ...]) -> str:
    return print_chain(chain)


class TestBlockOps(unittest.TestCase):
    def test_every_block_has_a_default_that_prints(self) -> None:
        for op in SCHEMA:
            call = default_call(op)
            self.assertEqual(call.op, op)
            print_chain((call,))

    def test_new_key_blocks_start_empty_and_block_applying(self) -> None:
        from inputremapper.gui_v3.document import Entry, InputRef, Trigger
        from inputremapper.gui_v3.render import RenderError, entry_to_mapping

        def entry(*then: Call) -> Entry:
            return Entry(trigger=Trigger(inputs=(InputRef(1, 30),)), then=then)

        self.assertEqual(default_call("key_down").args, ("",))
        for call in (
            default_call("key_down"),
            default_call("set"),
            default_call("repeat"),
            Call.make("repeat", 2, (default_call("key"),)),
        ):
            with self.assertRaises(RenderError):
                entry_to_mapping(entry(call))
        entry_to_mapping(entry(Call.make("key_down", "BTN_LEFT")))

    def test_insert_and_remove_at_top_level(self) -> None:
        chain = parse_text("key(a).key(c)")
        chain = insert_call(chain, (), 1, Call.make("key", "b"))
        self.assertEqual(text(chain), "key(a).key(b).key(c)")
        chain = remove_call(chain, (), 0)
        self.assertEqual(text(chain), "key(b).key(c)")

    def test_insert_into_a_nested_stack(self) -> None:
        chain = parse_text("repeat(2, key(a))")
        chain = insert_call(chain, ((0, 1),), 1, Call.make("key", "b"))
        self.assertEqual(text(chain), "repeat(2, key(a).key(b))")

    def test_filling_and_emptying_an_optional_slot(self) -> None:
        chain = (Call.make("if_eq", Var("x"), 1),)
        chain = insert_call(chain, ((0, 2),), 0, Call.make("key", "a"))
        self.assertEqual(text(chain), "if_eq($x, 1, key(a))")
        chain = remove_call(chain, ((0, 2),), 0)
        self.assertEqual(chain, (Call.make("if_eq", Var("x"), 1),))

    def test_the_else_slot_can_be_filled_while_then_is_empty(self) -> None:
        chain = (Call.make("if_eq", Var("x"), 1),)
        chain = insert_call(chain, ((0, 3),), 0, Call.make("key", "b"))
        self.assertEqual(text(chain), "if_eq($x, 1, None, key(b))")
        self.assertEqual(get_chain(chain, ((0, 2),)), ())

    def test_set_arg_keeps_defaults_trimmed(self) -> None:
        chain = parse_text("wait(50)")
        chain = set_arg(chain, (), 0, 0, 80)
        self.assertEqual(text(chain), "wait(80)")
        chain = set_arg(chain, (), 0, 1, 120)
        self.assertEqual(text(chain), "wait(80, 120)")
        chain = set_arg(chain, (), 0, 1, None)
        self.assertEqual(text(chain), "wait(80)")

    def test_move_within_a_stack(self) -> None:
        chain = parse_text("key(a).key(b).key(c)")
        # Dragging a to the gap below b: gaps are numbered before the move.
        self.assertEqual(text(move_call(chain, (), 0, (), 2)), "key(b).key(a).key(c)")
        self.assertEqual(text(move_call(chain, (), 2, (), 0)), "key(c).key(a).key(b)")
        # Dropping next to itself changes nothing.
        self.assertEqual(move_call(chain, (), 1, (), 1), chain)
        self.assertEqual(move_call(chain, (), 1, (), 2), chain)

    def test_move_into_and_out_of_a_nested_stack(self) -> None:
        chain = parse_text("key(a).repeat(2, key(b))")
        inside: ChainPath = ((1, 1),)
        moved = move_call(chain, (), 0, inside, 0)
        self.assertEqual(text(moved), "repeat(2, key(a).key(b))")
        # Index shift: the repeat block moves up once key(a) has left.
        back = move_call(moved, ((0, 1),), 0, (), 1)
        self.assertEqual(text(back), "repeat(2, key(b)).key(a)")

    def test_cannot_move_a_block_into_itself(self) -> None:
        chain = parse_text("repeat(2, key(a))")
        self.assertFalse(can_move((), 0, ((0, 1),)))
        with self.assertRaises(ValueError):
            move_call(chain, (), 0, ((0, 1),), 0)

    def test_spread_blocks(self) -> None:
        chain = (default_call("hold_keys"),)
        chain = set_arg(chain, (), 0, 0, "KEY_A")
        chain = set_arg(chain, (), 0, 1, "KEY_B")
        self.assertEqual(text(chain), "hold_keys(KEY_A, KEY_B)")
        chain = remove_spread_arg(chain, (), 0, 0)
        self.assertEqual(text(chain), "hold_keys(KEY_B)")


if __name__ == "__main__":
    unittest.main()


class TestOutputKey(unittest.TestCase):
    def test_output_key_must_stand_alone(self):
        key = default_call("symbol")
        self.assertIn("no key", first_gap((key,)))
        key = Call("symbol", ("KEY_A",))
        self.assertIsNone(first_gap((key,)))
        self.assertIn("combined", first_gap((key, Call("wait", (10,)))))
        nested = set_arg((default_call("repeat"),), (), 0, 1, (key,))
        self.assertIn("combined", first_gap(nested))
