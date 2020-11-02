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

from keymapper.logger import update_verbosity
from keymapper.config import _modify_config, get_config


class ConfigTest(unittest.TestCase):
    def test_first_line(self):
        contents = """a=1\n # test=3\n  abc=123"""
        contents = _modify_config(contents, 'a', 3)
        self.assertEqual(contents, """a=3\n # test=3\n  abc=123""")

    def test_last_line(self):
        contents = """a=1\n # test=3\n  abc=123"""
        contents = _modify_config(contents, 'abc', 'foo')
        self.assertEqual(contents, """a=1\n # test=3\nabc=foo""")

    def test_new_line(self):
        contents = """a=1\n # test=3\n  abc=123"""
        contents = _modify_config(contents, 'test', '1234')
        self.assertEqual(contents, """a=1\n # test=3\n  abc=123\ntest=1234""")

    def test_get_config(self):
        config = get_config('device1', 'preset1', '/tmp/key-mapper')
        self.assertEqual(config.device, 'device1')
        self.assertEqual(config.preset, 'preset1')
        self.assertTrue(os.path.isfile('/tmp/key-mapper/device1/preset1'))

        get_config('device1', 'preset2', '/tmp/key-mapper')
        self.assertTrue(os.path.isfile('/tmp/key-mapper/device1/preset2'))

        get_config('device2', 'preset3', '/tmp/key-mapper')
        self.assertTrue(os.path.isfile('/tmp/key-mapper/device2/preset3'))

        config.set('key1', 'value')
        config.set('key2', 123)
        with open('/tmp/key-mapper/device1/preset1', 'r') as f:
            contents = f.read()
            self.assertEqual(contents, 'key1=value\nkey2=123\n')


if __name__ == "__main__":
    unittest.main()
