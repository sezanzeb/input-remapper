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

from keymapper.X import Mapping


class TestMapping(unittest.TestCase):
    def setUp(self):
        self.mapping = Mapping()

    def test_change(self):
        # 1 is not assigned yet, just add it
        self.mapping.change(1, 2, 'a')
        self.assertIsNone(self.mapping.get(1))
        self.assertEqual(self.mapping.get(2), 'a')
        self.assertEqual(len(self.mapping), 1)

        # change 2 to 3 and change a to b
        self.mapping.change(2, 3, 'b')
        self.assertIsNone(self.mapping.get(2))
        self.assertEqual(self.mapping.get(3), 'b')
        self.assertEqual(len(self.mapping), 1)

        # add 4
        self.mapping.change(None, 4, 'c')
        self.assertEqual(self.mapping.get(3), 'b')
        self.assertEqual(self.mapping.get(4), 'c')
        self.assertEqual(len(self.mapping), 2)

        # change the mapping of 4 to d
        self.mapping.change(None, 4, 'd')
        self.assertEqual(self.mapping.get(4), 'd')
        self.assertEqual(len(self.mapping), 2)

        # this also works in the same way
        self.mapping.change(4, 4, 'e')
        self.assertEqual(self.mapping.get(4), 'e')
        self.assertEqual(len(self.mapping), 2)

    def test_clear(self):
        self.mapping.change(None, 10, 'NUM1')
        self.mapping.change(None, 20, 'NUM2')
        self.mapping.change(None, 30, 'NUM3')
        self.mapping.clear(20)
        self.assertEqual(self.mapping.get(10), 'NUM1')
        self.assertIsNone(self.mapping.get(20))
        self.assertEqual(self.mapping.get(30), 'NUM3')


if __name__ == "__main__":
    unittest.main()
