#!/usr/bin/python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2023 sezanzeb <proxima@sezanzeb.de>
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


import unittest

from evdev._ecodes import EV_ABS, ABS_X, BTN_WEST, BTN_Y, EV_KEY, KEY_A

from inputremapper.utils import get_evdev_constant_name
from tests.test import setup_tests


@setup_tests
class TestUtil(unittest.TestCase):
    def test_get_evdev_constant_name(self):
        # BTN_WEST and BTN_Y both are code 308. I don't care which one is chosen
        # in the return value, but it should return one of them without crashing.
        self.assertEqual(get_evdev_constant_name(EV_KEY, BTN_Y), "BTN_WEST")
        self.assertEqual(get_evdev_constant_name(EV_KEY, BTN_WEST), "BTN_WEST")

        self.assertEqual(get_evdev_constant_name(123, KEY_A), "unknown")
        self.assertEqual(get_evdev_constant_name(EV_KEY, 9999), "unknown")

        self.assertEqual(get_evdev_constant_name(EV_KEY, KEY_A), "KEY_A")

        self.assertEqual(get_evdev_constant_name(EV_ABS, ABS_X), "ABS_X")
