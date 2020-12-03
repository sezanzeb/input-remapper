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
from evdev.events import EV_KEY, EV_ABS

from keymapper.mapping import Mapping
from keymapper.state import populate_system_mapping


class TestMapping(unittest.TestCase):
    def setUp(self):
        self.mapping = Mapping()
        self.assertFalse(self.mapping.changed)

    def test_populate_system_mapping(self):
        # not actually a mapping object, just a dict
        mapping = populate_system_mapping()
        self.assertGreater(len(mapping), 100)
        self.assertEqual(mapping['1'], 2)
        self.assertEqual(mapping['KEY_1'], 2)

        self.assertEqual(mapping['Alt_L'], 56)
        self.assertEqual(mapping['KEY_LEFTALT'], 56)

        self.assertEqual(mapping['KEY_LEFTSHIFT'], 42)
        self.assertEqual(mapping['Shift_L'], 42)

    def test_clone(self):
        mapping1 = Mapping()
        mapping1.change((EV_KEY, 1), 'a')
        mapping2 = mapping1.clone()
        mapping1.change((EV_KEY, 2), 'b')

        self.assertEqual(mapping1.get_character(EV_KEY, 1), 'a')
        self.assertEqual(mapping1.get_character(EV_KEY, 2), 'b')

        self.assertEqual(mapping2.get_character(EV_KEY, 1), 'a')
        self.assertIsNone(mapping2.get_character(EV_KEY, 2))

    def test_save_load(self):
        self.mapping.change((EV_KEY, 10), '1')
        self.mapping.change((EV_KEY, 11), '2')
        self.mapping.change((EV_KEY, 12), '3')
        self.mapping.config['foo'] = 'bar'
        self.mapping.save('device 1', 'test')

        loaded = Mapping()
        self.assertEqual(len(loaded), 0)
        loaded.load('device 1', 'test')

        self.assertEqual(len(loaded), 3)
        self.assertEqual(loaded.get_character(EV_KEY, 10), '1')
        self.assertEqual(loaded.get_character(EV_KEY, 11), '2')
        self.assertEqual(loaded.get_character(EV_KEY, 12), '3')
        self.assertEqual(loaded.config['foo'], 'bar')

    def test_change(self):
        # 1 is not assigned yet, ignore it
        self.mapping.change((EV_KEY, 2), 'a', (EV_KEY, 1))
        self.assertTrue(self.mapping.changed)
        self.assertIsNone(self.mapping.get_character(EV_KEY, 1))
        self.assertEqual(self.mapping.get_character(EV_KEY, 2), 'a')
        self.assertEqual(len(self.mapping), 1)

        # change KEY 2 to ABS 16 and change a to b
        self.mapping.change((EV_ABS, 16), 'b', (EV_KEY, 2))
        self.assertIsNone(self.mapping.get_character(EV_KEY, 2))
        self.assertEqual(self.mapping.get_character(EV_ABS, 16), 'b')
        self.assertEqual(len(self.mapping), 1)

        # add 4
        self.mapping.change((EV_KEY, 4), 'c', (None, None))
        self.assertEqual(self.mapping.get_character(EV_ABS, 16), 'b')
        self.assertEqual(self.mapping.get_character(EV_KEY, 4), 'c')
        self.assertEqual(len(self.mapping), 2)

        # change the mapping of 4 to d
        self.mapping.change((EV_KEY, 4), 'd', (None, None))
        self.assertEqual(self.mapping.get_character(EV_KEY, 4), 'd')
        self.assertEqual(len(self.mapping), 2)

        # this also works in the same way
        self.mapping.change((EV_KEY, 4), 'e', (EV_KEY, 4))
        self.assertEqual(self.mapping.get_character(EV_KEY, 4), 'e')
        self.assertEqual(len(self.mapping), 2)

        # and this
        self.mapping.change((EV_KEY, '4'), 'f', (str(EV_KEY), '4'))
        self.assertEqual(self.mapping.get_character(EV_KEY, 4), 'f')
        self.assertEqual(len(self.mapping), 2)

        # non-int keycodes are ignored
        self.mapping.change((EV_KEY, 'b'), 'c', (EV_KEY, 'a'))
        self.mapping.change((EV_KEY, 'b'), 'c')
        self.mapping.change(('foo', 1), 'c', ('foo', 2))
        self.mapping.change(('foo', 1), 'c')
        self.assertEqual(len(self.mapping), 2)

    def test_change_2(self):
        self.mapping.change((EV_KEY, 2), 'a')

        self.mapping.change((None, 2), 'b', (EV_KEY, 2))
        self.assertEqual(self.mapping.get_character(EV_KEY, 2), 'a')

        self.mapping.change((EV_KEY, None), 'c', (EV_KEY, 2))
        self.assertEqual(self.mapping.get_character(EV_KEY, 2), 'a')

        self.assertEqual(len(self.mapping), 1)

    def test_clear(self):
        # does nothing
        self.mapping.clear(EV_KEY, 40)
        self.assertFalse(self.mapping.changed)
        self.assertEqual(len(self.mapping), 0)

        self.mapping._mapping[(EV_KEY, 40)] = 'b'
        self.assertEqual(len(self.mapping), 1)
        self.mapping.clear(EV_KEY, 40)
        self.assertEqual(len(self.mapping), 0)
        self.assertTrue(self.mapping.changed)

        self.mapping.change((EV_KEY, 10), 'KP_1', (None, None))
        self.assertTrue(self.mapping.changed)
        self.mapping.change((EV_KEY, 20), 'KP_2', (None, None))
        self.mapping.change((EV_KEY, 30), 'KP_3', (None, None))
        self.assertEqual(len(self.mapping), 3)
        self.mapping.clear(EV_KEY, 20)
        self.assertEqual(len(self.mapping), 2)
        self.assertEqual(self.mapping.get_character(EV_KEY, 10), 'KP_1')
        self.assertIsNone(self.mapping.get_character(EV_KEY, 20))
        self.assertEqual(self.mapping.get_character(EV_KEY, 30), 'KP_3')

    def test_empty(self):
        self.mapping.change((EV_KEY, 10), '1')
        self.mapping.change((EV_KEY, 11), '2')
        self.mapping.change((EV_KEY, 12), '3')
        self.assertEqual(len(self.mapping), 3)
        self.mapping.empty()
        self.assertEqual(len(self.mapping), 0)


if __name__ == "__main__":
    unittest.main()
