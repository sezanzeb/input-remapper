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

from evdev.ecodes import EV_KEY, EV_ABS, ABS_HAT0X, KEY_COMMA
import time

from keymapper.dev.reader import keycode_reader

from tests.test import InputEvent, pending_events, EVENT_READ_TIMEOUT


CODE_1 = 100
CODE_2 = 101
CODE_3 = 102


def wait(func, timeout=1.0):
    """Wait for func to return True."""
    iterations = 0
    sleepytime = 0.1
    while not func():
        time.sleep(sleepytime)
        iterations += 1
        if iterations * sleepytime > timeout:
            break


class TestReader(unittest.TestCase):
    def setUp(self):
        # verify that tearDown properly cleared the reader
        self.assertEqual(keycode_reader.read(), None)

    def tearDown(self):
        keycode_reader.stop_reading()
        keys = list(pending_events.keys())
        for key in keys:
            del pending_events[key]
        keycode_reader.newest_event = None

    def test_reading_1(self):
        pending_events['device 1'] = [
            InputEvent(EV_KEY, CODE_1, 1, 10000.1234),
            InputEvent(EV_KEY, CODE_3, 1, 10001.1234),
            InputEvent(EV_ABS, ABS_HAT0X, -1, 10002.1234)
        ]
        keycode_reader.start_reading('device 1')

        # sending anything arbitrary does not stop the pipe
        keycode_reader._pipe[0].send((EV_KEY, 1234))

        wait(keycode_reader._pipe[0].poll, 0.5)

        self.assertEqual(keycode_reader.read(), (EV_ABS, ABS_HAT0X, -1))
        self.assertEqual(keycode_reader.read(), None)

    def test_reading_2(self):
        pending_events['device 1'] = [InputEvent(EV_ABS, ABS_HAT0X, 1)]
        keycode_reader.start_reading('device 1')
        wait(keycode_reader._pipe[0].poll, 0.5)
        self.assertEqual(keycode_reader.read(), (EV_ABS, ABS_HAT0X, 1))
        self.assertEqual(keycode_reader.read(), None)

    def test_reading_ignore_up(self):
        pending_events['device 1'] = [
            InputEvent(EV_KEY, CODE_1, 0, 10),
            InputEvent(EV_KEY, CODE_2, 0, 11),
            InputEvent(EV_KEY, CODE_3, 0, 12),
        ]
        keycode_reader.start_reading('device 1')
        time.sleep(0.1)
        self.assertEqual(keycode_reader.read(), None)

    def test_wrong_device(self):
        pending_events['device 1'] = [
            InputEvent(EV_KEY, CODE_1, 1),
            InputEvent(EV_KEY, CODE_2, 1),
            InputEvent(EV_KEY, CODE_3, 1)
        ]
        keycode_reader.start_reading('device 2')
        time.sleep(EVENT_READ_TIMEOUT * 5)
        self.assertEqual(keycode_reader.read(), None)

    def test_keymapper_devices(self):
        # Don't read from keymapper devices, their keycodes are not
        # representative for the original key. As long as this is not
        # intentionally programmed it won't even do that. But it was at some
        # point.
        pending_events['key-mapper device 2'] = [
            InputEvent(EV_KEY, CODE_1, 1),
            InputEvent(EV_KEY, CODE_2, 1),
            InputEvent(EV_KEY, CODE_3, 1)
        ]
        keycode_reader.start_reading('device 2')
        time.sleep(EVENT_READ_TIMEOUT * 5)
        self.assertEqual(keycode_reader.read(), None)

    def test_clear(self):
        pending_events['device 1'] = [
            InputEvent(EV_KEY, CODE_1, 1),
            InputEvent(EV_KEY, CODE_2, 1),
            InputEvent(EV_KEY, CODE_3, 1)
        ]
        keycode_reader.start_reading('device 1')
        time.sleep(EVENT_READ_TIMEOUT * 5)
        keycode_reader.clear()
        self.assertEqual(keycode_reader.read(), None)

    def test_switch_device(self):
        pending_events['device 2'] = [InputEvent(EV_KEY, CODE_1, 1)]
        pending_events['device 1'] = [InputEvent(EV_KEY, CODE_3, 1)]

        keycode_reader.start_reading('device 2')
        time.sleep(EVENT_READ_TIMEOUT * 5)

        keycode_reader.start_reading('device 1')
        time.sleep(EVENT_READ_TIMEOUT * 5)

        self.assertEqual(keycode_reader.read(), (EV_KEY, CODE_3, 1))
        self.assertEqual(keycode_reader.read(), None)

    def test_prioritizing_1(self):
        # filter the ABS_MISC events of the wacom intuos 5 out that come
        # with every button press. Or more general, prioritize them
        # based on the event type
        pending_events['device 1'] = [
            InputEvent(EV_ABS, ABS_HAT0X, 1, 1234.0000),
            InputEvent(EV_ABS, ABS_HAT0X, 1, 1235.0000),  # ignored
            InputEvent(EV_KEY, KEY_COMMA, 1, 1235.0010),
            InputEvent(EV_ABS, ABS_HAT0X, 1, 1235.0020),  # ignored
            InputEvent(EV_ABS, ABS_HAT0X, 1, 1236.0000)
        ]
        keycode_reader.start_reading('device 1')
        wait(keycode_reader._pipe[0].poll, 0.5)
        self.assertEqual(keycode_reader.read(), (EV_ABS, ABS_HAT0X, 1))
        self.assertEqual(keycode_reader.read(), None)

    def test_prioritizing_2_normalize(self):
        # furthermore, 1234 is 1 in the reader, because it probably is some
        # sort of continuous trigger or joystick value
        pending_events['device 1'] = [
            InputEvent(EV_ABS, ABS_HAT0X, 1, 1234.0000),
            InputEvent(EV_ABS, ABS_HAT0X, 1, 1235.0000),  # ignored
            InputEvent(EV_KEY, KEY_COMMA, 1234, 1235.0010),
            InputEvent(EV_ABS, ABS_HAT0X, 1, 1235.0020),  # ignored
            InputEvent(EV_ABS, ABS_HAT0X, 1, 1235.0030)  # ignored
        ]
        keycode_reader.start_reading('device 1')
        wait(keycode_reader._pipe[0].poll, 0.5)
        self.assertEqual(keycode_reader.read(), (EV_KEY, KEY_COMMA, 1))
        self.assertEqual(keycode_reader.read(), None)

    def test_prioritizing_3_normalize(self):
        # take the sign of -1234, just like in test_prioritizing_2_normalize
        pending_events['device 1'] = [
            InputEvent(EV_ABS, ABS_HAT0X, -1234, 1234.0000),
            InputEvent(EV_ABS, ABS_HAT0X, 0, 1234.0030)  # ignored
        ]
        keycode_reader.start_reading('device 1')
        wait(keycode_reader._pipe[0].poll, 0.5)
        self.assertEqual(keycode_reader.read(), (EV_ABS, ABS_HAT0X, -1))
        self.assertEqual(keycode_reader.read(), None)


if __name__ == "__main__":
    unittest.main()
