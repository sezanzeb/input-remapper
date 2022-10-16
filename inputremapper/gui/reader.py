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


"""Talking to the GUI helper that has root permissions.

see gui.helper.helper
"""
from typing import Optional, List, Generator, Dict, Tuple, Set

import evdev
from gi.repository import GLib

from inputremapper.event_combination import EventCombination
from inputremapper.groups import _Groups, _Group
from inputremapper.gui.helper import (
    MSG_EVENT,
    MSG_GROUPS,
    CMD_TERMINATE,
    CMD_REFRESH_GROUPS,
)
from inputremapper.gui.messages.message_types import MessageType
from inputremapper.gui.messages.message_broker import MessageBroker
from inputremapper.gui.messages.message_data import GroupsData, CombinationRecorded
from inputremapper.input_event import InputEvent
from inputremapper.ipc.pipe import Pipe
from inputremapper.logger import logger
from inputremapper.user import USER

BLACKLISTED_EVENTS = [(1, evdev.ecodes.BTN_TOOL_DOUBLETAP)]
RecordingGenerator = Generator[None, InputEvent, None]


class Reader:
    """Processes events from the helper for the GUI to use.

    Does not serve any purpose for the injection service.

    When a button was pressed, the newest keycode can be obtained from this
    object. GTK has get_key for keyboard keys, but Reader also
    has knowledge of buttons like the middle-mouse button.
    """

    def __init__(self, message_broker: MessageBroker, groups: _Groups):
        self.groups = groups
        self.message_broker = message_broker

        self.group: Optional[_Group] = None
        self.read_timeout: Optional[int] = None

        self._recording_generator: Optional[RecordingGenerator] = None
        self._results = None
        self._commands = None

        self.connect()
        self.attach_to_events()
        self._read_continuously()

    def connect(self):
        """Connect to the helper."""
        self._results = Pipe(f"/tmp/input-remapper-{USER}/results")
        self._commands = Pipe(f"/tmp/input-remapper-{USER}/commands")

    def attach_to_events(self):
        """Connect listeners to event_reader."""
        self.message_broker.subscribe(MessageType.terminate, lambda _: self.terminate())

    def _read_continuously(self):
        """Poll the result pipe in regular intervals."""
        self.read_timeout = GLib.timeout_add(30, self._read)

    def _read(self):
        """Read the messages from the helper and handle them."""
        while self._results.poll():
            message = self._results.recv()

            logger.debug("Reader received %s", message)

            message_type = message["type"]
            message_body = message["message"]
            if message_type == MSG_GROUPS:
                self._update_groups(message_body)
                continue

            if message_type == MSG_EVENT:
                if not self._recording_generator:
                    continue

                # update the generator
                try:
                    self._recording_generator.send(InputEvent(*message_body))
                except StopIteration:
                    self.message_broker.signal(MessageType.recording_finished)
                    self._recording_generator = None

        return True

    def start_recorder(self) -> None:
        """Record user input."""
        self._recording_generator = self._recorder()
        next(self._recording_generator)

    def stop_recorder(self) -> None:
        """Stop recording the input.

        Will send RecordingFinished message.
        """
        if self._recording_generator:
            self._recording_generator.close()
            self._recording_generator = None
            self.message_broker.signal(MessageType.recording_finished)

    def _recorder(self) -> RecordingGenerator:
        """Generator which receives InputEvents.

        it accumulates them into EventCombinations and sends those on the message_broker.
        it will stop once all keys or inputs are released.
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
                self.message_broker.send(
                    CombinationRecorded(EventCombination(accumulator))
                )

            if event not in accumulator:
                accumulator.append(event)
                self.message_broker.send(
                    CombinationRecorded(EventCombination(accumulator))
                )

    def set_group(self, group):
        """Start reading keycodes for a device."""
        logger.debug('Sending start msg to helper for "%s"', group.key)
        if self._recording_generator:
            self._recording_generator.close()
            self._recording_generator = None
        self._commands.send(group.key)
        self.group = group

    def terminate(self):
        """Stop reading keycodes for good."""
        logger.debug("Sending close msg to helper")
        self._commands.send(CMD_TERMINATE)
        if self.read_timeout:
            GLib.source_remove(self.read_timeout)
        while self._results.poll():
            self._results.recv()

    def refresh_groups(self):
        """Ask the helper for new device groups."""
        self._commands.send(CMD_REFRESH_GROUPS)

    def send_groups(self):
        """announce all known groups"""
        groups: Dict[str, List[str]] = {
            group.key: group.types or []
            for group in self.groups.filter(include_inputremapper=False)
        }
        self.message_broker.send(GroupsData(groups))

    def _update_groups(self, dump):
        if dump != self.groups.dumps():
            self.groups.loads(dump)
            logger.debug("Received %d devices", len(self.groups))
            self._groups_updated = True

        # send this even if the groups did not change, as the user expects the ui
        # to respond in some form
        self.send_groups()
