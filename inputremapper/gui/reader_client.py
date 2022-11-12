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


"""Talking to the ReaderService that has root permissions.

see gui.reader_service.ReaderService
"""

from typing import Optional, List, Generator, Dict, Tuple, Set
import time

import evdev

import gi

gi.require_version("GLib", "2.0")
from gi.repository import GLib

from inputremapper.event_combination import EventCombination
from inputremapper.groups import _Groups, _Group
from inputremapper.gui.reader_service import (
    MSG_EVENT,
    MSG_GROUPS,
    CMD_TERMINATE,
    CMD_REFRESH_GROUPS,
    CMD_STOP_READING,
    get_pipe_paths,
    ReaderService,
)
from inputremapper.gui.messages.message_types import MessageType
from inputremapper.gui.messages.message_broker import MessageBroker
from inputremapper.gui.messages.message_data import (
    GroupsData,
    CombinationRecorded,
    StatusData,
)
from inputremapper.gui.utils import CTX_ERROR
from inputremapper.gui.gettext import _
from inputremapper.input_event import InputEvent
from inputremapper.ipc.pipe import Pipe
from inputremapper.logger import logger

BLACKLISTED_EVENTS = [(1, evdev.ecodes.BTN_TOOL_DOUBLETAP)]
RecordingGenerator = Generator[None, InputEvent, None]


class ReaderClient:
    """Processes events from the reader-service for the GUI to use.

    Does not serve any purpose for the injection service.

    When a button was pressed, the newest keycode can be obtained from this object.
    GTK has get_key for keyboard keys, but Reader also has knowledge of buttons like
    the middle-mouse button.
    """

    # how long to wait for the reader-service at most
    _timeout: int = 5

    def __init__(self, message_broker: MessageBroker, groups: _Groups):
        self.groups = groups
        self.message_broker = message_broker

        self.group: Optional[_Group] = None

        self._recording_generator: Optional[RecordingGenerator] = None
        self._results_pipe = None
        self._commands_pipe = None

        self.connect()
        self.attach_to_events()

        self._read_timeout = GLib.timeout_add(30, self._read)

    def ensure_reader_service_running(self):
        if ReaderService.is_running():
            return

        logger.info("ReaderService not running anymore, restarting")
        ReaderService.pkexec_reader_service()

        # wait until the ReaderService is up

        # wait no more than:
        polling_period = 0.01
        # this will make the gui non-responsive for 0.4s or something. The pkexec
        # password prompt will appear, so the user understands that the lag has to
        # be connected to the authentication. I would actually prefer the frozen gui
        # over a reactive one here, because the short lag shows that stuff is going on
        # behind the scenes.
        for __ in range(int(self._timeout / polling_period)):
            if self._results_pipe.poll():
                logger.info("ReaderService started")
                break

            time.sleep(polling_period)
        else:
            msg = "The reader-service did not start"
            logger.error(msg)
            self.message_broker.publish(StatusData(CTX_ERROR, _(msg)))

    def _send_command(self, command: str):
        """Send a command to the ReaderService."""
        if command not in [CMD_TERMINATE, CMD_STOP_READING]:
            self.ensure_reader_service_running()

        logger.debug('Sending "%s" to ReaderService', command)
        self._commands_pipe.send(command)

    def connect(self):
        """Connect to the reader-service."""
        self._results_pipe = Pipe(get_pipe_paths()[0])
        self._commands_pipe = Pipe(get_pipe_paths()[1])

    def attach_to_events(self):
        """Connect listeners to event_reader."""
        self.message_broker.subscribe(
            MessageType.terminate,
            lambda _: self.terminate(),
        )

    def _read(self):
        """Read the messages from the reader-service and handle them."""
        while self._results_pipe.poll():
            message = self._results_pipe.recv()

            logger.debug("received %s", message)

            message_type = message["type"]
            message_body = message["message"]

            if message_type == MSG_GROUPS:
                self._update_groups(message_body)

            if message_type == MSG_EVENT:
                # update the generator
                try:
                    if self._recording_generator is not None:
                        self._recording_generator.send(InputEvent(*message_body))
                    else:
                        # the ReaderService should only send events while the gui
                        # is recording, so this is unexpected.
                        logger.error("Got event, but recorder is not running.")
                except StopIteration:
                    # the _recording_generator returned
                    logger.debug("Recorder finished.")
                    self.stop_recorder()
                    break

        return True

    def start_recorder(self) -> None:
        """Record user input."""
        if self.group is None:
            logger.error("No group set")
            return

        logger.debug("Starting recorder.")
        self._send_command(self.group.key)

        self._recording_generator = self._recorder()
        next(self._recording_generator)

        self.message_broker.signal(MessageType.recording_started)  # TODO test

    def stop_recorder(self) -> None:
        """Stop recording the input.

        Will send RecordingFinished message.
        """
        logger.debug("Stopping recorder.")
        self._send_command(CMD_STOP_READING)

        if self._recording_generator:
            self._recording_generator.close()
            self._recording_generator = None
        else:
            # this would be unexpected. but this is not critical enough to
            # show to the user without debug logs
            logger.debug("No recording generator existed")

        self.message_broker.signal(MessageType.recording_finished)

    def _recorder(self) -> RecordingGenerator:
        """Generator which receives InputEvents.

        It accumulates them into EventCombinations and sends those on the
        message_broker. It will stop once all keys or inputs are released.
        """
        active: Set[Tuple[int, int]] = set()
        accumulator: List[InputEvent] = []
        while True:
            event: InputEvent = yield
            if event.type_and_code in BLACKLISTED_EVENTS:
                continue

            if event.value == 0:
                try:
                    active.remove((event.type, event.code))
                except KeyError:
                    # we haven't seen this before probably a key got released which
                    # was pressed before we started recording. ignore it.
                    continue

                if not active:
                    # all previously recorded events are released
                    return
                continue

            active.add(event.type_and_code)
            accu_type_code = [e.type_and_code for e in accumulator]
            if event.type_and_code in accu_type_code and event not in accumulator:
                # the value has changed but the event is already in the accumulator
                # update the event
                i = accu_type_code.index(event.type_and_code)
                accumulator[i] = event
                self.message_broker.publish(
                    CombinationRecorded(EventCombination(accumulator))
                )

            if event not in accumulator:
                accumulator.append(event)
                self.message_broker.publish(
                    CombinationRecorded(EventCombination(accumulator))
                )

    def set_group(self, group: _Group):
        """Set the group for which input events should be read later."""
        # TODO load the active_group from the controller instead?
        self.group = group

    def terminate(self):
        """Stop reading keycodes for good."""
        self._send_command(CMD_TERMINATE)

        self.stop_recorder()

        if self._read_timeout is not None:
            GLib.source_remove(self._read_timeout)
            self._read_timeout = None

        while self._results_pipe.poll():
            self._results_pipe.recv()

    def refresh_groups(self):
        """Ask the ReaderService for new device groups."""
        self._send_command(CMD_REFRESH_GROUPS)

    def publish_groups(self):
        """Announce all known groups."""
        groups: Dict[str, List[str]] = {
            group.key: group.types or []
            for group in self.groups.filter(include_inputremapper=False)
        }
        self.message_broker.publish(GroupsData(groups))

    def _update_groups(self, dump: str):
        if dump != self.groups.dumps():
            self.groups.loads(dump)
            logger.debug("Received %d devices", len(self.groups))
            self._groups_updated = True

        # send this even if the groups did not change, as the user expects the ui
        # to respond in some form
        self.publish_groups()
