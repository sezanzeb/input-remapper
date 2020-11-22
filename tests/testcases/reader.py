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

import evdev

from keymapper.reader import keycode_reader

from test import Event, pending_events


CODE_1 = 100
CODE_2 = 101
CODE_3 = 102


class TestReader(unittest.TestCase):
    def tearDown(self):
        keycode_reader.clear()

    def test_reading(self):
        keycode_reader.start_reading('device 1')
        pending_events['device 1'] = [
            Event(evdev.events.EV_KEY, CODE_1, 1),
            Event(evdev.events.EV_KEY, CODE_2, 1),
            Event(evdev.events.EV_KEY, CODE_3, 1)
        ]
        self.assertEqual(keycode_reader.read(), CODE_3 + 8)
        self.assertIsNone(keycode_reader.read())

    def test_specific_device(self):
        keycode_reader.start_reading('device 2')
        pending_events['device 1'] = [
            Event(evdev.events.EV_KEY, CODE_1, 1),
            Event(evdev.events.EV_KEY, CODE_2, 1),
            Event(evdev.events.EV_KEY, CODE_3, 1)
        ]
        self.assertIsNone(keycode_reader.read())

    def test_clear(self):
        keycode_reader.start_reading('device 1')
        pending_events['device 1'] = [
            Event(evdev.events.EV_KEY, CODE_1, 1),
            Event(evdev.events.EV_KEY, CODE_2, 1),
            Event(evdev.events.EV_KEY, CODE_3, 1)
        ]
        keycode_reader.clear()
        self.assertIsNone(keycode_reader.read())

    def test_switch_device(self):
        keycode_reader.start_reading('device 2')
        pending_events['device 2'] = [Event(evdev.events.EV_KEY, CODE_1, 1)]

        keycode_reader.start_reading('device 1')
        pending_events['device 1'] = [Event(evdev.events.EV_KEY, CODE_3, 1)]

        self.assertEqual(keycode_reader.read(), CODE_3 + 8)
        self.assertIsNone(keycode_reader.read())


if __name__ == "__main__":
    unittest.main()
