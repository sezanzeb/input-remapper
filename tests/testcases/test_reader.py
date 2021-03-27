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
from unittest import mock
import time
import multiprocessing

from evdev.ecodes import EV_KEY, EV_ABS, ABS_HAT0X, KEY_COMMA, \
    BTN_LEFT, BTN_TOOL_DOUBLETAP, ABS_Z, ABS_Y, KEY_A, \
    EV_REL, REL_WHEEL, REL_X, ABS_X, ABS_RZ

from keymapper.gui.reader import reader, will_report_up
from keymapper.state import custom_mapping
from keymapper.config import BUTTONS, MOUSE
from keymapper.key import Key
from keymapper.gui.helper import RootHelper
from keymapper.getdevices import set_devices

from tests.test import new_event, push_events, send_event_to_reader, \
    EVENT_READ_TIMEOUT, START_READING_DELAY, quick_cleanup, MAX_ABS


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
        self.helper = None

    def tearDown(self):
        quick_cleanup()
        if self.helper is not None:
            self.helper.join()

    def create_helper(self):
        # this will cause pending events to be copied over to the helper
        # process
        def start_helper():
            helper = RootHelper()
            helper.run()

        self.helper = multiprocessing.Process(target=start_helper)
        self.helper.start()
        time.sleep(0.1)

    def test_will_report_up(self):
        self.assertFalse(will_report_up(EV_REL))
        self.assertTrue(will_report_up(EV_ABS))
        self.assertTrue(will_report_up(EV_KEY))

    def test_reading_1(self):
        # a single event
        push_events('device 1', [new_event(EV_ABS, ABS_HAT0X, 1)])
        push_events('device 1', [new_event(EV_ABS, REL_X, 1)])  # mouse movements are ignored
        self.create_helper()
        reader.start_reading('device 1')
        time.sleep(0.2)
        self.assertEqual(reader.read(), (EV_ABS, ABS_HAT0X, 1))
        self.assertEqual(reader.read(), None)
        self.assertEqual(len(reader._unreleased), 1)

    def test_reading_wheel(self):
        # will be treated as released automatically at some point
        self.create_helper()
        reader.start_reading('device 1')

        send_event_to_reader(new_event(EV_REL, REL_WHEEL, 0))
        self.assertIsNone(reader.read())

        send_event_to_reader(new_event(EV_REL, REL_WHEEL, 1))
        result = reader.read()
        self.assertIsInstance(result, Key)
        self.assertEqual(result, (EV_REL, REL_WHEEL, 1))
        self.assertEqual(result, ((EV_REL, REL_WHEEL, 1),))
        self.assertNotEqual(result, ((EV_REL, REL_WHEEL, 1), (1, 1, 1)))
        self.assertEqual(result.keys, ((EV_REL, REL_WHEEL, 1),))

        # it won't return the same event twice
        self.assertEqual(reader.read(), None)

        # but it is still remembered unreleased
        self.assertEqual(len(reader._unreleased), 1)
        self.assertEqual(reader.get_unreleased_keys(), (EV_REL, REL_WHEEL, 1))
        self.assertIsInstance(reader.get_unreleased_keys(), Key)

        # as long as new wheel events arrive, it is considered unreleased
        for _ in range(10):
            send_event_to_reader(new_event(EV_REL, REL_WHEEL, 1))
            self.assertEqual(reader.read(), None)
            self.assertEqual(len(reader._unreleased), 1)

        # read a few more times, at some point it is treated as unreleased
        for _ in range(4):
            self.assertEqual(reader.read(), None)
        self.assertEqual(len(reader._unreleased), 0)
        self.assertIsNone(reader.get_unreleased_keys())

        """combinations"""

        send_event_to_reader(new_event(EV_REL, REL_WHEEL, 1, 1000))
        send_event_to_reader(new_event(EV_KEY, KEY_COMMA, 1, 1001))
        combi_1 = ((EV_REL, REL_WHEEL, 1), (EV_KEY, KEY_COMMA, 1))
        combi_2 = ((EV_KEY, KEY_COMMA, 1), (EV_KEY, KEY_A, 1))
        read = reader.read()
        self.assertEqual(read, combi_1)
        self.assertEqual(reader.read(), None)
        self.assertEqual(len(reader._unreleased), 2)
        self.assertEqual(reader.get_unreleased_keys(), combi_1)

        # don't send new wheel down events, it should get released again
        i = 0
        while len(reader._unreleased) == 2:
            read = reader.read()
            if i == 100:
                raise AssertionError('Did not release the wheel')
            i += 1
        # and only the comma remains. However, a changed combination is
        # only returned when a new key is pressed. Only then the pressed
        # down keys are collected in a new Key object.
        self.assertEqual(read, None)
        self.assertEqual(reader.read(), None)
        self.assertEqual(len(reader._unreleased), 1)
        self.assertEqual(reader.get_unreleased_keys(), combi_1[1])

        # press down a new key, now it will return a different combination
        send_event_to_reader(new_event(EV_KEY, KEY_A, 1, 1002))
        self.assertEqual(reader.read(), combi_2)
        self.assertEqual(len(reader._unreleased), 2)

        # release all of them
        send_event_to_reader(new_event(EV_KEY, KEY_COMMA, 0))
        send_event_to_reader(new_event(EV_KEY, KEY_A, 0))
        self.assertEqual(reader.read(), None)
        self.assertEqual(len(reader._unreleased), 0)
        self.assertEqual(reader.get_unreleased_keys(), None)

    def test_change_wheel_direction(self):
        # not just wheel, anything that suddenly reports a different value.
        # as long as type and code are equal its the same key, so there is no
        # way both directions can be held down.
        self.assertEqual(reader.read(), None)
        self.create_helper()
        self.assertEqual(reader.read(), None)
        reader.start_reading('device 1')
        self.assertEqual(reader.read(), None)

        send_event_to_reader(new_event(EV_REL, REL_WHEEL, 1))
        self.assertEqual(reader.read(), (EV_REL, REL_WHEEL, 1))
        self.assertEqual(len(reader._unreleased), 1)
        self.assertEqual(reader.read(), None)

        send_event_to_reader(new_event(EV_REL, REL_WHEEL, -1))
        self.assertEqual(reader.read(), (EV_REL, REL_WHEEL, -1))
        # notice that this is no combination of two sides, the previous
        # entry in unreleased has to get overwritten. So there is still only
        # one element in it.
        self.assertEqual(len(reader._unreleased), 1)
        self.assertEqual(reader.read(), None)

    def test_change_device(self):
        push_events('device 1', [
            new_event(EV_KEY, 1, 1),
        ] * 100)

        push_events('device 2', [
            new_event(EV_KEY, 2, 1),
        ] * 100)

        self.create_helper()

        reader.start_reading('device 1')
        time.sleep(0.1)
        self.assertEqual(reader.read(), Key(EV_KEY, 1, 1))

        reader.start_reading('device 2')

        # it's plausible that right after sending the new read command more
        # events from the old device might still appear. Give the helper
        # some time to handle the new command.
        time.sleep(0.1)
        reader.clear()

        time.sleep(0.1)
        self.assertEqual(reader.read(), Key(EV_KEY, 2, 1))

    def test_reading_2(self):
        # a combination of events
        push_events('device 1', [
            new_event(EV_KEY, CODE_1, 1, 10000.1234),
            new_event(EV_KEY, CODE_3, 1, 10001.1234),
            new_event(EV_ABS, ABS_HAT0X, -1, 10002.1234)
        ])
        self.create_helper()
        reader.start_reading('device 1')

        # sending anything arbitrary does not stop the helper
        reader._commands.send(856794)

        time.sleep(0.2)

        self.assertEqual(reader.read(), (
            (EV_KEY, CODE_1, 1),
            (EV_KEY, CODE_3, 1),
            (EV_ABS, ABS_HAT0X, -1)
        ))
        self.assertEqual(reader.read(), None)
        self.assertEqual(len(reader._unreleased), 3)

    def test_reading_3(self):
        self.create_helper()
        # a combination of events via Socket with reads inbetween
        reader.start_reading('gamepad')

        send_event_to_reader(new_event(EV_KEY, CODE_1, 1, 1001))
        self.assertEqual(reader.read(), (
            (EV_KEY, CODE_1, 1)
        ))

        custom_mapping.set('gamepad.joystick.left_purpose', BUTTONS)
        send_event_to_reader(new_event(EV_ABS, ABS_Y, 1, 1002))
        self.assertEqual(reader.read(), (
            (EV_KEY, CODE_1, 1),
            (EV_ABS, ABS_Y, 1)
        ))

        send_event_to_reader(new_event(EV_ABS, ABS_HAT0X, -1, 1003))
        self.assertEqual(reader.read(), (
            (EV_KEY, CODE_1, 1),
            (EV_ABS, ABS_Y, 1),
            (EV_ABS, ABS_HAT0X, -1)
        ))

        # adding duplicate down events won't report a different combination.
        # import for triggers, as they keep reporting more down-events before
        # they are released
        send_event_to_reader(new_event(EV_ABS, ABS_Y, 1, 1005))
        self.assertEqual(reader.read(), None)
        send_event_to_reader(new_event(EV_ABS, ABS_HAT0X, -1, 1006))
        self.assertEqual(reader.read(), None)

        send_event_to_reader(new_event(EV_KEY, CODE_1, 0, 1004))
        read = reader.read()
        self.assertEqual(read, None)

        send_event_to_reader(new_event(EV_ABS, ABS_Y, 0, 1007))
        self.assertEqual(reader.read(), None)

        send_event_to_reader(new_event(EV_KEY, ABS_HAT0X, 0, 1008))
        self.assertEqual(reader.read(), None)

    def test_reads_joysticks(self):
        # if their purpose is "buttons"
        custom_mapping.set('gamepad.joystick.left_purpose', BUTTONS)
        push_events('gamepad', [
            new_event(EV_ABS, ABS_Y, MAX_ABS),
            # the value of that one is interpreted as release, because
            # it is too small
            new_event(EV_ABS, ABS_X, MAX_ABS // 10)
        ])
        self.create_helper()

        reader.start_reading('gamepad')
        time.sleep(0.2)
        self.assertEqual(reader.read(), (EV_ABS, ABS_Y, 1))
        self.assertEqual(reader.read(), None)
        self.assertEqual(len(reader._unreleased), 1)

        reader._unreleased = {}
        custom_mapping.set('gamepad.joystick.left_purpose', MOUSE)
        push_events('gamepad', [
            new_event(EV_ABS, ABS_Y, MAX_ABS)
        ])
        self.create_helper()

        reader.start_reading('gamepad')
        time.sleep(0.1)
        self.assertEqual(reader.read(), None)
        self.assertEqual(len(reader._unreleased), 0)

    def test_combine_triggers(self):
        reader.start_reading('device 1')

        i = 0

        def next_timestamp():
            nonlocal i
            i += 1
            return time.time() + i

        # based on an observed bug
        send_event_to_reader(new_event(3, 1, 0, next_timestamp()))
        send_event_to_reader(new_event(3, 0, 0, next_timestamp()))
        send_event_to_reader(new_event(3, 2, 1, next_timestamp()))
        self.assertEqual(reader.read(), (EV_ABS, ABS_Z, 1))
        send_event_to_reader(new_event(3, 0, 0, next_timestamp()))
        send_event_to_reader(new_event(3, 5, 1, next_timestamp()))
        self.assertEqual(reader.read(), ((EV_ABS, ABS_Z, 1), (EV_ABS, ABS_RZ, 1)))
        send_event_to_reader(new_event(3, 5, 0, next_timestamp()))
        send_event_to_reader(new_event(3, 0, 0, next_timestamp()))
        send_event_to_reader(new_event(3, 1, 0, next_timestamp()))
        self.assertEqual(reader.read(), None)
        send_event_to_reader(new_event(3, 2, 1, next_timestamp()))
        send_event_to_reader(new_event(3, 1, 0, next_timestamp()))
        send_event_to_reader(new_event(3, 0, 0, next_timestamp()))
        # due to not properly handling the duplicate down event it cleared
        # the combination and returned it. Instead it should report None
        # and by doing that keep the previous combination.
        self.assertEqual(reader.read(), None)

    def test_ignore_btn_left(self):
        # click events are ignored because overwriting them would render the
        # mouse useless, but a mouse is needed to stop the injection
        # comfortably. Furthermore, reading mouse events breaks clicking
        # around in the table. It can still be changed in the config files.
        push_events('device 1', [
            new_event(EV_KEY, BTN_LEFT, 1),
            new_event(EV_KEY, CODE_2, 1),
            new_event(EV_KEY, BTN_TOOL_DOUBLETAP, 1),
        ])
        self.create_helper()
        reader.start_reading('device 1')
        time.sleep(0.1)
        self.assertEqual(reader.read(), (EV_KEY, CODE_2, 1))
        self.assertEqual(reader.read(), None)
        self.assertEqual(len(reader._unreleased), 1)

    def test_ignore_value_2(self):
        # this is not a combination, because (EV_KEY CODE_3, 2) is ignored
        push_events('device 1', [
            new_event(EV_ABS, ABS_HAT0X, 1),
            new_event(EV_KEY, CODE_3, 2)
        ])
        self.create_helper()
        reader.start_reading('device 1')
        time.sleep(0.2)
        self.assertEqual(reader.read(), (EV_ABS, ABS_HAT0X, 1))
        self.assertEqual(reader.read(), None)
        self.assertEqual(len(reader._unreleased), 1)

    def test_reading_ignore_up(self):
        push_events('device 1', [
            new_event(EV_KEY, CODE_1, 0, 10),
            new_event(EV_KEY, CODE_2, 1, 11),
            new_event(EV_KEY, CODE_3, 0, 12),
        ])
        self.create_helper()
        reader.start_reading('device 1')
        time.sleep(0.1)
        self.assertEqual(reader.read(), (EV_KEY, CODE_2, 1))
        self.assertEqual(reader.read(), None)
        self.assertEqual(len(reader._unreleased), 1)

    def test_reading_ignore_duplicate_down(self):
        send_event_to_reader(new_event(EV_ABS, ABS_Z, 1, 10))

        self.assertEqual(reader.read(), (EV_ABS, ABS_Z, 1))
        self.assertEqual(reader.read(), None)

        # duplicate
        send_event_to_reader(new_event(EV_ABS, ABS_Z, 1, 10))
        self.assertEqual(reader.read(), None)
        self.assertEqual(len(reader._unreleased), 1)
        self.assertEqual(len(reader.get_unreleased_keys()), 1)
        self.assertIsInstance(reader.get_unreleased_keys(), Key)

        # release
        send_event_to_reader(new_event(EV_ABS, ABS_Z, 0, 10))
        self.assertEqual(reader.read(), None)
        self.assertEqual(len(reader._unreleased), 0)
        self.assertIsNone(reader.get_unreleased_keys())

    def test_wrong_device(self):
        push_events('device 1', [
            new_event(EV_KEY, CODE_1, 1),
            new_event(EV_KEY, CODE_2, 1),
            new_event(EV_KEY, CODE_3, 1)
        ])
        self.create_helper()
        reader.start_reading('device 2')
        time.sleep(EVENT_READ_TIMEOUT * 5)
        self.assertEqual(reader.read(), None)
        self.assertEqual(len(reader._unreleased), 0)

    def test_keymapper_devices(self):
        # Don't read from keymapper devices, their keycodes are not
        # representative for the original key. As long as this is not
        # intentionally programmed it won't even do that. But it was at some
        # point.
        push_events('key-mapper device 2', [
            new_event(EV_KEY, CODE_1, 1),
            new_event(EV_KEY, CODE_2, 1),
            new_event(EV_KEY, CODE_3, 1)
        ])
        self.create_helper()
        reader.start_reading('device 2')
        time.sleep(EVENT_READ_TIMEOUT * 5)
        self.assertEqual(reader.read(), None)
        self.assertEqual(len(reader._unreleased), 0)

    def test_clear(self):
        push_events('device 1', [
            new_event(EV_KEY, CODE_1, 1),
            new_event(EV_KEY, CODE_2, 1),
            new_event(EV_KEY, CODE_3, 1)
        ] * 15)

        self.create_helper()
        reader.start_reading('device 1')
        time.sleep(START_READING_DELAY + EVENT_READ_TIMEOUT * 3)

        reader.read()
        self.assertEqual(len(reader._unreleased), 3)
        self.assertIsNotNone(reader.previous_event)
        self.assertIsNotNone(reader.previous_result)

        # make the helper send more events to the reader
        time.sleep(EVENT_READ_TIMEOUT * 2)
        self.assertTrue(reader._results.poll())
        reader.clear()

        self.assertFalse(reader._results.poll())
        self.assertEqual(reader.read(), None)
        self.assertEqual(len(reader._unreleased), 0)
        self.assertIsNone(reader.get_unreleased_keys())
        self.assertIsNone(reader.previous_event)
        self.assertIsNone(reader.previous_result)
        self.tearDown()

    def test_switch_device(self):
        push_events('device 2', [new_event(EV_KEY, CODE_1, 1)])
        push_events('device 1', [new_event(EV_KEY, CODE_3, 1)])
        self.create_helper()

        reader.start_reading('device 2')
        self.assertFalse(reader._results.poll())
        self.assertEqual(reader.device_name, 'device 2')
        time.sleep(EVENT_READ_TIMEOUT * 5)

        self.assertTrue(reader._results.poll())
        reader.start_reading('device 1')
        self.assertEqual(reader.device_name, 'device 1')
        self.assertFalse(reader._results.poll())  # pipe resets

        time.sleep(EVENT_READ_TIMEOUT * 5)
        self.assertTrue(reader._results.poll())

        self.assertEqual(reader.read(), (EV_KEY, CODE_3, 1))
        self.assertEqual(reader.read(), None)
        self.assertEqual(len(reader._unreleased), 1)

    def test_terminate(self):
        self.create_helper()
        reader.start_reading('device 1')

        push_events('device 1', [new_event(EV_KEY, CODE_3, 1)])
        time.sleep(START_READING_DELAY + EVENT_READ_TIMEOUT)
        self.assertTrue(reader._results.poll())

        reader.terminate()
        reader.clear()
        time.sleep(EVENT_READ_TIMEOUT)

        # no new events arrive after terminating
        push_events('device 1', [new_event(EV_KEY, CODE_3, 1)])
        time.sleep(EVENT_READ_TIMEOUT * 3)
        self.assertFalse(reader._results.poll())

    def test_are_new_devices_available(self):
        self.create_helper()
        set_devices({})

        # read stuff from the helper, which includes the devices
        self.assertFalse(reader.are_new_devices_available())
        reader.read()

        self.assertTrue(reader.are_new_devices_available())


if __name__ == "__main__":
    unittest.main()
