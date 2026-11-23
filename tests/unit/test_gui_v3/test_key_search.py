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

from inputremapper.gui_v3.key_search import key_group, key_items
from inputremapper.gui_v3.search import search


class TestKeySearch(unittest.TestCase):
    def test_the_kind_of_device(self):
        self.assertEqual(key_group("KEY_A"), "Keyboard")
        self.assertEqual(key_group("a"), "Keyboard")
        self.assertEqual(key_group("BTN_LEFT"), "Mouse")
        self.assertEqual(key_group("btn_side"), "Mouse")
        self.assertEqual(key_group("BTN_SOUTH"), "Gamepad")

    def test_no_query_lists_every_group_in_order(self):
        items = key_items(["BTN_SOUTH", "KEY_B", "BTN_LEFT", "KEY_A"])
        self.assertEqual(
            [(g, [i.value for i in found]) for g, found in search(items, "")],
            [
                ("Keyboard", ["KEY_B", "KEY_A"]),
                ("Mouse", ["BTN_LEFT"]),
                ("Gamepad", ["BTN_SOUTH"]),
            ],
        )

    def test_the_group_with_the_best_match_comes_first(self):
        items = key_items(
            ["BTN_C", "KEY_CLEAR", "KEY_LEFT", "BTN_LEFT", "KEY_LEFTSHIFT"]
        )

        def groups(query: str):
            return [(g, [i.value for i in found]) for g, found in search(items, query)]

        # Equal matches in both: the group order breaks the tie.
        self.assertEqual(
            groups("left"),
            [("Keyboard", ["KEY_LEFT", "KEY_LEFTSHIFT"]), ("Mouse", ["BTN_LEFT"])],
        )
        # The gamepad button has the shorter match, and its group goes first.
        self.assertEqual(
            groups("c"), [("Gamepad", ["BTN_C"]), ("Keyboard", ["KEY_CLEAR"])]
        )
        self.assertEqual(groups("zzz"), [])


if __name__ == "__main__":
    unittest.main()
