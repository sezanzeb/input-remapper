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

from keymapper.config import config


class TestConfig(unittest.TestCase):
    def tearDown(self):
        config.clear_config()
        self.assertEqual(len(config.iterate_autoload_presets()), 0)
        config.save_config()

    def test_get_default(self):
        config._config = {}
        self.assertEqual(config.get('gamepad.joystick.non_linearity'), 4)

        config.set('gamepad.joystick.non_linearity', 3)
        self.assertEqual(config.get('gamepad.joystick.non_linearity'), 3)

    def test_basic(self):
        self.assertEqual(config.get('a'), None)

        config.set('a', 1)
        self.assertEqual(config.get('a'), 1)

        config.remove('a')
        config.set('a.b', 2)
        self.assertEqual(config.get('a.b'), 2)
        self.assertEqual(config._config['a']['b'], 2)

        config.remove('a.b')
        config.set('a.b.c', 3)
        self.assertEqual(config.get('a.b.c'), 3)
        self.assertEqual(config._config['a']['b']['c'], 3)

    def test_autoload(self):
        del config._config['autoload']
        self.assertEqual(len(config.iterate_autoload_presets()), 0)
        self.assertFalse(config.is_autoloaded('d1', 'a'))
        self.assertFalse(config.is_autoloaded('d2', 'b'))

        config.set_autoload_preset('d1', 'a')
        self.assertEqual(len(config.iterate_autoload_presets()), 1)
        self.assertTrue(config.is_autoloaded('d1', 'a'))
        self.assertFalse(config.is_autoloaded('d2', 'b'))

        config.set_autoload_preset('d2', 'b')
        self.assertEqual(len(config.iterate_autoload_presets()), 2)
        self.assertTrue(config.is_autoloaded('d1', 'a'))
        self.assertTrue(config.is_autoloaded('d2', 'b'))

        config.set_autoload_preset('d2', 'c')
        self.assertEqual(len(config.iterate_autoload_presets()), 2)
        self.assertTrue(config.is_autoloaded('d1', 'a'))
        self.assertFalse(config.is_autoloaded('d2', 'b'))
        self.assertTrue(config.is_autoloaded('d2', 'c'))
        self.assertListEqual(
            list(config.iterate_autoload_presets()),
            [('d1', 'a'), ('d2', 'c')]
        )

        config.set_autoload_preset('d2', None)
        self.assertTrue(config.is_autoloaded('d1', 'a'))
        self.assertFalse(config.is_autoloaded('d2', 'b'))
        self.assertFalse(config.is_autoloaded('d2', 'c'))
        self.assertListEqual(
            list(config.iterate_autoload_presets()),
            [('d1', 'a')]
        )

    def test_save_load(self):
        self.assertEqual(len(config.iterate_autoload_presets()), 0)

        config.load_config()
        self.assertEqual(len(config.iterate_autoload_presets()), 0)

        config.set_autoload_preset('d1', 'a')
        config.set_autoload_preset('d2', 'b')
        config.save_config()

        # ignored after load
        config.set_autoload_preset('d3', 'c')

        config.load_config()
        self.assertListEqual(
            list(config.iterate_autoload_presets()),
            [('d1', 'a'), ('d2', 'b')]
        )


if __name__ == "__main__":
    unittest.main()
