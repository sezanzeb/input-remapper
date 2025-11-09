#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2025 sezanzeb <b8x45ygc9@mozmail.com>
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

import os
import unittest
from unittest.mock import patch

import pkg_resources

from inputremapper.configs.data import get_data_path
from tests.lib.test_setup import test_setup

egg_info_distribution = pkg_resources.require("input-remapper")[0]

project_root = os.getcwd().replace("/tests/integration", "")


@test_setup
class TestData(unittest.TestCase):
    @patch.object(egg_info_distribution, "location", project_root)
    def test_data_editable(self):
        self.assertEqual(get_data_path(), project_root + "/data/")
        self.assertEqual(get_data_path("a"), project_root + "/data/a")

    @patch.object(
        egg_info_distribution,
        "location",
        "/usr/some/where/python3.8/dist-packages/",
    )
    def test_data_usr(self):
        self.assertTrue(get_data_path().startswith("/usr/"))
        self.assertTrue(get_data_path().endswith("input-remapper/"))

        self.assertTrue(get_data_path("a").startswith("/usr/"))
        self.assertTrue(get_data_path("a").endswith("input-remapper/a"))


if __name__ == "__main__":
    unittest.main()
