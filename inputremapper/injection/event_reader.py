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


"""Because multiple calls to async_read_loop won't work."""
import asyncio
import evdev
from inputremapper.logger import logger
from inputremapper.input_event import InputEvent, EventActions
from inputremapper.injection.context import Context


class _ReadLoop:
    def __init__(self, device: evdev.InputDevice, stop_event: asyncio.Event):
        self.iterator = device.async_read_loop().__aiter__()
        self.stop_event = stop_event
        self.wait_for_stop = asyncio.Task(stop_event.wait())

    def __aiter__(self):
        return self

    def __anext__(self):
        if self.stop_event.is_set():
            raise StopAsyncIteration

        return self.future()

    async def future(self):
        ev_task = asyncio.Task(self.iterator.__anext__())
        stop_task = self.wait_for_stop
        done, pending = await asyncio.wait(
            {ev_task, stop_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if stop_task in done:
            raise StopAsyncIteration

        return done.pop().result()


class EventReader:
    """Reads input events from a single device and distributes them.

    There is one EventReader object for each source, which tells multiple mapping_handlers
    that a new event is ready so that they can inject all sorts of funny
    things.

    Other devnodes may be present for the hardware device, in which case this
    needs to be created multiple times.
    """

    def __init__(
        self,
        context: Context,
        source: evdev.InputDevice,
        forward_to: evdev.UInput,
        stop_event: asyncio.Event,
    ) -> None:
        """Initialize all mapping_handlers

        Parameters
        ----------
        source : evdev.InputDevice
            where to read keycodes from
        forward_to : evdev.UInput
            where to write keycodes to that were not mapped to anything.
            Should be an UInput with capabilities that work for all forwarded
            events, so ideally they should be copied from source.
        """
        self._source = source
        self._forward_to = forward_to
        self.context = context
        self.stop_event = stop_event

    def send_to_handlers(self, event: InputEvent) -> bool:
        """Send the event to callback."""
        if event.type == evdev.ecodes.EV_MSC:
            return False

        if event.type == evdev.ecodes.EV_SYN:
            return False

        results = set()
        for callback in self.context.callbacks.get(event.type_and_code) or ():
            results.add(callback(event, source=self._source, forward=self._forward_to))

        return True in results

    async def send_to_listeners(self, event: InputEvent) -> None:
        """Send the event to listeners."""
        if event.type == evdev.ecodes.EV_MSC:
            return

        if event.type == evdev.ecodes.EV_SYN:
            return

        for listener in self.context.listeners.copy():
            # use a copy, since the listeners might remove themselves form the set

            # fire and forget, run them in parallel and don't wait for them, since
            # a listener might be blocking forever while waiting for more events.
            asyncio.ensure_future(listener(event))

            # Running macros have priority, give them a head-start for processing the
            # event.  If if_single injects a modifier, this modifier should be active
            # before the next handler injects an "a" or something, so that it is
            # possible to capitalize it via if_single.
            # 1. Event from keyboard arrives (e.g. an "a")
            # 2. the listener for if_single is called
            # 3. if_single decides runs then (e.g. injects shift_L)
            # 4. The original event is forwarded (or whatever it is supposed to do)
            # 5. Capitalized "A" is injected.
            # So make sure to call the listeners before notifying the handlers.
            await asyncio.sleep(0)

    def forward(self, event: InputEvent) -> None:
        """Forward an event, which injects it unmodified."""
        if event.type == evdev.ecodes.EV_KEY:
            logger.debug_key(event.event_tuple, "forwarding")

        self._forward_to.write(*event.event_tuple)

    async def handle(self, event: InputEvent) -> None:
        if event.type == evdev.ecodes.EV_KEY and event.value == 2:
            # button-hold event. Environments (gnome, etc.) create them on
            # their own for the injection-fake-device if the release event
            # won't appear, no need to forward or map them.
            return

        await self.send_to_listeners(event)

        if not self.send_to_handlers(event):
            # no handler took care of it, forward it
            self.forward(event)

    async def run(self):
        """Start doing things.

        Can be stopped by stopping the asyncio loop. This loop
        reads events from a single device only.
        """
        logger.debug(
            "Starting to listen for events from %s, fd %s",
            self._source.path,
            self._source.fd,
        )

        async for event in _ReadLoop(self._source, self.stop_event):
            await self.handle(InputEvent.from_event(event))

        self.context.reset()
        logger.info('read loop for %s stopped', self._source.path)
