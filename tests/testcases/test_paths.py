#!/usr/bin/python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@sezanzeb.de>
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

from inputremapper.paths import touch, mkdir, get_preset_path, get_config_path

from tests.test import quick_cleanup, tmp


def _raise(error):
    raise error


class TestPaths(unittest.TestCase):
    def tearDown(self):
        quick_cleanup()

    def test_touch(self):
        touch("/tmp/a/b/c/d/e")
        self.assertTrue(os.path.exists("/tmp/a/b/c/d/e"))
        self.assertTrue(os.path.isfile("/tmp/a/b/c/d/e"))
        self.assertRaises(ValueError, lambda: touch("/tmp/a/b/c/d/f/"))

    def test_mkdir(self):
        mkdir("/tmp/b/c/d/e")
        self.assertTrue(os.path.exists("/tmp/b/c/d/e"))
        self.assertTrue(os.path.isdir("/tmp/b/c/d/e"))

    def test_get_preset_path(self):
        self.assertEqual(get_preset_path(), os.path.join(tmp, "presets"))
        self.assertEqual(get_preset_path("a"), os.path.join(tmp, "presets/a"))
        self.assertEqual(
            get_preset_path("a", "b"), os.path.join(tmp, "presets/a/b.json")
        )

    def test_get_config_path(self):
        self.assertEqual(get_config_path(), tmp)
        self.assertEqual(get_config_path("a", "b"), os.path.join(tmp, "a/b"))
