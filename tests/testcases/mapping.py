#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2020 sezanzeb <proxima@hip70890b.de>
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

from keymapper.mapping import Mapping


class TestMapping(unittest.TestCase):
    def setUp(self):
        self.mapping = Mapping()
        self.assertFalse(self.mapping.changed)

    def test_change(self):
        # 1 is not assigned yet, ignore it
        self.mapping.change(1, 2, 'a')
        self.assertTrue(self.mapping.changed)
        self.assertIsNone(self.mapping.get_character(1))
        self.assertEqual(self.mapping.get_character(2), 'a')
        self.assertEqual(self.mapping.get_keycode('a'), 2)
        self.assertEqual(len(self.mapping), 1)

        # change 2 to 3 and change a to b
        self.mapping.change(2, 3, 'b')
        self.assertIsNone(self.mapping.get_character(2))
        self.assertEqual(self.mapping.get_character(3), 'b')
        self.assertEqual(self.mapping.get_keycode('b'), 3)
        self.assertEqual(len(self.mapping), 1)

        # add 4
        self.mapping.change(None, 4, 'c')
        self.assertEqual(self.mapping.get_character(3), 'b')
        self.assertEqual(self.mapping.get_character(4), 'c')
        self.assertEqual(self.mapping.get_keycode('c'), 4)
        self.assertEqual(len(self.mapping), 2)

        # change the mapping of 4 to d
        self.mapping.change(None, 4, 'd')
        self.assertEqual(self.mapping.get_character(4), 'd')
        self.assertEqual(self.mapping.get_keycode('d'), 4)
        self.assertEqual(len(self.mapping), 2)

        # this also works in the same way
        self.mapping.change(4, 4, 'e')
        self.assertEqual(self.mapping.get_character(4), 'e')
        self.assertEqual(self.mapping.get_keycode('e'), 4)
        self.assertEqual(len(self.mapping), 2)

        # and this
        self.mapping.change('4', '4', 'f')
        self.assertEqual(self.mapping.get_character(4), 'f')
        self.assertEqual(self.mapping.get_keycode('f'), 4)
        self.assertEqual(len(self.mapping), 2)

        # non-int keycodes are ignored
        self.mapping.change('a', 'b', 'c')
        self.assertEqual(len(self.mapping), 2)

    def test_clear(self):
        # does nothing
        self.mapping.clear(40)
        self.assertFalse(self.mapping.changed)

        self.mapping._mapping[40] = 'b'
        self.mapping.clear(40)
        self.assertTrue(self.mapping.changed)

        self.mapping.change(None, 10, 'KP_1')
        self.assertTrue(self.mapping.changed)
        self.mapping.change(None, 20, 'KP_2')
        self.mapping.change(None, 30, 'KP_3')
        self.mapping.clear(20)
        self.assertEqual(self.mapping.get_character(10), 'KP_1')
        self.assertIsNone(self.mapping.get_character(20))
        self.assertEqual(self.mapping.get_character(30), 'KP_3')


if __name__ == "__main__":
    unittest.main()
