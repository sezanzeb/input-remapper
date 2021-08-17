#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@sezanzeb.de>
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
from unittest import mock

from keymapper.user import get_user

from tests.test import quick_cleanup


def _raise(error):
    raise error


class TestPaths(unittest.TestCase):
    def tearDown(self):
        quick_cleanup()

    def test_get_user(self):
        with mock.patch('os.getlogin', lambda: 'foo'):
            self.assertEqual(get_user(), 'foo')

        with mock.patch('os.getlogin', lambda: 'root'):
            self.assertEqual(get_user(), 'root')

        with mock.patch('os.getlogin', lambda: _raise(OSError())):
            os.environ['USER'] = 'root'
            os.environ['SUDO_USER'] = 'qux'
            self.assertEqual(get_user(), 'qux')

            os.environ['USER'] = 'root'
            del os.environ['SUDO_USER']
            os.environ['PKEXEC_UID'] = '1000'
            self.assertNotEqual(get_user(), 'root')
