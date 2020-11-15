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
import time
import unittest
import shutil

from keymapper.X import custom_mapping, generate_symbols, \
    create_identity_mapping, create_setxkbmap_config, \
    get_preset_name, create_default_symbols
from keymapper.paths import get_home_path, get_usr_path, KEYCODES_PATH, \
    HOME_PATH, USERS_SYMBOLS

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

            self.assertIn('include "key-mapper/user/default"', content)
            self.assertIn(get_preset_name('device_a', 'preset_b'), content)

    def test_default_symbols(self):
        # keycodes are missing
        self.assertRaises(
            FileNotFoundError,
            create_default_symbols
        )
        create_identity_mapping()
        create_default_symbols()

        self.assertTrue(os.path.exists(get_home_path('default')))
        self.assertTrue(os.path.exists(get_usr_path('default')))
        self.assertTrue(os.path.islink(get_usr_path()))

        with open(get_home_path('default'), 'r') as f:
            content = f.read()
            self.assertNotIn('include', content)
            # this is pretty much the same on every keyboard
            self.assertIn('key <10> { [ 1', content)
            self.assertIn('key <11> { [ 2', content)
            self.assertIn('key <12> { [ 3', content)
            self.assertIn('key <65> { [ space ] };', content)

    def test_get_preset_name(self):
        self.assertEqual(get_preset_name('a', 'b'), 'key-mapper/user/a/b')
        self.assertEqual(get_preset_name('a'), 'key-mapper/user/a')

    def test_generate_content(self):
        self.assertRaises(
            FileNotFoundError,
            generate_symbols,
            'device', 'preset'
        )

        # create the identity mapping, because it is required for
        # generate_symbols
        create_identity_mapping()

        content = generate_symbols('device/preset')
        self.assertIn('key <10> { [ a ] };', content)
        self.assertIn('key <11> { [ KP_1 ] };', content)
        self.assertIn('key <12> { [ 3 ] };', content)

    def test_identity_mapping(self):
        create_identity_mapping()
        self.assertTrue(os.path.exists(KEYCODES_PATH))
        with open(KEYCODES_PATH, 'r') as f:
            content = f.read()
            self.assertIn('minimum = 8;', content)
            # whatever the maximum is, might change if mouse buttons
            # can be supported at some point as well (no idea how)
            self.assertIn('maximum =', content)
            self.assertIn('<8> = 8;', content)
            self.assertIn('<255> = 255;', content)
            # this is stuff that should only be found in symbol files
            self.assertNotIn('include', content)
            self.assertNotIn('name', content)
            # to make sure they are used together with format, which
            # changes {{ to {.
            self.assertNotIn('{{', content)
            self.assertNotIn('}}', content)


if __name__ == "__main__":
    unittest.main()
