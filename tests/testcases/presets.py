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
import time

from keymapper.presets import find_newest_preset


class PresetsTest(unittest.TestCase):
    def setUp(self):
        shutil.rmtree('/tmp/key-mapper-test')

    def test_find_newest_preset_1(self):
        os.makedirs('/tmp/key-mapper-test/symbols/device_1')
        os.makedirs('/tmp/key-mapper-test/symbols/device_2')
        os.mknod('/tmp/key-mapper-test/symbols/device_1/preset_1')
        time.sleep(0.01)
        os.mknod('/tmp/key-mapper-test/symbols/device_2/preset_2')
        # since presets are loaded from the path, and devices from the
        # x command line tools, the presets have the exact same name as
        # the path whereas devices need their whitespaces removed.
        self.assertEqual(find_newest_preset(), ('device 2', 'preset_2'))

    def test_find_newest_preset_2(self):
        os.makedirs('/tmp/key-mapper-test/symbols/device_1')
        time.sleep(0.01)
        os.makedirs('/tmp/key-mapper-test/symbols/device_2')
        # takes the first one that the test-fake returns
        self.assertEqual(find_newest_preset(), ('device 1', None))

    def test_find_newest_preset_3(self):
        os.makedirs('/tmp/key-mapper-test/symbols/device_1')
        self.assertEqual(find_newest_preset(), ('device 1', None))

    def test_find_newest_preset_4(self):
        os.makedirs('/tmp/key-mapper-test/symbols/device_1')
        os.mknod('/tmp/key-mapper-test/symbols/device_1/preset_1')
        self.assertEqual(find_newest_preset(), ('device 1', 'preset_1'))

    def test_find_newest_preset_5(self):
        os.makedirs('/tmp/key-mapper-test/symbols/device_1')
        os.mknod('/tmp/key-mapper-test/symbols/device_1/preset_1')
        time.sleep(0.01)
        os.makedirs('/tmp/key-mapper-test/symbols/unknown_device3')
        os.mknod('/tmp/key-mapper-test/symbols/unknown_device3/preset_1')
        self.assertEqual(find_newest_preset(), ('device 1', 'preset_1'))

    def test_find_newest_preset_6(self):
        # takes the first one that the test-fake returns
        self.assertEqual(find_newest_preset(), ('device 1', None))


if __name__ == "__main__":
    unittest.main()
