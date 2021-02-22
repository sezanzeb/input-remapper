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

import evdev
from evdev.ecodes import EV_ABS, EV_KEY

from keymapper.getdevices import get_devices

from tests.test import InputDevice, cleanup, fixtures


class TestTest(unittest.TestCase):
    def test_stubs(self):
        self.assertIn('device 1', get_devices())

    def test_fake_capabilities(self):
        device = InputDevice('/dev/input/event30')
        capabilities = device.capabilities(absinfo=False)
        self.assertIsInstance(capabilities, dict)
        self.assertIsInstance(capabilities[EV_ABS], list)
        self.assertIsInstance(capabilities[EV_ABS][0], int)

        capabilities = device.capabilities()
        self.assertIsInstance(capabilities, dict)
        self.assertIsInstance(capabilities[EV_ABS], list)
        self.assertIsInstance(capabilities[EV_ABS][0], tuple)
        self.assertIsInstance(capabilities[EV_ABS][0][0], int)
        self.assertIsInstance(capabilities[EV_ABS][0][1], evdev.AbsInfo)
        self.assertIsInstance(capabilities[EV_ABS][0][1].max, int)
        self.assertIsInstance(capabilities, dict)
        self.assertIsInstance(capabilities[EV_KEY], list)
        self.assertIsInstance(capabilities[EV_KEY][0], int)

    def test_restore_fixtures(self):
        fixtures[1] = [1234]
        del fixtures['/dev/input/event11']
        cleanup()
        self.assertIsNone(fixtures.get(1))
        self.assertIsNotNone(fixtures.get('/dev/input/event11'))

    def test_restore_os_environ(self):
        os.environ['foo'] = 'bar'
        del os.environ['USER']
        environ = os.environ
        cleanup()
        self.assertIn('USER', environ)
        self.assertNotIn('foo', environ)


if __name__ == "__main__":
    unittest.main()
