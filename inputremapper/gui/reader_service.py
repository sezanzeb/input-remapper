# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2022 sezanzeb <proxima@hip70890b.de>
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

"""Process that sends stuff to the GUI.

It should be started via input-remapper-control and pkexec.

GUIs should not run as root
https://wiki.archlinux.org/index.php/Running_GUI_applications_as_root

The service shouldn't do that even though it has root rights, because that
would enable key-loggers to just ask input-remapper for all user-input.

Instead, the ReaderService is used, which will be stopped when the gui closes.

Whereas for the reader-service to start a password is needed and it stops whe
the ui closes.

This uses the backend injection.event_reader and mapping_handlers to process all the
different input-events into simple on/off events and sends them to the gui.
"""

from __future__ import annotations

import asyncio
import logging
import multiprocessing
import os
import subprocess
import sys
import time
from collections import defaultdict
from typing import Set, List

import evdev
from evdev.ecodes import EV_KEY, EV_ABS, EV_REL, REL_HWHEEL, REL_WHEEL
from inputremapper.utils import get_device_hash

from inputremapper.configs.input_config import InputCombination, InputConfig
from inputremapper.configs.mapping import Mapping
from inputremapper.groups import _Groups, _Group
from inputremapper.injection.event_reader import EventReader
from inputremapper.injection.mapping_handlers.abs_to_btn_handler import AbsToBtnHandler
from inputremapper.injection.mapping_handlers.mapping_handler import (
    NotifyCallback,
    InputEventHandler,
    MappingHandler,
)
from inputremapper.injection.mapping_handlers.rel_to_btn_handler import RelToBtnHandler
from inputremapper.input_event import InputEvent, EventActions
from inputremapper.ipc.pipe import Pipe
from inputremapper.logger import logger
from inputremapper.user import USER

# received by the reader-service
CMD_TERMINATE = "terminate"
CMD_STOP_READING = "stop-reading"
CMD_REFRESH_GROUPS = "refresh_groups"

# sent by the reader-service to the reader
MSG_GROUPS = "groups"
MSG_EVENT = "event"
MSG_STATUS = "status"


def get_pipe_paths():
    """Get the path where the pipe can be found."""
    return (
        f"/tmp/input-remapper-{USER}/reader-results",
        f"/tmp/input-remapper-{USER}/reader-commands",
    )


class ReaderService:
    """Service that only reads events and is supposed to run as root.

    Sends device information and keycodes to the GUI.

    Commands are either numbers for generic commands,
    or strings to start listening on a specific device.
    """

    # the speed threshold at which relative axis are considered moving
    # and will be sent as "pressed" to the frontend.
    # We want to allow some mouse movement before we record it as an input
    rel_xy_speed = defaultdict(lambda: 3)
    # wheel events usually don't produce values higher than 1
    rel_xy_speed[REL_WHEEL] = 1
    rel_xy_speed[REL_HWHEEL] = 1

    # Polkit won't ask for another password if the pid stays the same or something, and
    # if the previous request was no more than 5 minutes ago. see
    # https://unix.stackexchange.com/a/458260.
    # If the user does something after 6 minutes they will get a prompt already if the
    # reader timed out already, which sounds annoying. Instead, I'd rather have the
    # password prompt appear at most every 15 minutes.
    _maximum_lifetime: int = 60 * 15
    _timeout_tolerance: int = 60

    def __init__(self, groups: _Groups):
        """Construct the reader-service and initialize its communication pipes."""
        self._start_time = time.time()
        self.groups = groups
        self._results_pipe = Pipe(get_pipe_paths()[0])
        self._commands_pipe = Pipe(get_pipe_paths()[1])
        self._pipe = multiprocessing.Pipe()

        self._tasks: Set[asyncio.Task] = set()
        self._stop_event = asyncio.Event()

        self._results_pipe.send({"type": MSG_STATUS, "message": "ready"})

    @staticmethod
    def is_running():
        """Check if the reader-service is running."""
        try:
            subprocess.check_output(["pgrep", "-f", "input-remapper-reader-service"])
        except subprocess.CalledProcessError:
            return False
        return True

    @staticmethod
    def pkexec_reader_service():
        """Start reader-service via pkexec to run in the background."""
        debug = " -d" if logger.level <= logging.DEBUG else ""
        cmd = f"pkexec input-remapper-control --command start-reader-service{debug}"

        logger.debug("Running `%s`", cmd)
        exit_code = os.system(cmd)

        if exit_code != 0:
            raise Exception(f"Failed to pkexec the reader-service, code {exit_code}")

    def run(self):
        """Start doing stuff. Blocks."""
        # the reader will check for new commands later, once it is running
        # it keeps running for one device or another.
        loop = asyncio.get_event_loop()
        logger.debug("Discovering initial groups")
        self.groups.refresh()
        self._send_groups()
        loop.run_until_complete(
            asyncio.gather(
                self._read_commands(),
                self._timeout(),
            )
        )

    def _send_groups(self):
        """Send the groups to the gui."""
        logger.debug("Sending groups")
        self._results_pipe.send({"type": MSG_GROUPS, "message": self.groups.dumps()})

    async def _timeout(self):
        """Stop automatically after some time."""
        # Prevents a permanent hole for key-loggers to exist, in case the gui crashes.
        # If the ReaderService stops even though the gui needs it, it needs to restart
        # it. This makes it also more comfortable to have debug mode running during
        # development, because it won't keep writing inputs containing passwords and
        # such to the terminal forever.

        await asyncio.sleep(self._maximum_lifetime)

        # if it is currently reading, wait a bit longer for the gui to complete
        # what it is doing.
        if self._is_reading():
            logger.debug("Waiting a bit longer for the gui to finish reading")

            for _ in range(self._timeout_tolerance):
                if not self._is_reading():
                    # once reading completes, it should terminate right away
                    break

                await asyncio.sleep(1)

        logger.debug("Maximum life-span reached, terminating")
        sys.exit(1)

    async def _read_commands(self):
        """Handle all unread commands.
        this will run until it receives CMD_TERMINATE
        """
        logger.debug("Waiting for commands")
        async for cmd in self._commands_pipe:
            logger.debug('Received command "%s"', cmd)

            if cmd == CMD_TERMINATE:
                await self._stop_reading()
                logger.debug("Terminating")
                sys.exit(0)

            if cmd == CMD_REFRESH_GROUPS:
                self.groups.refresh()
                self._send_groups()
                continue

            if cmd == CMD_STOP_READING:
                await self._stop_reading()
                continue

            group = self.groups.find(key=cmd)
            if group is None:
                # this will block for a bit maybe we want to do this async?
                self.groups.refresh()
                group = self.groups.find(key=cmd)

            if group is not None:
                await self._stop_reading()
                self._start_reading(group)
                continue

            logger.error('Received unknown command "%s"', cmd)

    def _is_reading(self) -> bool:
        """Check if the ReaderService is currently sending events to the GUI."""
        return len(self._tasks) > 0

    def _start_reading(self, group: _Group):
        """Find all devices of that group, filter interesting ones and send the events
        to the gui."""
        sources = []
        for path in group.paths:
            try:
                device = evdev.InputDevice(path)
            except (FileNotFoundError, OSError):
                logger.error('Could not find "%s"', path)
                return None

            capabilities = device.capabilities(absinfo=False)
            if (
                EV_KEY in capabilities
                or EV_ABS in capabilities
                or EV_REL in capabilities
            ):
                sources.append(device)

        context = self._create_event_pipeline(sources)
        # create the event reader and start it
        for device in sources:
            reader = EventReader(context, device, ForwardDummy, self._stop_event)
            self._tasks.add(asyncio.create_task(reader.run()))

    async def _stop_reading(self):
        """Stop the running event_reader."""
        self._stop_event.set()
        if self._tasks:
            await asyncio.gather(*self._tasks)
        self._tasks = set()
        self._stop_event.clear()

    def _create_event_pipeline(self, sources: List[evdev.InputDevice]) -> ContextDummy:
        """Create a custom event pipeline for each event code in the
        device capabilities.
        Instead of sending the events to a uinput they will be sent to the frontend.
        """
        context = ContextDummy()
        # create a context for each source
        for device in sources:
            device_hash = get_device_hash(device)
            capabilities = device.capabilities(absinfo=False)

            for ev_code in capabilities.get(EV_KEY) or ():
                input_config = InputConfig(
                    type=EV_KEY, code=ev_code, origin_hash=device_hash
                )
                context.add_handler(
                    input_config, ForwardToUIHandler(self._results_pipe)
                )

            for ev_code in capabilities.get(EV_ABS) or ():
                # positive direction
                input_config = InputConfig(
                    type=EV_ABS,
                    code=ev_code,
                    analog_threshold=30,
                    origin_hash=device_hash,
                )
                mapping = Mapping(
                    input_combination=InputCombination(input_config),
                    target_uinput="keyboard",
                    output_symbol="KEY_A",
                )
                handler: MappingHandler = AbsToBtnHandler(
                    InputCombination(input_config), mapping
                )
                handler.set_sub_handler(ForwardToUIHandler(self._results_pipe))
                context.add_handler(input_config, handler)

                # negative direction
                input_config = input_config.modify(analog_threshold=-30)
                mapping = Mapping(
                    input_combination=InputCombination(input_config),
                    target_uinput="keyboard",
                    output_symbol="KEY_A",
                )
                handler = AbsToBtnHandler(InputCombination(input_config), mapping)
                handler.set_sub_handler(ForwardToUIHandler(self._results_pipe))
                context.add_handler(input_config, handler)

            for ev_code in capabilities.get(EV_REL) or ():
                # positive direction
                input_config = InputConfig(
                    type=EV_REL,
                    code=ev_code,
                    analog_threshold=self.rel_xy_speed[ev_code],
                    origin_hash=device_hash,
                )
                mapping = Mapping(
                    input_combination=InputCombination(input_config),
                    target_uinput="keyboard",
                    output_symbol="KEY_A",
                    release_timeout=0.3,
                    force_release_timeout=True,
                )
                handler = RelToBtnHandler(InputCombination(input_config), mapping)
                handler.set_sub_handler(ForwardToUIHandler(self._results_pipe))
                context.add_handler(input_config, handler)

                # negative direction
                input_config = input_config.modify(
                    analog_threshold=-self.rel_xy_speed[ev_code]
                )
                mapping = Mapping(
                    input_combination=InputCombination(input_config),
                    target_uinput="keyboard",
                    output_symbol="KEY_A",
                    release_timeout=0.3,
                    force_release_timeout=True,
                )
                handler = RelToBtnHandler(InputCombination(input_config), mapping)
                handler.set_sub_handler(ForwardToUIHandler(self._results_pipe))
                context.add_handler(input_config, handler)

        return context


class ContextDummy:
    def __init__(self):
        self.listeners = set()
        self._notify_callbacks = defaultdict(list)

    def add_handler(self, input_config: InputConfig, handler: InputEventHandler):
        self._notify_callbacks[input_config.input_match_hash].append(handler.notify)

    def get_entry_points(self, input_event: InputEvent) -> List[NotifyCallback]:
        return self._notify_callbacks[input_event.input_match_hash]

    def reset(self):
        pass


class ForwardDummy:
    @staticmethod
    def write(*_):
        pass


class ForwardToUIHandler:
    """Implements the InputEventHandler protocol. Sends all events into the pipe."""

    def __init__(self, pipe: Pipe):
        self.pipe = pipe
        self._last_event = InputEvent.from_tuple((99, 99, 99))

    def notify(
        self,
        event: InputEvent,
        source: evdev.InputDevice,
        forward: evdev.UInput,
        suppress: bool = False,
    ) -> bool:
        """Filter duplicates and send into the pipe."""
        if event != self._last_event:
            self._last_event = event
            if EventActions.negative_trigger in event.actions:
                event = event.modify(value=-1)

            logger.debug_key(event.event_tuple, "to frontend:")
            self.pipe.send(
                {
                    "type": MSG_EVENT,
                    "message": {
                        "sec": event.sec,
                        "usec": event.usec,
                        "type": event.type,
                        "code": event.code,
                        "value": event.value,
                        "origin_hash": event.origin_hash,
                    },
                }
            )
        return True

    def reset(self):
        pass
