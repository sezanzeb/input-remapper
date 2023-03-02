#!/usr/bin/python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2023 sezanzeb <proxima@sezanzeb.de>
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
import os
import pkg_resources

from inputremapper.configs.data import get_data_path


class TestData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_location = pkg_resources.require("input-remapper")[0].location

    def tearDown(self):
        pkg_resources.require("input-remapper")[0].location = self.original_location

    def test_data_editable(self):
        path = os.getcwd().replace("/tests/integration", "")
        pkg_resources.require("input-remapper")[0].location = path
        self.assertEqual(get_data_path(), path + "/data/")
        self.assertEqual(get_data_path("a"), path + "/data/a")

    def test_data_usr(self):
        path = "/usr/some/where/python3.8/dist-packages/"
        pkg_resources.require("input-remapper")[0].location = path

        self.assertTrue(get_data_path().startswith("/usr/"))
        self.assertTrue(get_data_path().endswith("input-remapper/"))

        self.assertTrue(get_data_path("a").startswith("/usr/"))
        self.assertTrue(get_data_path("a").endswith("input-remapper/a"))


if __name__ == "__main__":
    unittest.main()
