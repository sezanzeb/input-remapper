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
import time
import multiprocessing

import evdev
from evdev.ecodes import EV_ABS, EV_KEY

from keymapper.getdevices import get_devices
from keymapper.gui.reader import reader
from keymapper.gui.helper import RootHelper

from tests.test import InputDevice, quick_cleanup, cleanup, fixtures,\
    new_event, push_events, EVENT_READ_TIMEOUT, START_READING_DELAY


class TestTest(unittest.TestCase):
    def test_stubs(self):
        self.assertIn('device 1', get_devices())

    def tearDown(self):
        quick_cleanup()

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

    def test_push_events(self):
        """Test that push_event works properly between helper and reader.

        Using push_events after the helper is already forked should work,
        as well as using push_event twice
        """
        def create_helper():
            # this will cause pending events to be copied over to the helper
            # process
            def start_helper():
                helper = RootHelper()
                helper.run()

            self.helper = multiprocessing.Process(target=start_helper)
            self.helper.start()
            time.sleep(0.1)

        def wait_for_results():
            # wait for the helper to send stuff
            for _ in range(10):
                time.sleep(EVENT_READ_TIMEOUT)
                if reader._results.poll():
                    break

        event = new_event(EV_KEY, 102, 1)
        create_helper()
        reader.start_reading('device 1')
        time.sleep(START_READING_DELAY)

        push_events('device 1', [event])
        wait_for_results()
        self.assertTrue(reader._results.poll())

        reader.clear()
        self.assertFalse(reader._results.poll())

        # can push more events to the helper that is inside a separate
        # process, which end up being sent to the reader
        push_events('device 1', [event])
        wait_for_results()
        self.assertTrue(reader._results.poll())


if __name__ == "__main__":
    unittest.main()
