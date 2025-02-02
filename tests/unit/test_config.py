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

from inputremapper.configs.global_config import GlobalConfig
from inputremapper.configs.paths import PathUtils
from tests.lib.test_setup import test_setup
from tests.lib.tmp import tmp


@test_setup
class TestConfig(unittest.TestCase):
    def test_basic(self):
        global_config = GlobalConfig()
        self.assertEqual(global_config.get("a"), None)

        global_config.set("a", 1)
        self.assertEqual(global_config.get("a"), 1)

        global_config.remove("a")
        global_config.set("a.b", 2)
        self.assertEqual(global_config.get("a.b"), 2)
        self.assertEqual(global_config._config["a"]["b"], 2)

        global_config.remove("a.b")
        global_config.set("a.b.c", 3)
        self.assertEqual(global_config.get("a.b.c"), 3)
        self.assertEqual(global_config._config["a"]["b"]["c"], 3)

    def test_autoload(self):
        global_config = GlobalConfig()
        self.assertEqual(len(global_config.iterate_autoload_presets()), 0)
        self.assertFalse(global_config.is_autoloaded("d1", "a"))
        self.assertFalse(global_config.is_autoloaded("d2.foo", "b"))
        self.assertEqual(global_config.get(["autoload", "d1"]), None)
        self.assertEqual(global_config.get(["autoload", "d2.foo"]), None)

        global_config.set_autoload_preset("d1", "a")
        self.assertEqual(len(global_config.iterate_autoload_presets()), 1)
        self.assertTrue(global_config.is_autoloaded("d1", "a"))
        self.assertFalse(global_config.is_autoloaded("d2.foo", "b"))

        global_config.set_autoload_preset("d2.foo", "b")
        self.assertEqual(len(global_config.iterate_autoload_presets()), 2)
        self.assertTrue(global_config.is_autoloaded("d1", "a"))
        self.assertTrue(global_config.is_autoloaded("d2.foo", "b"))
        self.assertEqual(global_config.get(["autoload", "d1"]), "a")
        self.assertEqual(global_config.get("autoload.d1"), "a")
        self.assertEqual(global_config.get(["autoload", "d2.foo"]), "b")

        global_config.set_autoload_preset("d2.foo", "c")
        self.assertEqual(len(global_config.iterate_autoload_presets()), 2)
        self.assertTrue(global_config.is_autoloaded("d1", "a"))
        self.assertFalse(global_config.is_autoloaded("d2.foo", "b"))
        self.assertTrue(global_config.is_autoloaded("d2.foo", "c"))
        self.assertEqual(global_config._config["autoload"]["d2.foo"], "c")
        self.assertListEqual(
            list(global_config.iterate_autoload_presets()),
            [("d1", "a"), ("d2.foo", "c")],
        )

        global_config.set_autoload_preset("d2.foo", None)
        self.assertTrue(global_config.is_autoloaded("d1", "a"))
        self.assertFalse(global_config.is_autoloaded("d2.foo", "b"))
        self.assertFalse(global_config.is_autoloaded("d2.foo", "c"))
        self.assertListEqual(
            list(global_config.iterate_autoload_presets()),
            [("d1", "a")],
        )
        self.assertEqual(global_config.get(["autoload", "d1"]), "a")

        self.assertRaises(ValueError, global_config.is_autoloaded, "d1", None)
        self.assertRaises(ValueError, global_config.is_autoloaded, None, "a")

    def test_initial(self):
        global_config = GlobalConfig()
        # when loading for the first time, create a config file with
        # the default values
        self.assertFalse(os.path.exists(global_config.path))
        global_config.load_config()
        self.assertTrue(os.path.exists(global_config.path))

        with open(global_config.path, "r") as file:
            contents = file.read()
            self.assertIn('"autoload": {}', contents)

    def test_save_load(self):
        global_config = GlobalConfig()
        self.assertEqual(len(global_config.iterate_autoload_presets()), 0)

        global_config.load_config()
        self.assertEqual(len(global_config.iterate_autoload_presets()), 0)

        global_config.set_autoload_preset("d1", "a")
        global_config.set_autoload_preset("d2.foo", "b")

        global_config.load_config()
        self.assertListEqual(
            list(global_config.iterate_autoload_presets()),
            [("d1", "a"), ("d2.foo", "b")],
        )

        config_2 = os.path.join(tmp, "config_2.json")
        PathUtils.touch(config_2)
        with open(config_2, "w") as f:
            f.write('{"a":"b"}')

        global_config.load_config(config_2)
        self.assertEqual(global_config.get("a"), "b")
        self.assertEqual(global_config.get(["a"]), "b")


if __name__ == "__main__":
    unittest.main()
