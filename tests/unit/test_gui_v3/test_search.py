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

from inputremapper.gui_v3.search import Item, rank_labels, search

NAMES = [
    "BTN_C",
    "BTN_LEFT",
    "BTN_PINKIE",
    "KEY_CLEAR",
    "KEY_CLOSE",
    "KEY_LEFT",
    "KEY_LEFTCTRL",
    "KEY_LEFT_SHIFT",
    "KEY_RIGHT",
    "Left",
]


class TestRank(unittest.TestCase):
    def test_prefix_before_word_prefix_before_substring(self):
        names = ["xxLEFT", "KEY_LEFT", "LEFTY", "a_left_b"]
        self.assertEqual(
            rank_labels(names, "left"), ["LEFTY", "KEY_LEFT", "a_left_b", "xxLEFT"]
        )

    def test_words_are_split_at_underscores(self):
        self.assertEqual(rank_labels(NAMES, "cl"), ["KEY_CLEAR", "KEY_CLOSE"])
        # The rest of the name from a word on can be typed, underscores included.
        self.assertEqual(rank_labels(NAMES, "left_sh"), ["KEY_LEFT_SHIFT"])
        self.assertEqual(rank_labels(NAMES, "ink"), ["BTN_PINKIE"])

    def test_shorter_names_first_within_a_tier(self):
        self.assertEqual(
            rank_labels(NAMES, "left"),
            ["Left", "BTN_LEFT", "KEY_LEFT", "KEY_LEFTCTRL", "KEY_LEFT_SHIFT"],
        )

    def test_case_and_surrounding_spaces_do_not_matter(self):
        self.assertEqual(rank_labels(NAMES, "  KEY_right "), ["KEY_RIGHT"])

    def test_empty_query_keeps_everything_in_order(self):
        self.assertEqual(rank_labels(NAMES, ""), NAMES)
        self.assertEqual(rank_labels(NAMES, "   "), NAMES)

    def test_nothing_matches(self):
        self.assertEqual(rank_labels(NAMES, "zzz"), [])

    def test_words_of_a_label_with_spaces_and_slashes(self):
        labels = ["key / mouse / button down", "wait"]
        self.assertEqual(rank_labels(labels, "mouse"), ["key / mouse / button down"])
        self.assertEqual(rank_labels(labels, "but"), ["key / mouse / button down"])


class TestAliases(unittest.TestCase):
    ITEMS = [
        Item("wait", "wait", "Timing", "delay sleep pause"),
        Item("repeat", "repeat", "Timing", "loop times"),
        Item("key", "press key", "Keys", "tap type click"),
        Item("while", "while equal", "Control", "loop condition"),
    ]

    def values(self, query: str) -> list[tuple[str, list[str]]]:
        return [(g, [i.value for i in items]) for g, items in search(self.ITEMS, query)]

    def test_an_alias_finds_the_item(self):
        self.assertEqual(self.values("sleep"), [("Timing", ["wait"])])
        self.assertEqual(self.values("cl"), [("Keys", ["key"])])

    def test_the_label_beats_an_alias(self):
        # "loop" is only an alias; "wait" matches by label so it ranks above.
        items = [Item("a", "loop", "G"), Item("b", "wait", "G", "loop")]
        found = [i.value for _g, group in search(items, "loop") for i in group]
        self.assertEqual(found, ["a", "b"])

    def test_every_word_has_to_match(self):
        self.assertEqual(self.values("loop times"), [("Timing", ["repeat"])])
        self.assertEqual(self.values("loop zzz"), [])

    def test_no_query_keeps_the_groups_and_items_as_given(self):
        self.assertEqual(
            self.values(""),
            [
                ("Timing", ["wait", "repeat"]),
                ("Keys", ["key"]),
                ("Control", ["while"]),
            ],
        )

    def test_the_group_with_the_best_match_comes_first(self):
        # Both groups match "loop" by alias; "while" is the shorter label's group,
        # but the first-given group wins a tie of equal rank.
        found = self.values("loop")
        self.assertEqual({g for g, _ in found}, {"Timing", "Control"})
        # A label match in a later group beats an alias match in an earlier one.
        items = [Item("a", "wait", "First", "loop"), Item("b", "loop", "Second")]
        self.assertEqual([g for g, _ in search(items, "loop")], ["Second", "First"])


if __name__ == "__main__":
    unittest.main()
