#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@hip70890b.de>
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

from keymapper.paths import get_user, touch, mkdir, \
    get_preset_path, get_config_path

from tests.test import quick_cleanup, tmp


original_getlogin = os.getlogin()


def _raise(error):
    raise error


class TestPaths(unittest.TestCase):
    def tearDown(self):
        quick_cleanup()
        os.getlogin = original_getlogin

    def test_get_user(self):
        os.getlogin = lambda: 'foo'
        self.assertEqual(get_user(), 'foo')

        os.getlogin = lambda: 'root'
        self.assertEqual(get_user(), 'root')

        os.getlogin = lambda: _raise(OSError())

        os.environ['USER'] = 'root'
        os.environ['SUDO_USER'] = 'qux'
        self.assertEqual(get_user(), 'qux')

        os.environ['USER'] = 'root'
        del os.environ['SUDO_USER']
        os.environ['PKEXEC_UID'] = '1000'
        self.assertNotEqual(get_user(), 'root')

    def test_touch(self):
        touch('/tmp/a/b/c/d/e')
        self.assertTrue(os.path.exists('/tmp/a/b/c/d/e'))
        self.assertTrue(os.path.isfile('/tmp/a/b/c/d/e'))
        self.assertRaises(ValueError, lambda: touch('/tmp/a/b/c/d/f/'))

    def test_mkdir(self):
        mkdir('/tmp/b/c/d/e')
        self.assertTrue(os.path.exists('/tmp/b/c/d/e'))
        self.assertTrue(os.path.isdir('/tmp/b/c/d/e'))

    def test_get_preset_path(self):
        self.assertEqual(get_preset_path(), os.path.join(tmp, 'presets'))
        self.assertEqual(get_preset_path('a'), os.path.join(tmp, 'presets/a'))
        self.assertEqual(get_preset_path('a', 'b'), os.path.join(tmp, 'presets/a/b.json'))

    def test_get_config_path(self):
        self.assertEqual(get_config_path(), tmp)
        self.assertEqual(get_config_path('a', 'b'), os.path.join(tmp, 'a/b'))

