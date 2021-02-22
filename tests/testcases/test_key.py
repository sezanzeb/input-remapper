#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@sezanzeb.de>
#
# This file is part of key-mapper.
#
# key-mapper is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# key-mapper is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with key-mapper.  If not, see <https://www.gnu.org/licenses/>.


import unittest

from evdev.ecodes import KEY_LEFTSHIFT, KEY_RIGHTALT, KEY_LEFTCTRL

from keymapper.key import Key


class TestKey(unittest.TestCase):
    def test_key(self):
        # its very similar to regular tuples, but with some extra stuff
        key_1 = Key((1, 3, 1), (1, 5, 1))
        self.assertEqual(str(key_1), 'Key((1, 3, 1), (1, 5, 1))')
        self.assertEqual(len(key_1), 2)
        self.assertEqual(key_1[0], (1, 3, 1))
        self.assertEqual(key_1[1], (1, 5, 1))
        self.assertEqual(hash(key_1), hash(((1, 3, 1), (1, 5, 1))))

        key_2 = Key((1, 3, 1))
        self.assertEqual(str(key_2), 'Key((1, 3, 1),)')
        self.assertEqual(len(key_2), 1)
        self.assertNotEqual(key_2, key_1)
        self.assertNotEqual(hash(key_2), hash(key_1))

        key_3 = Key(1, 3, 1)
        self.assertEqual(str(key_3), 'Key((1, 3, 1),)')
        self.assertEqual(len(key_3), 1)
        self.assertEqual(key_3, key_2)
        self.assertEqual(key_3, (1, 3, 1))
        self.assertEqual(hash(key_3), hash(key_2))
        self.assertEqual(hash(key_3), hash((1, 3, 1)))

        key_4 = Key(key_3)
        self.assertEqual(str(key_4), 'Key((1, 3, 1),)')
        self.assertEqual(len(key_4), 1)
        self.assertEqual(key_4, key_3)
        self.assertEqual(hash(key_4), hash(key_3))

        key_5 = Key(key_4, key_4, (1, 7, 1))
        self.assertEqual(str(key_5), 'Key((1, 3, 1), (1, 3, 1), (1, 7, 1))')
        self.assertEqual(len(key_5), 3)
        self.assertNotEqual(key_5, key_4)
        self.assertNotEqual(hash(key_5), hash(key_4))
        self.assertEqual(key_5, ((1, 3, 1), (1, 3, 1), (1, 7, 1)))
        self.assertEqual(hash(key_5), hash(((1, 3, 1), (1, 3, 1), (1, 7, 1))))

    def test_get_permutations(self):
        key_1 = Key((1, 3, 1))
        self.assertEqual(len(key_1.get_permutations()), 1)
        self.assertEqual(key_1.get_permutations()[0], key_1)

        key_2 = Key((1, 3, 1), (1, 5, 1))
        self.assertEqual(len(key_2.get_permutations()), 1)
        self.assertEqual(key_2.get_permutations()[0], key_2)

        key_3 = Key((1, 3, 1), (1, 5, 1), (1, 7, 1))
        self.assertEqual(len(key_3.get_permutations()), 2)
        self.assertEqual(
            key_3.get_permutations()[0],
            Key((1, 3, 1), (1, 5, 1), (1, 7, 1))
        )
        self.assertEqual(
            key_3.get_permutations()[1],
            ((1, 5, 1), (1, 3, 1), (1, 7, 1))
        )

    def test_is_problematic(self):
        key_1 = Key((1, KEY_LEFTSHIFT, 1), (1, 5, 1))
        self.assertTrue(key_1.is_problematic())

        key_2 = Key((1, KEY_RIGHTALT, 1), (1, 5, 1))
        self.assertTrue(key_2.is_problematic())

        key_3 = Key((1, 3, 1), (1, KEY_LEFTCTRL, 1))
        self.assertTrue(key_3.is_problematic())

        key_4 = Key(1, 3, 1)
        self.assertFalse(key_4.is_problematic())

        key_5 = Key((1, 3, 1), (1, 5, 1))
        self.assertFalse(key_5.is_problematic())


if __name__ == "__main__":
    unittest.main()
