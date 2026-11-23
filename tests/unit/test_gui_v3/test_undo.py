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

from inputremapper.gui_v3.undo import History


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class TestHistory(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.history = History("a", clock=self.clock)

    def test_undo_redo(self):
        self.history.commit("b")
        self.history.commit("c")
        self.assertEqual(self.history.undo(), "b")
        self.assertEqual(self.history.undo(), "a")
        self.assertFalse(self.history.can_undo)
        self.assertEqual(self.history.undo(), "a")
        self.assertEqual(self.history.redo(), "b")
        self.assertEqual(self.history.redo(), "c")
        self.assertFalse(self.history.can_redo)

    def test_commit_after_undo_drops_redo(self):
        self.history.commit("b")
        self.history.undo()
        self.history.commit("c")
        self.assertFalse(self.history.can_redo)
        self.assertEqual(self.history.undo(), "a")

    def test_unchanged_state_is_not_recorded(self):
        self.assertFalse(self.history.commit("a"))
        self.assertFalse(self.history.can_undo)

    def test_merge_key_coalesces_quick_edits(self):
        self.history.commit("b")
        self.history.commit("bc", merge_key="name")
        self.clock.now = 0.5
        self.history.commit("bcd", merge_key="name")
        self.assertEqual(self.history.undo(), "b")
        self.assertEqual(self.history.undo(), "a")

    def test_merge_key_does_not_coalesce_after_pause_or_other_key(self):
        self.history.commit("b", merge_key="name")
        self.history.commit("bc", merge_key="name")
        self.clock.now = 5
        self.history.commit("bcd", merge_key="name")
        self.history.commit("bcde", merge_key="other")
        self.assertEqual(self.history.undo(), "bcd")
        self.assertEqual(self.history.undo(), "bc")

    def test_undo_breaks_merging(self):
        self.history.commit("b")
        self.history.commit("c", merge_key="k")
        self.history.undo()
        self.history.redo()
        self.history.commit("d", merge_key="k")
        self.assertEqual(self.history.undo(), "c")

    def test_limit(self):
        history = History(0, limit=3, clock=self.clock)
        for i in range(1, 10):
            history.commit(i)
        self.assertEqual(history.undo(), 8)
        self.assertEqual(history.undo(), 7)
        self.assertFalse(history.can_undo)


if __name__ == "__main__":
    unittest.main()
