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
from keymapper.state import populate_system_mapping


class TestMapping(unittest.TestCase):
    def setUp(self):
        self.mapping = Mapping()
        self.assertFalse(self.mapping.changed)

    def test_populate_system_mapping(self):
        mapping = populate_system_mapping()
        self.assertGreater(len(mapping), 100)
        # xkb keycode 10 is typically mapped to '1'
        self.assertEqual(mapping['1'], 10)
        # linux keycodes are properly increased to the xkb keycodes
        self.assertEqual(mapping['KEY_1'], 10)
        self.assertEqual(mapping['KEY_LEFTSHIFT'], mapping['Shift_L'])

    def test_clone(self):
        mapping1 = Mapping()
        mapping1.change(1, 'a')
        mapping2 = mapping1.clone()
        mapping1.change(2, 'b')

        self.assertEqual(mapping1.get_character(1), 'a')
        self.assertEqual(mapping1.get_character(2), 'b')

        self.assertEqual(mapping2.get_character(1), 'a')
        self.assertIsNone(mapping2.get_character(2))

    def test_save_load(self):
        self.mapping.change(10, '1')
        self.mapping.change(11, '2')
        self.mapping.change(12, '3')
        self.mapping.save('device 1', 'test')
        loaded = Mapping()
        self.assertEqual(len(loaded), 0)
        loaded.load('device 1', 'test')
        self.assertEqual(len(loaded), 3)
        self.assertEqual(loaded.get_character(10), '1')
        self.assertEqual(loaded.get_character(11), '2')
        self.assertEqual(loaded.get_character(12), '3')

    def test_change(self):
        # 1 is not assigned yet, ignore it
        self.mapping.change(2, 'a', 1)
        self.assertTrue(self.mapping.changed)
        self.assertIsNone(self.mapping.get_character(1))
        self.assertEqual(self.mapping.get_character(2), 'a')
        self.assertEqual(len(self.mapping), 1)

        # change 2 to 3 and change a to b
        self.mapping.change(3, 'b', 2)
        self.assertIsNone(self.mapping.get_character(2))
        self.assertEqual(self.mapping.get_character(3), 'b')
        self.assertEqual(len(self.mapping), 1)

        # add 4
        self.mapping.change(4, 'c', None)
        self.assertEqual(self.mapping.get_character(3), 'b')
        self.assertEqual(self.mapping.get_character(4), 'c')
        self.assertEqual(len(self.mapping), 2)

        # change the mapping of 4 to d
        self.mapping.change(4, 'd', None)
        self.assertEqual(self.mapping.get_character(4), 'd')
        self.assertEqual(len(self.mapping), 2)

        # this also works in the same way
        self.mapping.change(4, 'e', 4)
        self.assertEqual(self.mapping.get_character(4), 'e')
        self.assertEqual(len(self.mapping), 2)

        # and this
        self.mapping.change('4', 'f', '4')
        self.assertEqual(self.mapping.get_character(4), 'f')
        self.assertEqual(len(self.mapping), 2)

        # non-int keycodes are ignored
        self.mapping.change('b', 'c', 'a')
        self.assertEqual(len(self.mapping), 2)

    def test_clear(self):
        # does nothing
        self.mapping.clear(40)
        self.assertFalse(self.mapping.changed)
        self.assertEqual(len(self.mapping), 0)

        self.mapping._mapping[40] = 'b'
        self.assertEqual(len(self.mapping), 1)
        self.mapping.clear(40)
        self.assertEqual(len(self.mapping), 0)
        self.assertTrue(self.mapping.changed)

        self.mapping.change(10, 'KP_1', None)
        self.assertTrue(self.mapping.changed)
        self.mapping.change(20, 'KP_2', None)
        self.mapping.change(30, 'KP_3', None)
        self.assertEqual(len(self.mapping), 3)
        self.mapping.clear(20)
        self.assertEqual(len(self.mapping), 2)
        self.assertEqual(self.mapping.get_character(10), 'KP_1')
        self.assertIsNone(self.mapping.get_character(20))
        self.assertEqual(self.mapping.get_character(30), 'KP_3')

    def test_empty(self):
        self.mapping.change(10, '1')
        self.mapping.change(11, '2')
        self.mapping.change(12, '3')
        self.assertEqual(len(self.mapping), 3)
        self.mapping.empty()
        self.assertEqual(len(self.mapping), 0)


if __name__ == "__main__":
    unittest.main()
