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


import unittest
import time
import multiprocessing

from evdev.ecodes import EV_KEY, EV_ABS, ABS_HAT0X, ABS_HAT0Y, KEY_COMMA, \
    BTN_LEFT, BTN_TOOL_DOUBLETAP, ABS_Z, ABS_Y, ABS_MISC, KEY_A, \
    EV_REL, REL_WHEEL, REL_X, ABS_X, ABS_RZ

from keymapper.gui.reader import keycode_reader, will_report_up, \
    event_unix_time
from keymapper.state import custom_mapping
from keymapper.config import BUTTONS, MOUSE
from keymapper.key import Key

from tests.test import new_event, pending_events, EVENT_READ_TIMEOUT, \
    quick_cleanup, MAX_ABS


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
        quick_cleanup()

    def test_will_report_up(self):
        self.assertFalse(will_report_up(EV_REL))
        self.assertTrue(will_report_up(EV_ABS))
        self.assertTrue(will_report_up(EV_KEY))

    def test_event_unix_time(self):
        event = new_event(1, 1, 1, 1234.5678)
        self.assertEqual(event_unix_time(event), 1234.5678)
        self.assertEqual(event_unix_time(None), 0)

    def test_reading_1(self):
        # a single event
        pending_events['device 1'] = [
            new_event(EV_ABS, ABS_HAT0X, 1),
            new_event(EV_REL, REL_X, 1),  # mouse movements are ignored
        ]
        keycode_reader.start_reading('device 1')
        wait(keycode_reader._pipe[0].poll, 0.5)
        self.assertEqual(keycode_reader.read(), (EV_ABS, ABS_HAT0X, 1))
        self.assertEqual(keycode_reader.read(), None)
        self.assertEqual(len(keycode_reader._unreleased), 1)

    def test_reading_wheel(self):
        # will be treated as released automatically at some point
        keycode_reader.start_reading('device 1')

        keycode_reader._pipe[1].send(new_event(EV_REL, REL_WHEEL, 0))
        self.assertIsNone(keycode_reader.read())

        keycode_reader._pipe[1].send(new_event(EV_REL, REL_WHEEL, 1))
        result = keycode_reader.read()
        self.assertIsInstance(result, Key)
        self.assertEqual(result, (EV_REL, REL_WHEEL, 1))
        self.assertEqual(result, ((EV_REL, REL_WHEEL, 1),))
        self.assertNotEqual(result, ((EV_REL, REL_WHEEL, 1), (1, 1, 1)))
        self.assertEqual(result.keys, ((EV_REL, REL_WHEEL, 1),))

        # it won't return the same event twice
        self.assertEqual(keycode_reader.read(), None)

        # but it is still remembered unreleased
        self.assertEqual(len(keycode_reader._unreleased), 1)
        self.assertEqual(keycode_reader.get_unreleased_keys(), (EV_REL, REL_WHEEL, 1))
        self.assertIsInstance(keycode_reader.get_unreleased_keys(), Key)

        # as long as new wheel events arrive, it is considered unreleased
        for _ in range(10):
            keycode_reader._pipe[1].send(new_event(EV_REL, REL_WHEEL, 1))
            self.assertEqual(keycode_reader.read(), None)
            self.assertEqual(len(keycode_reader._unreleased), 1)

        # read a few more times, at some point it is treated as unreleased
        for _ in range(4):
            self.assertEqual(keycode_reader.read(), None)
        self.assertEqual(len(keycode_reader._unreleased), 0)
        self.assertIsNone(keycode_reader.get_unreleased_keys())

        """combinations"""

        keycode_reader._pipe[1].send(new_event(EV_REL, REL_WHEEL, 1, 1000))
        keycode_reader._pipe[1].send(new_event(EV_KEY, KEY_COMMA, 1, 1001))
        combi_1 = ((EV_REL, REL_WHEEL, 1), (EV_KEY, KEY_COMMA, 1))
        combi_2 = ((EV_KEY, KEY_COMMA, 1), (EV_KEY, KEY_A, 1))
        read = keycode_reader.read()
        self.assertEqual(read, combi_1)
        self.assertEqual(keycode_reader.read(), None)
        self.assertEqual(len(keycode_reader._unreleased), 2)
        self.assertEqual(keycode_reader.get_unreleased_keys(), combi_1)

        # don't send new wheel down events, it should get released again
        i = 0
        while len(keycode_reader._unreleased) == 2:
            read = keycode_reader.read()
            if i == 100:
                raise AssertionError('Did not release the wheel')
            i += 1
        # and only the comma remains. However, a changed combination is
        # only returned when a new key is pressed. Only then the pressed
        # down keys are collected in a new Key object.
        self.assertEqual(read, None)
        self.assertEqual(keycode_reader.read(), None)
        self.assertEqual(len(keycode_reader._unreleased), 1)
        self.assertEqual(keycode_reader.get_unreleased_keys(), combi_1[1])

        # press down a new key, now it will return a different combination
        keycode_reader._pipe[1].send(new_event(EV_KEY, KEY_A, 1, 1002))
        self.assertEqual(keycode_reader.read(), combi_2)
        self.assertEqual(len(keycode_reader._unreleased), 2)

        # release all of them
        keycode_reader._pipe[1].send(new_event(EV_KEY, KEY_COMMA, 0))
        keycode_reader._pipe[1].send(new_event(EV_KEY, KEY_A, 0))
        self.assertEqual(keycode_reader.read(), None)
        self.assertEqual(len(keycode_reader._unreleased), 0)
        self.assertEqual(keycode_reader.get_unreleased_keys(), None)

    def test_change_wheel_direction(self):
        # not just wheel, anything that suddenly reports a different value.
        # as long as type and code are equal its the same key, so there is no
        # way both directions can be held down.
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

    def test_stop_reading(self):
        keycode_reader.start_reading('device 1')
        time.sleep(0.1)
        self.assertTrue(keycode_reader._process.is_alive())
        keycode_reader.stop_reading()
        time.sleep(0.1)
        self.assertFalse(keycode_reader._process.is_alive())
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
        keycode_reader._pipe[0].send(856794)

        wait(keycode_reader._pipe[0].poll, 0.5)

        self.assertEqual(keycode_reader.read(), (
            (EV_KEY, CODE_1, 1),
            (EV_KEY, CODE_3, 1),
            (EV_ABS, ABS_HAT0X, -1)
        ))
        self.assertEqual(keycode_reader.read(), None)
        self.assertEqual(len(keycode_reader._unreleased), 3)

    def test_reading_3(self):
        # a combination of events via the pipe with reads inbetween
        keycode_reader.start_reading('device 1')

        pipe = keycode_reader._pipe

        pipe[1].send(new_event(EV_KEY, CODE_1, 1, 1001))
        self.assertEqual(keycode_reader.read(), (
            (EV_KEY, CODE_1, 1)
        ))

        pipe[1].send(new_event(EV_ABS, ABS_Y, 1, 1002))
        self.assertEqual(keycode_reader.read(), (
            (EV_KEY, CODE_1, 1),
            (EV_ABS, ABS_Y, 1)
        ))

        pipe[1].send(new_event(EV_ABS, ABS_HAT0X, -1, 1003))
        self.assertEqual(keycode_reader.read(), (
            (EV_KEY, CODE_1, 1),
            (EV_ABS, ABS_Y, 1),
            (EV_ABS, ABS_HAT0X, -1)
        ))

        # adding duplicate down events won't report a different combination.
        # import for triggers, as they keep reporting more down-events before
        # they are released
        pipe[1].send(new_event(EV_ABS, ABS_Y, 1, 1005))
        self.assertEqual(keycode_reader.read(), None)
        pipe[1].send(new_event(EV_ABS, ABS_HAT0X, -1, 1006))
        self.assertEqual(keycode_reader.read(), None)

        pipe[1].send(new_event(EV_KEY, CODE_1, 0, 1004))
        read = keycode_reader.read()
        self.assertEqual(read, None)

        pipe[1].send(new_event(EV_ABS, ABS_Y, 0, 1007))
        self.assertEqual(keycode_reader.read(), None)

        pipe[1].send(new_event(EV_KEY, ABS_HAT0X, 0, 1008))
        self.assertEqual(keycode_reader.read(), None)

    def test_reads_joysticks(self):
        # if their purpose is "buttons"
        custom_mapping.set('gamepad.joystick.left_purpose', BUTTONS)
        pending_events['gamepad'] = [
            new_event(EV_ABS, ABS_Y, MAX_ABS),
            # the value of that one is interpreted as release, because
            # it is too small
            new_event(EV_ABS, ABS_X, MAX_ABS // 10)
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

    def test_combine_triggers(self):
        pipe = multiprocessing.Pipe()
        keycode_reader._pipe = pipe

        i = 0
        def next_timestamp():
            nonlocal i
            i += 1
            return 100 * i

        # based on an observed bug
        pipe[1].send(new_event(3, 1, 0, next_timestamp()))
        pipe[1].send(new_event(3, 0, 0, next_timestamp()))
        pipe[1].send(new_event(3, 2, 1, next_timestamp()))
        self.assertEqual(keycode_reader.read(), (EV_ABS, ABS_Z, 1))
        pipe[1].send(new_event(3, 0, 0, next_timestamp()))
        pipe[1].send(new_event(3, 5, 1, next_timestamp()))
        self.assertEqual(keycode_reader.read(), ((EV_ABS, ABS_Z, 1), (EV_ABS, ABS_RZ, 1)))
        pipe[1].send(new_event(3, 5, 0, next_timestamp()))
        pipe[1].send(new_event(3, 0, 0, next_timestamp()))
        pipe[1].send(new_event(3, 1, 0, next_timestamp()))
        self.assertEqual(keycode_reader.read(), None)
        pipe[1].send(new_event(3, 2, 1, next_timestamp()))
        pipe[1].send(new_event(3, 1, 0, next_timestamp()))
        pipe[1].send(new_event(3, 0, 0, next_timestamp()))
        # due to not properly handling the duplicate down event it cleared
        # the combination and returned it. Instead it should report None
        # and by doing that keep the previous combination.
        self.assertEqual(keycode_reader.read(), None)

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

        # duplicate
        pipe[1].send(new_event(EV_ABS, ABS_Z, 1, 10))
        self.assertEqual(keycode_reader.read(), None)
        self.assertEqual(len(keycode_reader._unreleased), 1)
        self.assertEqual(len(keycode_reader.get_unreleased_keys()), 1)
        self.assertIsInstance(keycode_reader.get_unreleased_keys(), Key)

        # release
        pipe[1].send(new_event(EV_ABS, ABS_Z, 0, 10))
        self.assertEqual(keycode_reader.read(), None)
        self.assertEqual(len(keycode_reader._unreleased), 0)
        self.assertIsNone(keycode_reader.get_unreleased_keys())

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
        keycode_reader.start_reading('device 1')
        pipe = keycode_reader._pipe

        pipe[1].send(new_event(EV_KEY, CODE_1, 1))
        pipe[1].send(new_event(EV_KEY, CODE_2, 1))
        pipe[1].send(new_event(EV_KEY, CODE_3, 1))

        keycode_reader.read()
        self.assertEqual(len(keycode_reader._unreleased), 1)
        self.assertIsNotNone(keycode_reader.previous_event)
        self.assertIsNotNone(keycode_reader.previous_result)

        keycode_reader.clear()
        self.assertEqual(keycode_reader.read(), None)
        self.assertEqual(len(keycode_reader._unreleased), 0)
        self.assertIsNone(keycode_reader.get_unreleased_keys())
        self.assertIsNone(keycode_reader.previous_event)
        self.assertIsNone(keycode_reader.previous_result)

    def test_switch_device(self):
        pending_events['device 2'] = [new_event(EV_KEY, CODE_1, 1)]
        pending_events['device 1'] = [new_event(EV_KEY, CODE_3, 1)]

        keycode_reader.start_reading('device 2')
        time.sleep(EVENT_READ_TIMEOUT * 5)

        keycode_reader.start_reading('device 1')
        time.sleep(EVENT_READ_TIMEOUT * 5)

        self.assertEqual(keycode_reader.read(), (EV_KEY, CODE_3, 1))
        self.assertEqual(keycode_reader.read(), None)

    def test_prioritizing_1_normalize(self):
        # filter the ABS_MISC events of the wacom intuos 5 out that come
        # with every button press. Or more general, prioritize them
        # based on the event type
        pending_events['device 1'] = [
            # all ABS values will be fitted into [-1, 0, 1]
            new_event(EV_ABS, ABS_HAT0X, 5678, 1234.0000),
            new_event(EV_ABS, ABS_HAT0X, 0, 1234.0001),

            new_event(EV_ABS, ABS_HAT0X, 5678, 1235.0000),  # ignored
            new_event(EV_ABS, ABS_HAT0X, 0, 1235.0001),

            new_event(EV_KEY, KEY_COMMA, 1, 1235.0010),
            new_event(EV_KEY, KEY_COMMA, 0, 1235.0011),

            new_event(EV_ABS, ABS_HAT0X, 5678, 1235.0020),  # ignored
            new_event(EV_ABS, ABS_HAT0X, 0, 1235.0021),  # ignored

            new_event(EV_ABS, ABS_HAT0X, 5678, 1236.0000)
        ]
        keycode_reader.start_reading('device 1')
        wait(keycode_reader._pipe[0].poll, 0.5)
        self.assertEqual(keycode_reader.read(), (EV_ABS, ABS_HAT0X, 1))
        self.assertEqual(keycode_reader.read(), None)
        self.assertEqual(len(keycode_reader._unreleased), 1)
        self.assertEqual(
            keycode_reader.get_unreleased_keys(),
            ((EV_ABS, ABS_HAT0X, 1),)
        )

    def test_prioritizing_2(self):
        custom_mapping.set('gamepad.joystick.left_purpose', BUTTONS)

        keycode_reader.start_reading('gamepad')
        pipe = keycode_reader._pipe

        pipe[1].send(new_event(EV_ABS, ABS_HAT0X, 1, 1234.0000)),
        pipe[1].send(new_event(EV_ABS, ABS_MISC, 1, 1235.0000)),
        self.assertEqual(keycode_reader.read(), (
            (EV_ABS, ABS_HAT0X, 1),
            (EV_ABS, ABS_MISC, 1)
        ))

        # will make the previous ABS_MISC event get ignored
        pipe[1].send(new_event(EV_ABS, ABS_Y, 1, 1235.0010)),
        pipe[1].send(new_event(EV_ABS, ABS_MISC, 1, 1235.0020)),  # ignored
        pipe[1].send(new_event(EV_ABS, ABS_MISC, 1, 1235.0030))  # ignored
        # this time, don't release anything. the combination should
        # ignore stuff as well.
        self.assertEqual(keycode_reader.read(), (
            (EV_ABS, ABS_HAT0X, 1),
            (EV_ABS, ABS_Y, 1)
        ))

        self.assertEqual(keycode_reader.read(), None)
        self.assertEqual(len(keycode_reader._unreleased), 2)
        self.assertEqual(keycode_reader.get_unreleased_keys(), (
            (EV_ABS, ABS_HAT0X, 1),
            (EV_ABS, ABS_Y, 1)
        ))
        self.assertIsInstance(keycode_reader.get_unreleased_keys(), Key)

    def test_prioritizing_3_normalize(self):
        # take the sign of -1234, just like in test_prioritizing_2_normalize
        pending_events['device 1'] = [
            # HAT0X usually reports only -1, 0 and 1, but that shouldn't
            # matter. Everything is normalized.
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
