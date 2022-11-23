#!/usr/bin/python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2022 sezanzeb <proxima@sezanzeb.de>
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

from inputremapper.gui.messages.message_broker import MessageBroker
from tests.fixtures import new_event
from tests.cleanup import cleanup, quick_cleanup
from tests.constants import EVENT_READ_TIMEOUT, START_READING_DELAY
from tests.logger import logger
from tests.fixtures import fixtures
from tests.pipes import push_events
from tests.patches import InputDevice

import os
import unittest
import time
import multiprocessing

import evdev
from evdev.ecodes import EV_ABS, EV_KEY

from inputremapper.groups import groups, _Groups
from inputremapper.gui.reader_client import ReaderClient
from inputremapper.gui.reader_service import ReaderService


class TestTest(unittest.TestCase):
    def test_stubs(self):
        self.assertIsNotNone(groups.find(key="Foo Device 2"))

    def tearDown(self):
        quick_cleanup()

    def test_fake_capabilities(self):
        device = InputDevice("/dev/input/event30")
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
        fixtures["/bar/dev"] = {"name": "bla"}
        cleanup()
        self.assertIsNone(fixtures.get("/bar/dev"))
        self.assertIsNotNone(fixtures.get("/dev/input/event11"))

    def test_restore_os_environ(self):
        os.environ["foo"] = "bar"
        del os.environ["USER"]
        environ = os.environ
        cleanup()
        self.assertIn("USER", environ)
        self.assertNotIn("foo", environ)

    def test_push_events(self):
        """Test that push_event works properly between reader service and client.

        Using push_events after the reader-service is already started should work,
        as well as using push_event twice
        """
        reader_client = ReaderClient(MessageBroker(), groups)

        def create_reader_service():
            # this will cause pending events to be copied over to the reader-service
            # process
            def start_reader_service():
                # there is no point in using the global groups object
                # because the reader-service runs in a different process
                reader_service = ReaderService(_Groups())
                reader_service.run()

            self.reader_service = multiprocessing.Process(target=start_reader_service)
            self.reader_service.start()
            time.sleep(0.1)

        def wait_for_results():
            # wait for the reader-service to send stuff
            for _ in range(10):
                time.sleep(EVENT_READ_TIMEOUT)
                if reader_client._results_pipe.poll():
                    break

        create_reader_service()
        reader_client.set_group(groups.find(key="Foo Device 2"))
        reader_client.start_recorder()
        time.sleep(START_READING_DELAY)

        event = new_event(EV_KEY, 102, 1)
        push_events(fixtures.foo_device_2_keyboard, [event])
        wait_for_results()
        self.assertTrue(reader_client._results_pipe.poll())

        reader_client._read()
        self.assertFalse(reader_client._results_pipe.poll())

        # can push more events to the reader-service that is inside a separate
        # process, which end up being sent to the reader
        event = new_event(EV_KEY, 102, 0)
        logger.info("push_events")
        push_events(fixtures.foo_device_2_keyboard, [event])
        wait_for_results()
        logger.info("assert")
        self.assertTrue(reader_client._results_pipe.poll())

        reader_client.terminate()


if __name__ == "__main__":
    unittest.main()
