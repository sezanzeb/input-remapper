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


import unittest

from evdev.ecodes import KEY_LEFTSHIFT, KEY_RIGHTALT, KEY_LEFTCTRL

from inputremapper.event_combination import EventCombination
from inputremapper.input_event import InputEvent


class TestKey(unittest.TestCase):
    def test_key(self):
        # its very similar to regular tuples, but with some extra stuff
        key_1 = EventCombination((1, 3, 1), (1, 5, 1))
        self.assertEqual(len(key_1), 2)
        self.assertEqual(key_1[0], (1, 3, 1))
        self.assertEqual(key_1[1], (1, 5, 1))
        self.assertEqual(hash(key_1), hash(((1, 3, 1), (1, 5, 1))))

        key_2 = EventCombination((1, 3, 1))
        self.assertEqual(len(key_2), 1)
        self.assertNotEqual(key_2, key_1)
        self.assertNotEqual(hash(key_2), hash(key_1))

        key_3 = EventCombination((1, 3, 1))
        self.assertEqual(len(key_3), 1)
        self.assertEqual(key_3, key_2)
        self.assertNotEqual(key_3, (1, 3, 1))
        self.assertEqual(hash(key_3), hash(key_2))
        self.assertEqual(hash(key_3), hash(((1, 3, 1),)))

        key_4 = EventCombination(*key_3)
        self.assertEqual(len(key_4), 1)
        self.assertEqual(key_4, key_3)
        self.assertEqual(hash(key_4), hash(key_3))

        key_5 = EventCombination(*key_4, *key_4, (1, 7, 1))
        self.assertEqual(len(key_5), 3)
        self.assertNotEqual(key_5, key_4)
        self.assertNotEqual(hash(key_5), hash(key_4))
        self.assertEqual(key_5, ((1, 3, 1), (1, 3, 1), (1, 7, 1)))
        self.assertEqual(hash(key_5), hash(((1, 3, 1), (1, 3, 1), (1, 7, 1))))

    def test_get_permutations(self):
        key_1 = EventCombination((1, 3, 1))
        self.assertEqual(len(key_1.get_permutations()), 1)
        self.assertEqual(key_1.get_permutations()[0], key_1)

        key_2 = EventCombination((1, 3, 1), (1, 5, 1))
        self.assertEqual(len(key_2.get_permutations()), 1)
        self.assertEqual(key_2.get_permutations()[0], key_2)

        key_3 = EventCombination((1, 3, 1), (1, 5, 1), (1, 7, 1))
        self.assertEqual(len(key_3.get_permutations()), 2)
        self.assertEqual(
            key_3.get_permutations()[0],
            EventCombination((1, 3, 1), (1, 5, 1), (1, 7, 1)),
        )
        self.assertEqual(key_3.get_permutations()[1], ((1, 5, 1), (1, 3, 1), (1, 7, 1)))

    def test_is_problematic(self):
        key_1 = EventCombination((1, KEY_LEFTSHIFT, 1), (1, 5, 1))
        self.assertTrue(key_1.is_problematic())

        key_2 = EventCombination((1, KEY_RIGHTALT, 1), (1, 5, 1))
        self.assertTrue(key_2.is_problematic())

        key_3 = EventCombination((1, 3, 1), (1, KEY_LEFTCTRL, 1))
        self.assertTrue(key_3.is_problematic())

        key_4 = EventCombination((1, 3, 1))
        self.assertFalse(key_4.is_problematic())

        key_5 = EventCombination((1, 3, 1), (1, 5, 1))
        self.assertFalse(key_5.is_problematic())

    def test_init(self):
        self.assertRaises(ValueError, lambda: EventCombination(1))
        self.assertRaises(ValueError, lambda: EventCombination(None))
        self.assertRaises(ValueError, lambda: EventCombination([1]))
        self.assertRaises(ValueError, lambda: EventCombination((1,)))
        self.assertRaises(ValueError, lambda: EventCombination((1, 2)))
        self.assertRaises(ValueError, lambda: EventCombination("1"))
        self.assertRaises(ValueError, lambda: EventCombination("(1,2,3)"))
        self.assertRaises(
            ValueError, lambda: EventCombination((1, 2, 3), (1, 2, 3), None)
        )

        # those don't raise errors
        EventCombination((1, 2, 3), (1, 2, 3))
        EventCombination((1, 2, 3))
        EventCombination(("1", "2", "3"))
        EventCombination("1, 2, 3")
        EventCombination("1, 2, 3", (1, 3, 4), InputEvent.from_string(" 1,5 , 1 "))
        EventCombination((1, 2, 3), (1, 2, "3"))

    def test_json_str(self):
        c1 = EventCombination((1, 2, 3))
        c2 = EventCombination((1, 2, 3), (4, 5, 6))
        self.assertEqual(c1.json_str(), "1,2,3")
        self.assertEqual(c2.json_str(), "1,2,3+4,5,6")


if __name__ == "__main__":
    unittest.main()
