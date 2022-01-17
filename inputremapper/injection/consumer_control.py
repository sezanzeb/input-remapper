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

from inputremapper.injection.consumers.joystick_to_mouse import JoystickToMouse
from inputremapper.injection.consumers.keycode_mapper import KeycodeMapper
from inputremapper.logger import logger
from inputremapper.injection.context import Context

consumer_classes = [
    KeycodeMapper,
    JoystickToMouse,
]

def copy_event(event: evdev.InputEvent) -> evdev.InputEvent:
    return evdev.InputEvent(
        sec=event.sec,
        usec=event.usec,
        type=event.type,
        code=event.code,
        value=event.value,
    )


class ConsumerControl:
    """Reads input events from a single device and distributes them.

    There is one ConsumerControl object for each source, which tells multiple consumers
    that a new event is ready so that they can inject all sorts of funny
    things.

    Other devnodes may be present for the hardware device, in which case this
    needs to be created multiple times.
    """

    def __init__(self,
                 context: Context,
                 source: evdev.InputDevice,
                 forward_to: evdev.UInput,
                 ) -> None:
        """Initialize all consumers

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

        # add all consumers that are enabled for this particular configuration
        self._consumers = []
        for Consumer in consumer_classes:
            consumer = Consumer(context, source, forward_to)
            if consumer.is_enabled():
                self._consumers.append(consumer)

    async def run(self):
        """Start doing things.

        Can be stopped by stopping the asyncio loop. This loop
        reads events from a single device only.
        """
        for consumer in self._consumers:
            # run all of them in parallel
            asyncio.ensure_future(consumer.run())

        logger.debug(
            "Starting to listen for events from %s, fd %s",
            self._source.path,
            self._source.fd,
        )

        async for event in self._source.async_read_loop():
            if event.type == evdev.ecodes.EV_KEY and event.value == 2:
                # button-hold event. Environments (gnome, etc.) create them on
                # their own for the injection-fake-device if the release event
                # won't appear, no need to forward or map them.
                continue

            tasks = []
            if (event.type, event.code) in self.context.callbacks.keys():
                for callback in self.context.callbacks[(event.type, event.code)]:
                    tasks.append(callback(copy_event(event)))
                results = await asyncio.gather(*tasks)
                if True in results:
                    continue

            # try legacy injection if the new injection did not do anything
            # TODO: Remove. only keep the call to forward
            handled = False
            for consumer in self._consumers:
                # copy so that the consumer doesn't screw this up for
                # all other future consumers
                event_copy = copy_event(event)
                if consumer.is_handled(event_copy):
                    await consumer.notify(event_copy)
                    handled = True

            if not handled:
                # forward the rest
                self._forward_to.write(event.type, event.code, event.value)
                # this already includes SYN events, so need to syn here again

        # This happens all the time in tests because the async_read_loop stops when
        # there is nothing to read anymore. Otherwise tests would block.
        logger.error('The async_read_loop for "%s" stopped early', self._source.path)
