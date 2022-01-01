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


import os
import unittest

from inputremapper.config import config, GlobalConfig
from inputremapper.paths import touch, CONFIG_PATH
from inputremapper.logger import logger

from tests.test import quick_cleanup, tmp


class TestConfig(unittest.TestCase):
    def tearDown(self):
        quick_cleanup()
        self.assertEqual(len(config.iterate_autoload_presets()), 0)

    def test_get_default(self):
        config._config = {}
        self.assertEqual(config.get("gamepad.joystick.non_linearity"), 4)

        config.set("gamepad.joystick.non_linearity", 3)
        self.assertEqual(config.get("gamepad.joystick.non_linearity"), 3)

    def test_basic(self):
        self.assertEqual(config.get("a"), None)

        config.set("a", 1)
        self.assertEqual(config.get("a"), 1)

        config.remove("a")
        config.set("a.b", 2)
        self.assertEqual(config.get("a.b"), 2)
        self.assertEqual(config._config["a"]["b"], 2)

        config.remove("a.b")
        config.set("a.b.c", 3)
        self.assertEqual(config.get("a.b.c"), 3)
        self.assertEqual(config._config["a"]["b"]["c"], 3)

    def test_autoload(self):
        self.assertEqual(len(config.iterate_autoload_presets()), 0)
        self.assertFalse(config.is_autoloaded("d1", "a"))
        self.assertFalse(config.is_autoloaded("d2.foo", "b"))
        self.assertEqual(config.get(["autoload", "d1"]), None)
        self.assertEqual(config.get(["autoload", "d2.foo"]), None)

        config.set_autoload_preset("d1", "a")
        self.assertEqual(len(config.iterate_autoload_presets()), 1)
        self.assertTrue(config.is_autoloaded("d1", "a"))
        self.assertFalse(config.is_autoloaded("d2.foo", "b"))

        config.set_autoload_preset("d2.foo", "b")
        self.assertEqual(len(config.iterate_autoload_presets()), 2)
        self.assertTrue(config.is_autoloaded("d1", "a"))
        self.assertTrue(config.is_autoloaded("d2.foo", "b"))
        self.assertEqual(config.get(["autoload", "d1"]), "a")
        self.assertEqual(config.get("autoload.d1"), "a")
        self.assertEqual(config.get(["autoload", "d2.foo"]), "b")

        config.set_autoload_preset("d2.foo", "c")
        self.assertEqual(len(config.iterate_autoload_presets()), 2)
        self.assertTrue(config.is_autoloaded("d1", "a"))
        self.assertFalse(config.is_autoloaded("d2.foo", "b"))
        self.assertTrue(config.is_autoloaded("d2.foo", "c"))
        self.assertEqual(config._config["autoload"]["d2.foo"], "c")
        self.assertListEqual(
            list(config.iterate_autoload_presets()), [("d1", "a"), ("d2.foo", "c")]
        )

        config.set_autoload_preset("d2.foo", None)
        self.assertTrue(config.is_autoloaded("d1", "a"))
        self.assertFalse(config.is_autoloaded("d2.foo", "b"))
        self.assertFalse(config.is_autoloaded("d2.foo", "c"))
        self.assertListEqual(list(config.iterate_autoload_presets()), [("d1", "a")])
        self.assertEqual(config.get(["autoload", "d1"]), "a")

    def test_initial(self):
        # when loading for the first time, create a config file with
        # the default values
        os.remove(config.path)
        self.assertFalse(os.path.exists(config.path))
        config.load_config()
        self.assertTrue(os.path.exists(config.path))

        with open(config.path, "r") as file:
            contents = file.read()
            self.assertIn('"keystroke_sleep_ms": 10', contents)

    def test_save_load(self):
        self.assertEqual(len(config.iterate_autoload_presets()), 0)

        config.load_config()
        self.assertEqual(len(config.iterate_autoload_presets()), 0)

        config.set_autoload_preset("d1", "a")
        config.set_autoload_preset("d2.foo", "b")
        config.save_config()

        # ignored after load
        config.set_autoload_preset("d3", "c")

        config.load_config()
        self.assertListEqual(
            list(config.iterate_autoload_presets()), [("d1", "a"), ("d2.foo", "b")]
        )

        config_2 = os.path.join(tmp, "config_2.json")
        touch(config_2)
        with open(config_2, "w") as f:
            f.write('{"a":"b"}')

        config.load_config(config_2)
        self.assertEqual(config.get("a"), "b")
        self.assertEqual(config.get(["a"]), "b")


if __name__ == "__main__":
    unittest.main()
