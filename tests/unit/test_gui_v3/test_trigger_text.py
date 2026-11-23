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

from evdev import ecodes

from inputremapper.gui_v3.document import InputRef
from inputremapper.gui_v3.trigger_text import parse_trigger, print_trigger


class TestTriggerText(unittest.TestCase):
    def test_parse_combination(self) -> None:
        self.assertEqual(
            parse_trigger("KEY_LEFTCTRL + a"),
            (
                InputRef(1, ecodes.KEY_LEFTCTRL),
                InputRef(1, ecodes.KEY_A),
            ),
        )

    def test_buttons(self) -> None:
        self.assertEqual(parse_trigger("btn_left"), (InputRef(1, ecodes.BTN_LEFT),))

    def test_unknown_key(self) -> None:
        with self.assertRaises(ValueError):
            parse_trigger("KEY_NOPE")

    def test_round_trip(self) -> None:
        text = "KEY_LEFTCTRL + KEY_A"
        self.assertEqual(print_trigger(parse_trigger(text)), text)

    def test_empty(self) -> None:
        self.assertEqual(parse_trigger("  "), ())


if __name__ == "__main__":
    unittest.main()
