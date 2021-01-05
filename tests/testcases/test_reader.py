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


import unittest
import time
import multiprocessing

from evdev.ecodes import EV_KEY, EV_ABS, ABS_HAT0X, ABS_HAT0Y, KEY_COMMA, \
    BTN_LEFT, BTN_TOOL_DOUBLETAP, ABS_Z, ABS_Y, ABS_MISC

from keymapper.dev.reader import keycode_reader
from keymapper.state import custom_mapping
from keymapper.config import BUTTONS, MOUSE

from tests.test import new_event, pending_events, EVENT_READ_TIMEOUT, \
    cleanup, MAX_ABS


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
        cleanup()

    def test_reading_1(self):
        # a single event
        pending_events['device 1'] = [
            new_event(EV_ABS, ABS_HAT0X, 1)
        ]
        keycode_reader.start_reading('device 1')
        wait(keycode_reader._pipe[0].poll, 0.5)
        self.assertEqual(keycode_reader.read(), (EV_ABS, ABS_HAT0X, 1))
        self.assertEqual(keycode_reader.read(), None)
        self.assertEqual(len(keycode_reader._unreleased), 1)

    def test_change_wheel_direction(self):
        keycode_reader.start_reading('device 1')

        keycode_reader._pipe[1].send(new_event(1234, 2345, 1))
        self.assertEqual(keycode_reader.read(), (1234, 2345, 1))
        self.assertEqual(len(keycode_reader._unreleased), 1)
        self.assertEqual(keycode_reader.read(), None)

        keycode_reader._pipe[1].send(new_event(1234, 2345, -1))
        self.assertEqual(keycode_reader.read(), (1234, 2345, -1))
        # notice that this is no combination of two sides, the previous
        # entry in unreleased has to get overwritten. So there is still only
        # one element in it.
        self.assertEqual(len(keycode_reader._unreleased), 1)
        self.assertEqual(keycode_reader.read(), None)

    def test_reading_2(self):
        # a combination of events
        pending_events['device 1'] = [
            new_event(EV_KEY, CODE_1, 1, 10000.1234),
            new_event(EV_KEY, CODE_3, 1, 10001.1234),
            new_event(EV_ABS, ABS_HAT0X, -1, 10002.1234)
        ]
        keycode_reader.start_reading('device 1')

        # sending anything arbitrary does not stop the pipe
        keycode_reader._pipe[0].send((EV_KEY, 1234))

        wait(keycode_reader._pipe[0].poll, 0.5)

        self.assertEqual(keycode_reader.read(), (
            (EV_KEY, CODE_1, 1),
            (EV_KEY, CODE_3, 1),
            (EV_ABS, ABS_HAT0X, -1)
        ))
        self.assertEqual(keycode_reader.read(), None)
        self.assertEqual(len(keycode_reader._unreleased), 3)

    def test_reads_joysticks(self):
        # if their purpose is "buttons"
        custom_mapping.set('gamepad.joystick.left_purpose', BUTTONS)
        pending_events['gamepad'] = [
            new_event(EV_ABS, ABS_Y, MAX_ABS)
        ]
        keycode_reader.start_reading('gamepad')
        wait(keycode_reader._pipe[0].poll, 0.5)
        self.assertEqual(keycode_reader.read(), (EV_ABS, ABS_Y, 1))
        self.assertEqual(keycode_reader.read(), None)
        self.assertEqual(len(keycode_reader._unreleased), 1)

        keycode_reader._unreleased = {}
        custom_mapping.set('gamepad.joystick.left_purpose', MOUSE)
        pending_events['gamepad'] = [
            new_event(EV_ABS, ABS_Y, MAX_ABS)
        ]
        keycode_reader.start_reading('gamepad')
        time.sleep(0.1)
        self.assertEqual(keycode_reader.read(), None)
        self.assertEqual(len(keycode_reader._unreleased), 0)

    def test_ignore_btn_left(self):
        # click events are ignored because overwriting them would render the
        # mouse useless, but a mouse is needed to stop the injection
        # comfortably. Furthermore, reading mouse events breaks clicking
        # around in the table. It can still be changed in the config files.
        pending_events['device 1'] = [
            new_event(EV_KEY, BTN_LEFT, 1),
            new_event(EV_KEY, CODE_2, 1),
            new_event(EV_KEY, BTN_TOOL_DOUBLETAP, 1),
        ]
        keycode_reader.start_reading('device 1')
        time.sleep(0.1)
        self.assertEqual(keycode_reader.read(), (EV_KEY, CODE_2, 1))
        self.assertEqual(keycode_reader.read(), None)
        self.assertEqual(len(keycode_reader._unreleased), 1)

    def test_ignore_value_2(self):
        # this is not a combination, because (EV_KEY CODE_3, 2) is ignored
        pending_events['device 1'] = [
            new_event(EV_ABS, ABS_HAT0X, 1),
            new_event(EV_KEY, CODE_3, 2)
        ]
        keycode_reader.start_reading('device 1')
        wait(keycode_reader._pipe[0].poll, 0.5)
        self.assertEqual(keycode_reader.read(), (EV_ABS, ABS_HAT0X, 1))
        self.assertEqual(keycode_reader.read(), None)
        self.assertEqual(len(keycode_reader._unreleased), 1)

    def test_reading_ignore_up(self):
        pending_events['device 1'] = [
            new_event(EV_KEY, CODE_1, 0, 10),
            new_event(EV_KEY, CODE_2, 1, 11),
            new_event(EV_KEY, CODE_3, 0, 12),
        ]
        keycode_reader.start_reading('device 1')
        time.sleep(0.1)
        self.assertEqual(keycode_reader.read(), (EV_KEY, CODE_2, 1))
        self.assertEqual(keycode_reader.read(), None)
        self.assertEqual(len(keycode_reader._unreleased), 1)

    def test_reading_ignore_duplicate_down(self):
        pipe = multiprocessing.Pipe()
        pipe[1].send(new_event(EV_ABS, ABS_Z, 1, 10))
        keycode_reader._pipe = pipe

        self.assertEqual(keycode_reader.read(), (EV_ABS, ABS_Z, 1))
        self.assertEqual(keycode_reader.read(), None)

        pipe[1].send(new_event(EV_ABS, ABS_Z, 1, 10))
        # still none
        self.assertEqual(keycode_reader.read(), None)

        self.assertEqual(len(keycode_reader._unreleased), 1)

    def test_wrong_device(self):
        pending_events['device 1'] = [
            new_event(EV_KEY, CODE_1, 1),
            new_event(EV_KEY, CODE_2, 1),
            new_event(EV_KEY, CODE_3, 1)
        ]
        keycode_reader.start_reading('device 2')
        time.sleep(EVENT_READ_TIMEOUT * 5)
        self.assertEqual(keycode_reader.read(), None)
        self.assertEqual(len(keycode_reader._unreleased), 0)

    def test_keymapper_devices(self):
        # Don't read from keymapper devices, their keycodes are not
        # representative for the original key. As long as this is not
        # intentionally programmed it won't even do that. But it was at some
        # point.
        pending_events['key-mapper device 2'] = [
            new_event(EV_KEY, CODE_1, 1),
            new_event(EV_KEY, CODE_2, 1),
            new_event(EV_KEY, CODE_3, 1)
        ]
        keycode_reader.start_reading('device 2')
        time.sleep(EVENT_READ_TIMEOUT * 5)
        self.assertEqual(keycode_reader.read(), None)
        self.assertEqual(len(keycode_reader._unreleased), 0)

    def test_clear(self):
        pending_events['device 1'] = [
            new_event(EV_KEY, CODE_1, 1),
            new_event(EV_KEY, CODE_2, 1),
            new_event(EV_KEY, CODE_3, 1)
        ]
        keycode_reader.start_reading('device 1')
        time.sleep(EVENT_READ_TIMEOUT * 5)
        keycode_reader.clear()
        self.assertEqual(keycode_reader.read(), None)
        self.assertEqual(len(keycode_reader._unreleased), 0)

    def test_switch_device(self):
        pending_events['device 2'] = [new_event(EV_KEY, CODE_1, 1)]
        pending_events['device 1'] = [new_event(EV_KEY, CODE_3, 1)]

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
            new_event(EV_ABS, ABS_HAT0X, 1, 1234.0000),
            new_event(EV_ABS, ABS_HAT0X, 0, 1234.0001),

            new_event(EV_ABS, ABS_HAT0X, 1, 1235.0000),  # ignored
            new_event(EV_ABS, ABS_HAT0X, 0, 1235.0001),

            new_event(EV_KEY, KEY_COMMA, 1, 1235.0010),
            new_event(EV_KEY, KEY_COMMA, 0, 1235.0011),

            new_event(EV_ABS, ABS_HAT0X, 1, 1235.0020),  # ignored
            new_event(EV_ABS, ABS_HAT0X, 0, 1235.0021),  # ignored

            new_event(EV_ABS, ABS_HAT0X, 1, 1236.0000)
        ]
        keycode_reader.start_reading('device 1')
        wait(keycode_reader._pipe[0].poll, 0.5)
        self.assertEqual(keycode_reader.read(), (EV_ABS, ABS_HAT0X, 1))
        self.assertEqual(keycode_reader.read(), None)
        self.assertEqual(len(keycode_reader._unreleased), 1)

    def test_prioritizing_2_normalize(self):
        # a value of 1234 becomes 1 in the reader in order to properly map
        # it. Value like that are usually some sort of continuous trigger
        # value and normal for some ev_abs events.
        custom_mapping.set('gamepad.joystick.left_purpose', BUTTONS)
        pending_events['gamepad'] = [
            new_event(EV_ABS, ABS_HAT0X, 1, 1234.0000),
            new_event(EV_ABS, ABS_MISC, 1, 1235.0000),  # ignored
            new_event(EV_ABS, ABS_Y, MAX_ABS, 1235.0010),
            new_event(EV_ABS, ABS_MISC, 1, 1235.0020),  # ignored
            new_event(EV_ABS, ABS_MISC, 1, 1235.0030)  # ignored
            # this time, don't release anything. the combination should
            # ignore stuff as well.
        ]
        keycode_reader.start_reading('gamepad')
        time.sleep(0.5)
        wait(keycode_reader._pipe[0].poll, 0.5)
        self.assertEqual(keycode_reader.read(), (
            (EV_ABS, ABS_HAT0X, 1),
            (EV_ABS, ABS_Y, 1)
        ))
        self.assertEqual(keycode_reader.read(), None)
        self.assertEqual(len(keycode_reader._unreleased), 2)

    def test_prioritizing_3_normalize(self):
        # take the sign of -1234, just like in test_prioritizing_2_normalize
        pending_events['device 1'] = [
            new_event(EV_ABS, ABS_HAT0X, -1234, 1234.0000),
            new_event(EV_ABS, ABS_HAT0Y, 0, 1234.0030)  # ignored
            # this time don't release anything as well, but it's not
            # a combination because only one event is accepted
        ]
        keycode_reader.start_reading('device 1')
        wait(keycode_reader._pipe[0].poll, 0.5)
        self.assertEqual(keycode_reader.read(), (EV_ABS, ABS_HAT0X, -1))
        self.assertEqual(keycode_reader.read(), None)
        self.assertEqual(len(keycode_reader._unreleased), 1)


if __name__ == "__main__":
    unittest.main()
