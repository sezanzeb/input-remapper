#!/usr/bin/python3
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
would provide a key-logger that can be accessed by any user at all times,
whereas for the helper to start a password is needed and it stops when the ui
closes.

This uses the backend injection.event_reader and mapping_handlers to process all the
different input-events into simple on/off events and sends them to the gui.
"""
from __future__ import annotations

import asyncio
import multiprocessing
import subprocess
import sys
from collections import defaultdict
from typing import Set, List

import evdev
from evdev.ecodes import EV_KEY, EV_ABS, EV_REL, REL_HWHEEL, REL_WHEEL

from inputremapper.configs.mapping import UIMapping
from inputremapper.event_combination import EventCombination
from inputremapper.groups import _Groups, _Group
from inputremapper.injection.event_reader import EventReader
from inputremapper.injection.mapping_handlers.abs_to_btn_handler import AbsToBtnHandler
from inputremapper.injection.mapping_handlers.mapping_handler import MappingHandler
from inputremapper.injection.mapping_handlers.rel_to_btn_handler import RelToBtnHandler
from inputremapper.input_event import InputEvent, EventActions
from inputremapper.ipc.pipe import Pipe
from inputremapper.logger import logger
from inputremapper.user import USER

# received by the helper
CMD_TERMINATE = "terminate"
CMD_REFRESH_GROUPS = "refresh_groups"

# sent by the helper to the reader
MSG_GROUPS = "groups"
MSG_EVENT = "event"


def is_helper_running():
    """Check if the helper is running."""
    try:
        subprocess.check_output(["pgrep", "-f", "input-remapper-helper"])
    except subprocess.CalledProcessError:
        return False
    return True


class RootHelper:
    """Client that runs as root and works for the GUI.

    Sends device information and keycodes to the GUIs socket.

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

    def __init__(self, groups: _Groups):
        """Construct the helper and initialize its sockets."""
        self.groups = groups
        self._results = Pipe(f"/tmp/input-remapper-{USER}/results")
        self._commands = Pipe(f"/tmp/input-remapper-{USER}/commands")
        self._pipe = multiprocessing.Pipe()

        self._tasks: Set[asyncio.Task] = set()
        self._stop_event = asyncio.Event()

    def run(self):
        """Start doing stuff. Blocks."""
        # the reader will check for new commands later, once it is running
        # it keeps running for one device or another.
        loop = asyncio.get_event_loop()
        logger.debug("Discovering initial groups")
        self.groups.refresh()
        self._send_groups()
        logger.debug("Waiting commands")
        loop.run_until_complete(self._read_commands())
        logger.debug("Helper terminates")
        sys.exit(0)

    def _send_groups(self):
        """Send the groups to the gui."""
        logger.debug("Sending groups")
        self._results.send({"type": MSG_GROUPS, "message": self.groups.dumps()})

    async def _read_commands(self):
        """Handle all unread commands.
        this will run until it receives CMD_TERMINATE
        """
        async for cmd in self._commands:
            logger.debug('Received command "%s"', cmd)

            if cmd == CMD_TERMINATE:
                await self._stop_reading()
                return

            if cmd == CMD_REFRESH_GROUPS:
                self.groups.refresh()
                self._send_groups()
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

    def _start_reading(self, group: _Group):
        """find all devices of that group, filter interesting ones and send the events
        to the gui"""
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
        """stop the running event_reader"""
        self._stop_event.set()
        if self._tasks:
            await asyncio.gather(*self._tasks)
        self._tasks = set()
        self._stop_event.clear()

    def _create_event_pipeline(self, sources: List[evdev.InputDevice]) -> ContextDummy:
        """create a custom event pipeline for each event code in the
        device capabilities.
        Instead of sending the events to a uinput they will be sent to the frontend"""
        context = ContextDummy()
        # create a context for each source
        for device in sources:
            capabilities = device.capabilities(absinfo=False)

            for ev_code in capabilities.get(EV_KEY) or ():
                context.notify_callbacks[(EV_KEY, ev_code)].append(
                    ForwardToUIHandler(self._results).notify
                )

            for ev_code in capabilities.get(EV_ABS) or ():
                # positive direction
                mapping = UIMapping(
                    event_combination=EventCombination((EV_ABS, ev_code, 30)),
                    target_uinput="keyboard",
                )
                handler: MappingHandler = AbsToBtnHandler(
                    EventCombination((EV_ABS, ev_code, 30)), mapping
                )
                handler.set_sub_handler(ForwardToUIHandler(self._results))
                context.notify_callbacks[(EV_ABS, ev_code)].append(handler.notify)

                # negative direction
                mapping = UIMapping(
                    event_combination=EventCombination((EV_ABS, ev_code, -30)),
                    target_uinput="keyboard",
                )
                handler = AbsToBtnHandler(
                    EventCombination((EV_ABS, ev_code, -30)), mapping
                )
                handler.set_sub_handler(ForwardToUIHandler(self._results))
                context.notify_callbacks[(EV_ABS, ev_code)].append(handler.notify)

            for ev_code in capabilities.get(EV_REL) or ():
                # positive direction
                mapping = UIMapping(
                    event_combination=EventCombination(
                        (EV_REL, ev_code, self.rel_xy_speed[ev_code])
                    ),
                    target_uinput="keyboard",
                    release_timeout=0.3,
                    force_release_timeout=True,
                )
                handler = RelToBtnHandler(
                    EventCombination((EV_REL, ev_code, self.rel_xy_speed[ev_code])),
                    mapping,
                )
                handler.set_sub_handler(ForwardToUIHandler(self._results))
                context.notify_callbacks[(EV_REL, ev_code)].append(handler.notify)

                # negative direction
                mapping = UIMapping(
                    event_combination=EventCombination(
                        (EV_REL, ev_code, -self.rel_xy_speed[ev_code])
                    ),
                    target_uinput="keyboard",
                    release_timeout=0.3,
                    force_release_timeout=True,
                )
                handler = RelToBtnHandler(
                    EventCombination((EV_REL, ev_code, -self.rel_xy_speed[ev_code])),
                    mapping,
                )
                handler.set_sub_handler(ForwardToUIHandler(self._results))
                context.notify_callbacks[(EV_REL, ev_code)].append(handler.notify)

        return context


class ContextDummy:
    def __init__(self):
        self.listeners = set()
        self.notify_callbacks = defaultdict(list)

    def reset(self):
        pass


class ForwardDummy:
    @staticmethod
    def write(*_):
        pass


class ForwardToUIHandler:
    """implements the InputEventHandler protocol. Sends all events into the pipe"""

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
        """filter duplicates and send into the pipe"""
        if event != self._last_event:
            self._last_event = event
            if EventActions.negative_trigger in event.actions:
                event = event.modify(value=-1)

            logger.debug_key(event, f"to frontend:")
            self.pipe.send(
                {
                    "type": MSG_EVENT,
                    "message": (
                        event.sec,
                        event.usec,
                        event.type,
                        event.code,
                        event.value,
                    ),
                }
            )
        return True

    def reset(self):
        pass
