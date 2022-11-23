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

import os
import json
import multiprocessing
import time
import unittest
from typing import List, Optional
from unittest.mock import patch, MagicMock

from evdev.ecodes import (
    EV_KEY,
    EV_ABS,
    ABS_HAT0X,
    KEY_COMMA,
    BTN_TOOL_DOUBLETAP,
    KEY_A,
    EV_REL,
    REL_WHEEL,
    REL_X,
    ABS_X,
    REL_HWHEEL,
)

from inputremapper.event_combination import EventCombination
from inputremapper.groups import _Groups, DeviceType
from inputremapper.gui.messages.message_broker import (
    MessageBroker,
    Signal,
)
from inputremapper.gui.messages.message_data import CombinationRecorded
from inputremapper.gui.messages.message_types import MessageType
from inputremapper.gui.reader_client import ReaderClient
from inputremapper.gui.reader_service import ReaderService
from tests.test import (
    new_event,
    EVENT_READ_TIMEOUT,
    START_READING_DELAY,
    quick_cleanup,
    MAX_ABS,
    MIN_ABS,
)
from tests.pipes import push_event, push_events
from tests.fixtures import fixtures

CODE_1 = 100
CODE_2 = 101
CODE_3 = 102


class Listener:
    def __init__(self):
        self.calls: List = []

    def __call__(self, data):
        self.calls.append(data)


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
        self.reader_service = None
        self.groups = _Groups()
        self.message_broker = MessageBroker()
        self.reader_client = ReaderClient(self.message_broker, self.groups)

    def tearDown(self):
        quick_cleanup()
        try:
            self.reader_client.terminate()
        except (BrokenPipeError, OSError):
            pass

        if self.reader_service is not None:
            self.reader_service.join()

    def create_reader_service(self, groups: Optional[_Groups] = None):
        # this will cause pending events to be copied over to the reader-service
        # process
        if not groups:
            groups = self.groups

        def start_reader_service():
            reader_service = ReaderService(groups)
            reader_service.run()

        self.reader_service = multiprocessing.Process(target=start_reader_service)
        self.reader_service.start()
        time.sleep(0.1)

    def test_reading(self):
        l1 = Listener()
        l2 = Listener()
        self.message_broker.subscribe(MessageType.combination_recorded, l1)
        self.message_broker.subscribe(MessageType.recording_finished, l2)
        self.create_reader_service()
        self.reader_client.set_group(self.groups.find(key="Foo Device 2"))
        self.reader_client.start_recorder()

        push_events(fixtures.foo_device_2_gamepad, [new_event(EV_ABS, ABS_HAT0X, 1)])
        # we need to sleep because we have two different fixtures,
        # which will lead to race conditions
        time.sleep(0.1)

        # relative axis events should be released automagically after 0.3s
        push_events(fixtures.foo_device_2_mouse, [new_event(EV_REL, REL_X, 5)])
        time.sleep(0.1)
        # read all pending events. Having a glib mainloop would be better,
        # as it would call read automatically periodically
        self.reader_client._read()
        self.assertEqual(
            [
                CombinationRecorded(EventCombination.from_string("3,16,1")),
                CombinationRecorded(EventCombination.from_string("3,16,1+2,0,1")),
            ],
            l1.calls,
        )

        # release the hat switch should emit the recording finished event
        # as both the hat and relative axis are released by now
        push_events(fixtures.foo_device_2_gamepad, [new_event(EV_ABS, ABS_HAT0X, 0)])
        time.sleep(0.3)
        self.reader_client._read()
        self.assertEqual([Signal(MessageType.recording_finished)], l2.calls)

    def test_should_release_relative_axis(self):
        # the timeout is set to 0.3s
        l1 = Listener()
        l2 = Listener()
        self.message_broker.subscribe(MessageType.combination_recorded, l1)
        self.message_broker.subscribe(MessageType.recording_finished, l2)
        self.create_reader_service()
        self.reader_client.set_group(self.groups.find(key="Foo Device 2"))
        self.reader_client.start_recorder()

        push_events(fixtures.foo_device_2_mouse, [new_event(EV_REL, REL_X, -5)])
        time.sleep(0.1)
        self.reader_client._read()

        self.assertEqual(
            [CombinationRecorded(EventCombination.from_string("2,0,-1"))],
            l1.calls,
        )
        self.assertEqual([], l2.calls)  # no stop recording yet

        time.sleep(0.3)
        self.reader_client._read()
        self.assertEqual([Signal(MessageType.recording_finished)], l2.calls)

    def test_should_not_trigger_at_low_speed_for_rel_axis(self):
        l1 = Listener()
        self.message_broker.subscribe(MessageType.combination_recorded, l1)
        self.create_reader_service()
        self.reader_client.set_group(self.groups.find(key="Foo Device 2"))
        self.reader_client.start_recorder()

        push_events(fixtures.foo_device_2_mouse, [new_event(EV_REL, REL_X, -1)])
        time.sleep(0.1)
        self.reader_client._read()
        self.assertEqual(0, len(l1.calls))

    def test_should_trigger_wheel_at_low_speed(self):
        l1 = Listener()
        self.message_broker.subscribe(MessageType.combination_recorded, l1)
        self.create_reader_service()
        self.reader_client.set_group(self.groups.find(key="Foo Device 2"))
        self.reader_client.start_recorder()

        push_events(
            fixtures.foo_device_2_mouse,
            [new_event(EV_REL, REL_WHEEL, -1), new_event(EV_REL, REL_HWHEEL, 1)],
        )
        time.sleep(0.1)
        self.reader_client._read()

        self.assertEqual(
            [
                CombinationRecorded(EventCombination.from_string("2,8,-1")),
                CombinationRecorded(EventCombination.from_string("2,8,-1+2,6,1")),
            ],
            l1.calls,
        )

    def test_wont_emit_the_same_combination_twice(self):
        l1 = Listener()
        self.message_broker.subscribe(MessageType.combination_recorded, l1)
        self.create_reader_service()
        self.reader_client.set_group(self.groups.find(key="Foo Device 2"))
        self.reader_client.start_recorder()

        push_events(fixtures.foo_device_2_keyboard, [new_event(EV_KEY, KEY_A, 1)])
        time.sleep(0.1)
        self.reader_client._read()
        # the duplicate event should be ignored
        push_events(fixtures.foo_device_2_keyboard, [new_event(EV_KEY, KEY_A, 1)])
        time.sleep(0.1)
        self.reader_client._read()

        self.assertEqual(
            [CombinationRecorded(EventCombination.from_string("1,30,1"))],
            l1.calls,
        )

    def test_should_read_absolut_axis(self):
        l1 = Listener()
        l2 = Listener()
        self.message_broker.subscribe(MessageType.combination_recorded, l1)
        self.message_broker.subscribe(MessageType.recording_finished, l2)
        self.create_reader_service()
        self.reader_client.set_group(self.groups.find(key="Foo Device 2"))
        self.reader_client.start_recorder()

        # over 30% should trigger
        push_events(
            fixtures.foo_device_2_gamepad,
            [new_event(EV_ABS, ABS_X, int(MAX_ABS * 0.4))],
        )
        time.sleep(0.1)
        self.reader_client._read()
        self.assertEqual(
            [CombinationRecorded(EventCombination.from_string("3,0,1"))],
            l1.calls,
        )
        self.assertEqual([], l2.calls)  # no stop recording yet

        # less the 30% should release
        push_events(
            fixtures.foo_device_2_gamepad,
            [new_event(EV_ABS, ABS_X, int(MAX_ABS * 0.2))],
        )
        time.sleep(0.1)
        self.reader_client._read()
        self.assertEqual(
            [CombinationRecorded(EventCombination.from_string("3,0,1"))],
            l1.calls,
        )
        self.assertEqual([Signal(MessageType.recording_finished)], l2.calls)

    def test_should_change_direction(self):
        l1 = Listener()
        self.message_broker.subscribe(MessageType.combination_recorded, l1)
        self.create_reader_service()
        self.reader_client.set_group(self.groups.find(key="Foo Device 2"))
        self.reader_client.start_recorder()

        push_event(fixtures.foo_device_2_keyboard, new_event(EV_KEY, KEY_A, 1))
        time.sleep(0.1)
        push_event(
            fixtures.foo_device_2_gamepad, new_event(EV_ABS, ABS_X, int(MAX_ABS * 0.4))
        )
        time.sleep(0.1)
        push_event(fixtures.foo_device_2_keyboard, new_event(EV_KEY, KEY_COMMA, 1))
        time.sleep(0.1)
        push_events(
            fixtures.foo_device_2_gamepad,
            [
                new_event(EV_ABS, ABS_X, int(MAX_ABS * 0.1)),
                new_event(EV_ABS, ABS_X, int(MIN_ABS * 0.4)),
            ],
        )
        time.sleep(0.1)
        self.reader_client._read()
        self.assertEqual(
            [
                CombinationRecorded(EventCombination.from_string("1,30,1")),
                CombinationRecorded(EventCombination.from_string("1,30,1+3,0,1")),
                CombinationRecorded(
                    EventCombination.from_string("1,30,1+3,0,1+1,51,1")
                ),
                CombinationRecorded(
                    EventCombination.from_string("1,30,1+3,0,-1+1,51,1")
                ),
            ],
            l1.calls,
        )

    def test_change_device(self):
        l1 = Listener()
        self.message_broker.subscribe(MessageType.combination_recorded, l1)

        push_events(
            fixtures.foo_device_2_keyboard,
            [
                new_event(EV_KEY, 1, 1),
            ]
            * 10,
        )

        push_events(
            fixtures.bar_device,
            [
                new_event(EV_KEY, 2, 1),
                new_event(EV_KEY, 2, 0),
            ]
            * 3,
        )

        self.create_reader_service()
        self.reader_client.set_group(self.groups.find(key="Foo Device 2"))
        self.reader_client.start_recorder()
        time.sleep(0.1)
        self.reader_client._read()
        self.assertEqual(l1.calls[0].combination, EventCombination((EV_KEY, 1, 1)))

        self.reader_client.set_group(self.groups.find(name="Bar Device"))
        time.sleep(0.1)
        self.reader_client._read()

        # we did not get the event from the "Bar Device" because the group change
        # stopped the recording
        self.assertEqual(len(l1.calls), 1)

        self.reader_client.start_recorder()
        push_events(fixtures.bar_device, [new_event(EV_KEY, 2, 1)])
        time.sleep(0.1)
        self.reader_client._read()
        self.assertEqual(l1.calls[1].combination, EventCombination((EV_KEY, 2, 1)))

    def test_reading_2(self):
        l1 = Listener()
        self.message_broker.subscribe(MessageType.combination_recorded, l1)
        # a combination of events
        push_events(
            fixtures.foo_device_2_keyboard,
            [
                new_event(EV_KEY, CODE_1, 1, 10000.1234),
                new_event(EV_KEY, CODE_3, 1, 10001.1234),
            ],
        )

        pipe = multiprocessing.Pipe()

        def refresh():
            # from within the reader-service process notify this test that
            # refresh was called as expected
            pipe[1].send("refreshed")

        groups = _Groups()
        groups.refresh = refresh
        self.create_reader_service(groups)

        self.reader_client.set_group(self.groups.find(key="Foo Device 2"))
        self.reader_client.start_recorder()

        # sending anything arbitrary does not stop the reader-service
        self.reader_client._commands_pipe.send(856794)
        time.sleep(0.2)
        push_events(
            fixtures.foo_device_2_gamepad,
            [new_event(EV_ABS, ABS_HAT0X, -1, 10002.1234)],
        )
        time.sleep(0.1)
        # but it makes it look for new devices because maybe its list of
        # self.groups is not up-to-date
        self.assertTrue(pipe[0].poll())
        self.assertEqual(pipe[0].recv(), "refreshed")

        self.reader_client._read()
        self.assertEqual(
            l1.calls[-1].combination,
            ((EV_KEY, CODE_1, 1), (EV_KEY, CODE_3, 1), (EV_ABS, ABS_HAT0X, -1)),
        )

    def test_blacklisted_events(self):
        l1 = Listener()
        self.message_broker.subscribe(MessageType.combination_recorded, l1)

        push_events(
            fixtures.foo_device_2_mouse,
            [
                new_event(EV_KEY, BTN_TOOL_DOUBLETAP, 1),
                new_event(EV_KEY, CODE_2, 1),
                new_event(EV_KEY, BTN_TOOL_DOUBLETAP, 1),
            ],
            force=True,
        )
        self.create_reader_service()
        self.reader_client.set_group(self.groups.find(key="Foo Device 2"))
        self.reader_client.start_recorder()
        time.sleep(0.1)
        self.reader_client._read()
        self.assertEqual(
            l1.calls[-1].combination, EventCombination((EV_KEY, CODE_2, 1))
        )

    def test_ignore_value_2(self):
        l1 = Listener()
        self.message_broker.subscribe(MessageType.combination_recorded, l1)
        # this is not a combination, because (EV_KEY CODE_3, 2) is ignored
        push_events(
            fixtures.foo_device_2_gamepad,
            [new_event(EV_ABS, ABS_HAT0X, 1), new_event(EV_KEY, CODE_3, 2)],
            force=True,
        )
        self.create_reader_service()
        self.reader_client.set_group(self.groups.find(key="Foo Device 2"))
        self.reader_client.start_recorder()
        time.sleep(0.2)
        self.reader_client._read()
        self.assertEqual(
            l1.calls[-1].combination, EventCombination((EV_ABS, ABS_HAT0X, 1))
        )

    def test_reading_ignore_up(self):
        l1 = Listener()
        self.message_broker.subscribe(MessageType.combination_recorded, l1)
        push_events(
            fixtures.foo_device_2_keyboard,
            [
                new_event(EV_KEY, CODE_1, 0, 10),
                new_event(EV_KEY, CODE_2, 1, 11),
                new_event(EV_KEY, CODE_3, 0, 12),
            ],
        )
        self.create_reader_service()
        self.reader_client.set_group(self.groups.find(key="Foo Device 2"))
        self.reader_client.start_recorder()
        time.sleep(0.1)
        self.reader_client._read()
        self.assertEqual(
            l1.calls[-1].combination, EventCombination((EV_KEY, CODE_2, 1))
        )

    def test_wrong_device(self):
        l1 = Listener()
        self.message_broker.subscribe(MessageType.combination_recorded, l1)

        push_events(
            fixtures.foo_device_2_keyboard,
            [
                new_event(EV_KEY, CODE_1, 1),
                new_event(EV_KEY, CODE_2, 1),
                new_event(EV_KEY, CODE_3, 1),
            ],
        )
        self.create_reader_service()
        self.reader_client.set_group(self.groups.find(name="Bar Device"))
        self.reader_client.start_recorder()
        time.sleep(EVENT_READ_TIMEOUT * 5)
        self.reader_client._read()
        self.assertEqual(len(l1.calls), 0)

    def test_inputremapper_devices(self):
        # Don't read from inputremapper devices, their keycodes are not
        # representative for the original key. As long as this is not
        # intentionally programmed it won't even do that. But it was at some
        # point.
        l1 = Listener()
        self.message_broker.subscribe(MessageType.combination_recorded, l1)
        push_events(
            fixtures.input_remapper_bar_device,
            [
                new_event(EV_KEY, CODE_1, 1),
                new_event(EV_KEY, CODE_2, 1),
                new_event(EV_KEY, CODE_3, 1),
            ],
        )
        self.create_reader_service()
        self.reader_client.set_group(self.groups.find(name="Bar Device"))
        self.reader_client.start_recorder()
        time.sleep(EVENT_READ_TIMEOUT * 5)
        self.reader_client._read()
        self.assertEqual(len(l1.calls), 0)

    def test_terminate(self):
        self.create_reader_service()
        self.reader_client.set_group(self.groups.find(key="Foo Device 2"))

        push_events(fixtures.foo_device_2_keyboard, [new_event(EV_KEY, CODE_3, 1)])
        time.sleep(START_READING_DELAY + EVENT_READ_TIMEOUT)
        self.assertTrue(self.reader_client._results_pipe.poll())

        self.reader_client.terminate()
        time.sleep(EVENT_READ_TIMEOUT)
        self.assertFalse(self.reader_client._results_pipe.poll())

        # no new events arrive after terminating
        push_events(fixtures.foo_device_2_keyboard, [new_event(EV_KEY, CODE_3, 1)])
        time.sleep(EVENT_READ_TIMEOUT * 3)
        self.assertFalse(self.reader_client._results_pipe.poll())

    def test_are_new_groups_available(self):
        l1 = Listener()
        self.message_broker.subscribe(MessageType.groups, l1)
        self.create_reader_service()
        self.reader_client.groups.set_groups([])

        time.sleep(0.1)  # let the reader-service send the groups
        # read stuff from the reader-service, which includes the devices
        self.assertEqual("[]", self.reader_client.groups.dumps())
        self.reader_client._read()

        self.assertEqual(
            self.reader_client.groups.dumps(),
            json.dumps(
                [
                    json.dumps(
                        {
                            "paths": [
                                "/dev/input/event1",
                            ],
                            "names": ["Foo Device"],
                            "types": [DeviceType.KEYBOARD],
                            "key": "Foo Device",
                        }
                    ),
                    json.dumps(
                        {
                            "paths": [
                                "/dev/input/event11",
                                "/dev/input/event10",
                                "/dev/input/event13",
                                "/dev/input/event15",
                            ],
                            "names": [
                                "Foo Device foo",
                                "Foo Device",
                                "Foo Device",
                                "Foo Device bar",
                            ],
                            "types": [
                                DeviceType.GAMEPAD,
                                DeviceType.KEYBOARD,
                                DeviceType.MOUSE,
                            ],
                            "key": "Foo Device 2",
                        }
                    ),
                    json.dumps(
                        {
                            "paths": ["/dev/input/event20"],
                            "names": ["Bar Device"],
                            "types": [DeviceType.KEYBOARD],
                            "key": "Bar Device",
                        }
                    ),
                    json.dumps(
                        {
                            "paths": ["/dev/input/event30"],
                            "names": ["gamepad"],
                            "types": [DeviceType.GAMEPAD],
                            "key": "gamepad",
                        }
                    ),
                    json.dumps(
                        {
                            "paths": ["/dev/input/event40"],
                            "names": ["input-remapper Bar Device"],
                            "types": [DeviceType.KEYBOARD],
                            "key": "input-remapper Bar Device",
                        }
                    ),
                    json.dumps(
                        {
                            "paths": ["/dev/input/event52"],
                            "names": ["Qux/Device?"],
                            "types": [DeviceType.KEYBOARD],
                            "key": "Qux/Device?",
                        }
                    ),
                ]
            ),
        )

        self.assertEqual(len(l1.calls), 1)  # ensure we got the event

    def test_starts_the_service(self):
        # if ReaderClient can't see the ReaderService, a new ReaderService should
        # be started via pkexec
        with patch.object(ReaderService, "is_running", lambda: False):
            os_system_mock = MagicMock(return_value=0)
            with patch.object(os, "system", os_system_mock):
                # the status message enables the reader-client to see, that the
                # reader-service has started
                self.reader_client._results_pipe.send(
                    {"type": "status", "message": "ready"}
                )
                self.reader_client._send_command("foo")
                os_system_mock.assert_called_once_with(
                    "pkexec input-remapper-control --command start-reader-service -d"
                )

    def test_wont_start_the_service(self):
        # already running, no call to os.system
        with patch.object(ReaderService, "is_running", lambda: True):
            mock = MagicMock(return_value=0)
            with patch.object(os, "system", mock):
                self.reader_client._send_command("foo")
                mock.assert_not_called()

    def test_reader_service_wont_start(self):
        # test for the "The reader-service did not start" message

        expected_msg = "The reader-service did not start"
        subscribe_mock = MagicMock()
        self.message_broker.subscribe(MessageType.status_msg, subscribe_mock)

        with patch.object(ReaderClient, "_timeout", 1):
            with patch.object(ReaderService, "is_running", lambda: False):
                os_system_mock = MagicMock(return_value=0)
                with patch.object(os, "system", os_system_mock):
                    self.reader_client._send_command("foo")
                    # no message is sent into _results_pipe, so the reader-client will
                    # think the reader-service didn't manage to start
                    os_system_mock.assert_called_once_with(
                        "pkexec input-remapper-control "
                        "--command start-reader-service -d"
                    )

        subscribe_mock.assert_called_once()
        status = subscribe_mock.call_args[0][0]
        self.assertEqual(status.msg, expected_msg)

    def test_reader_service_times_out(self):
        # after some time the reader-service just stops, to avoid leaving a hole
        # that exposes user-input forever
        with patch.object(ReaderService, "_maximum_lifetime", 1):
            self.create_reader_service()
            self.assertTrue(self.reader_service.is_alive())
            time.sleep(0.5)
            self.assertTrue(self.reader_service.is_alive())
            time.sleep(1)
            self.assertFalse(self.reader_service.is_alive())

    def test_reader_service_waits_for_client_to_finish(self):
        # if the client is currently reading, it waits a bit longer until the
        # client finishes reading
        with patch.object(ReaderService, "_maximum_lifetime", 1):
            self.create_reader_service()
            self.assertTrue(self.reader_service.is_alive())

            self.reader_client.set_group(self.groups.find(key="Foo Device 2"))
            self.reader_client.start_recorder()

            time.sleep(2)
            # still alive, without start_recorder it should have already exited
            self.assertTrue(self.reader_service.is_alive())

            self.reader_client.stop_recorder()

            time.sleep(1)
            self.assertFalse(self.reader_service.is_alive())

    def test_reader_service_wont_wait_forever(self):
        # if the client is reading forever, stop it after another timeout
        with patch.object(ReaderService, "_maximum_lifetime", 1):
            with patch.object(ReaderService, "_timeout_tolerance", 1):
                self.create_reader_service()
                self.assertTrue(self.reader_service.is_alive())

                self.reader_client.set_group(self.groups.find(key="Foo Device 2"))
                self.reader_client.start_recorder()

                time.sleep(1.5)
                # still alive, without start_recorder it should have already exited
                self.assertTrue(self.reader_service.is_alive())

                time.sleep(1)
                # now it stopped, even though the reader is still reading
                self.assertFalse(self.reader_service.is_alive())


if __name__ == "__main__":
    unittest.main()
