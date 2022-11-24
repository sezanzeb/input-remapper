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


from tests.lib.cleanup import quick_cleanup
from tests.lib.tmp import tmp

import os
import unittest
import tempfile

from inputremapper.configs.paths import (
    touch,
    mkdir,
    get_preset_path,
    get_config_path,
    split_all,
)


def _raise(error):
    raise error


class TestPaths(unittest.TestCase):
    def tearDown(self):
        quick_cleanup()

    def test_touch(self):
        with tempfile.TemporaryDirectory() as local_tmp:
            path_abcde = os.path.join(local_tmp, "a/b/c/d/e")
            touch(path_abcde)
            self.assertTrue(os.path.exists(path_abcde))
            self.assertTrue(os.path.isfile(path_abcde))
            self.assertRaises(
                ValueError,
                lambda: touch(os.path.join(local_tmp, "a/b/c/d/f/")),
            )

    def test_mkdir(self):
        with tempfile.TemporaryDirectory() as local_tmp:
            path_bcde = os.path.join(local_tmp, "b/c/d/e")
            mkdir(path_bcde)
            self.assertTrue(os.path.exists(path_bcde))
            self.assertTrue(os.path.isdir(path_bcde))

    def test_get_preset_path(self):
        self.assertTrue(get_preset_path().startswith(get_config_path()))
        self.assertTrue(get_preset_path().endswith("presets"))
        self.assertTrue(get_preset_path("a").endswith("presets/a"))
        self.assertTrue(get_preset_path("a", "b").endswith("presets/a/b.json"))

    def test_get_config_path(self):
        # might end with /beta_XXX
        self.assertTrue(get_config_path().startswith(f"{tmp}/.config/input-remapper"))
        self.assertTrue(get_config_path("a", "b").endswith("a/b"))

    def test_split_all(self):
        self.assertListEqual(split_all("a/b/c/d"), ["a", "b", "c", "d"])
