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

from evdev.events import EV_KEY
import time

from keymapper.dev.reader import keycode_reader

from tests.test import Event, pending_events, EVENT_READ_TIMEOUT


CODE_1 = 100
CODE_2 = 101
CODE_3 = 102


class TestReader(unittest.TestCase):
    def setUp(self):
        # verify that tearDown properly cleared the reader
        self.assertEqual(keycode_reader.read(), (None, None))

    def tearDown(self):
        keycode_reader.stop_reading()
        keys = list(pending_events.keys())
        for key in keys:
            del pending_events[key]

    def test_reading(self):
        pending_events['device 1'] = [
            Event(EV_KEY, CODE_1, 1),
            Event(EV_KEY, CODE_2, 1),
            Event(EV_KEY, CODE_3, 1)
        ]
        keycode_reader.start_reading('device 1')

        # sending anything arbitrary does not stop the pipe
        keycode_reader._pipe[0].send((EV_KEY, 1234))

        time.sleep(EVENT_READ_TIMEOUT * 5)
        self.assertEqual(keycode_reader.read(), (EV_KEY, CODE_3))
        self.assertEqual(keycode_reader.read(), (None, None))

    def test_wrong_device(self):
        pending_events['device 1'] = [
            Event(EV_KEY, CODE_1, 1),
            Event(EV_KEY, CODE_2, 1),
            Event(EV_KEY, CODE_3, 1)
        ]
        keycode_reader.start_reading('device 2')
        time.sleep(EVENT_READ_TIMEOUT * 5)
        self.assertEqual(keycode_reader.read(), (None, None))

    def test_keymapper_devices(self):
        # Don't read from keymapper devices, their keycodes are not
        # representative for the original key. As long as this is not
        # intentionally programmed it won't even do that. But it was at some
        # point.
        pending_events['key-mapper device 2'] = [
            Event(EV_KEY, CODE_1, 1),
            Event(EV_KEY, CODE_2, 1),
            Event(EV_KEY, CODE_3, 1)
        ]
        keycode_reader.start_reading('device 2')
        time.sleep(EVENT_READ_TIMEOUT * 5)
        self.assertEqual(keycode_reader.read(), (None, None))

    def test_clear(self):
        pending_events['device 1'] = [
            Event(EV_KEY, CODE_1, 1),
            Event(EV_KEY, CODE_2, 1),
            Event(EV_KEY, CODE_3, 1)
        ]
        keycode_reader.start_reading('device 1')
        time.sleep(EVENT_READ_TIMEOUT * 5)
        keycode_reader.clear()
        self.assertEqual(keycode_reader.read(), (None, None))

    def test_switch_device(self):
        pending_events['device 2'] = [Event(EV_KEY, CODE_1, 1)]
        pending_events['device 1'] = [Event(EV_KEY, CODE_3, 1)]

        keycode_reader.start_reading('device 2')
        time.sleep(EVENT_READ_TIMEOUT * 5)

        keycode_reader.start_reading('device 1')
        time.sleep(EVENT_READ_TIMEOUT * 5)

        self.assertEqual(keycode_reader.read(), (EV_KEY, CODE_3))
        self.assertEqual(keycode_reader.read(), (None, None))


if __name__ == "__main__":
    unittest.main()
