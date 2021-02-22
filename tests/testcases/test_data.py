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
import os
import pkg_resources

from keymapper.data import get_data_path


class TestData(unittest.TestCase):
    def test_data_editable(self):
        path = os.getcwd()
        pkg_resources.require('key-mapper')[0].location = path
        self.assertEqual(get_data_path(), path + '/data/')
        self.assertEqual(get_data_path('a'), path + '/data/a')

    def test_data_usr(self):
        path = '/usr/some/where/python3.8/dist-packages/'
        pkg_resources.require('key-mapper')[0].location = path

        self.assertTrue(get_data_path().startswith('/usr/'))
        self.assertTrue(get_data_path().endswith('key-mapper/'))

        self.assertTrue(get_data_path('a').startswith('/usr/'))
        self.assertTrue(get_data_path('a').endswith('key-mapper/a'))


if __name__ == "__main__":
    unittest.main()
