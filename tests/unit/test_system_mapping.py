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

import json
import os
import subprocess
import unittest
from unittest.mock import patch

from evdev.ecodes import BTN_LEFT, KEY_A

from inputremapper.configs.paths import CONFIG_PATH
from inputremapper.configs.system_mapping import SystemMapping, XMODMAP_FILENAME
from tests.lib.cleanup import quick_cleanup


class TestSystemMapping(unittest.TestCase):
    def tearDown(self):
        quick_cleanup()

    def test_update(self):
        system_mapping = SystemMapping()
        system_mapping.update({"foo1": 101, "bar1": 102})
        system_mapping.update({"foo2": 201, "bar2": 202})
        self.assertEqual(system_mapping.get("foo1"), 101)
        self.assertEqual(system_mapping.get("bar2"), 202)

    def test_xmodmap_file(self):
        system_mapping = SystemMapping()
        path = os.path.join(CONFIG_PATH, XMODMAP_FILENAME)
        os.remove(path)

        system_mapping.populate()
        self.assertTrue(os.path.exists(path))
        with open(path, "r") as file:
            content = json.load(file)
            self.assertEqual(content["a"], KEY_A)
            # only xmodmap stuff should be present
            self.assertNotIn("key_a", content)
            self.assertNotIn("KEY_A", content)
            self.assertNotIn("disable", content)

    def test_empty_xmodmap(self):
        # if xmodmap returns nothing, don't write the file
        empty_xmodmap = ""

        class SubprocessMock:
            def decode(self):
                return empty_xmodmap

        def check_output(*args, **kwargs):
            return SubprocessMock()

        with patch.object(subprocess, "check_output", check_output):
            system_mapping = SystemMapping()
            path = os.path.join(CONFIG_PATH, XMODMAP_FILENAME)
            os.remove(path)

            system_mapping.populate()
            self.assertFalse(os.path.exists(path))

    def test_xmodmap_command_missing(self):
        # if xmodmap is not installed, don't write the file
        def check_output(*args, **kwargs):
            raise FileNotFoundError

        with patch.object(subprocess, "check_output", check_output):
            system_mapping = SystemMapping()
            path = os.path.join(CONFIG_PATH, XMODMAP_FILENAME)
            os.remove(path)

            system_mapping.populate()
            self.assertFalse(os.path.exists(path))

    def test_correct_case(self):
        system_mapping = SystemMapping()
        system_mapping.clear()
        system_mapping._set("A", 31)
        system_mapping._set("a", 32)
        system_mapping._set("abcd_B", 33)

        self.assertEqual(system_mapping.correct_case("a"), "a")
        self.assertEqual(system_mapping.correct_case("A"), "A")
        self.assertEqual(system_mapping.correct_case("ABCD_b"), "abcd_B")
        # unknown stuff is returned as is
        self.assertEqual(system_mapping.correct_case("FOo"), "FOo")

        self.assertEqual(system_mapping.get("A"), 31)
        self.assertEqual(system_mapping.get("a"), 32)
        self.assertEqual(system_mapping.get("ABCD_b"), 33)
        self.assertEqual(system_mapping.get("abcd_B"), 33)

    def test_system_mapping(self):
        system_mapping = SystemMapping()
        system_mapping.populate()
        self.assertGreater(len(system_mapping._mapping), 100)

        # this is case-insensitive
        self.assertEqual(system_mapping.get("1"), 2)
        self.assertEqual(system_mapping.get("KeY_1"), 2)

        self.assertEqual(system_mapping.get("AlT_L"), 56)
        self.assertEqual(system_mapping.get("KEy_LEFtALT"), 56)

        self.assertEqual(system_mapping.get("kEY_LeFTSHIFT"), 42)
        self.assertEqual(system_mapping.get("ShiFt_L"), 42)

        self.assertEqual(system_mapping.get("BTN_left"), 272)

        self.assertIsNotNone(system_mapping.get("KEY_KP4"))
        self.assertEqual(system_mapping.get("KP_Left"), system_mapping.get("KEY_KP4"))

        # this only lists the correct casing,
        # includes linux constants and xmodmap symbols
        names = system_mapping.list_names()
        self.assertIn("2", names)
        self.assertIn("c", names)
        self.assertIn("KEY_3", names)
        self.assertNotIn("key_3", names)
        self.assertIn("KP_Down", names)
        self.assertNotIn("kp_down", names)
        names = system_mapping._mapping.keys()
        self.assertIn("F4", names)
        self.assertNotIn("f4", names)
        self.assertIn("BTN_RIGHT", names)
        self.assertNotIn("btn_right", names)
        self.assertIn("KEY_KP7", names)
        self.assertIn("KP_Home", names)
        self.assertNotIn("kp_home", names)

        self.assertEqual(system_mapping.get("disable"), -1)

    def test_get_name_no_xmodmap(self):
        # if xmodmap is not installed, uses the linux constant names
        system_mapping = SystemMapping()

        def check_output(*args, **kwargs):
            raise FileNotFoundError

        with patch.object(subprocess, "check_output", check_output):
            system_mapping.populate()
            self.assertEqual(system_mapping.get_name(KEY_A), "KEY_A")

            # testing for BTN_LEFT is especially important, because
            # `evdev.ecodes.BTN.get(code)` returns an array of ['BTN_LEFT', 'BTN_MOUSE']
            self.assertEqual(system_mapping.get_name(BTN_LEFT), "BTN_LEFT")


if __name__ == "__main__":
    unittest.main()
