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

from evdev.ecodes import EV_KEY, EV_ABS, ABS_HAT0X, KEY_A, ABS_X, EV_REL, REL_X

from keymapper.dev.keycode_mapper import should_map_event_as_btn


class TestKeycodeMapper(unittest.TestCase):
    def test_should_map_event_as_btn(self):
        self.assertTrue(should_map_event_as_btn(EV_ABS, ABS_HAT0X))
        self.assertTrue(should_map_event_as_btn(EV_KEY, KEY_A))
        self.assertFalse(should_map_event_as_btn(EV_ABS, ABS_X))
        self.assertFalse(should_map_event_as_btn(EV_REL, REL_X))

    # TODO test for macro holding

if __name__ == "__main__":
    unittest.main()
