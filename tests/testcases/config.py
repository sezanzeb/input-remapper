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


import os
import unittest
import shutil

from keymapper.X import custom_mapping, generate_symbols, \
    create_identity_mapping, create_setxkbmap_config, get_home_path
from keymapper.paths import KEYCODES_PATH, USERS_SYMBOLS, HOME_PATH

from test import tmp


class TestConfig(unittest.TestCase):
    def setUp(self):
        custom_mapping.empty()
        custom_mapping.change(None, 10, 'a')
        custom_mapping.change(None, 11, 'KP_1')
        custom_mapping.change(None, 12, 3)
        if os.path.exists(tmp):
            shutil.rmtree(tmp)

    def test_create_setxkbmap_config(self):
        create_setxkbmap_config('device a', 'preset b')

        self.assertTrue(os.path.exists(os.path.join(
            HOME_PATH,
            'device_a',
            'preset_b'
        )))

        self.assertTrue(os.path.exists(os.path.join(
            USERS_SYMBOLS,
            'device_a',
            'preset_b'
        )))

        self.assertTrue(os.path.exists(KEYCODES_PATH))

        with open(get_home_path('device_a', 'preset_b'), 'r') as f:
            content = f.read()
            self.assertIn('key <10> { [ a ] };', content)
            self.assertIn('key <11> { [ KP_1 ] };', content)
            self.assertIn('key <12> { [ 3 ] };', content)

    def test_generate_content(self):
        self.assertRaises(
            FileNotFoundError,
            generate_symbols,
            'device', 'preset'
        )

        # create the identity mapping, because it is required for
        # generate_symbols
        create_identity_mapping()
        self.assertTrue(os.path.exists(KEYCODES_PATH))
        with open(KEYCODES_PATH, 'r') as f:
            keycodes = f.read()
            self.assertIn('<8> = 8;', keycodes)
            self.assertIn('<255> = 255;', keycodes)

        content = generate_symbols('device/preset')
        self.assertIn('key <10> { [ a ] };', content)
        self.assertIn('key <11> { [ KP_1 ] };', content)
        self.assertIn('key <12> { [ 3 ] };', content)


if __name__ == "__main__":
    unittest.main()
