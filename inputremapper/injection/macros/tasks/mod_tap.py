#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2024 sezanzeb <b8x45ygc9@mozmail.com>
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

from __future__ import annotations

import asyncio
from collections import deque
from typing import Deque

from evdev.ecodes import EV_KEY

from inputremapper.configs.keyboard_layout import keyboard_layout
from inputremapper.injection.macros.argument import ArgumentConfig
from inputremapper.injection.macros.task import Task
from inputremapper.input_event import InputEvent
from inputremapper.logging.logger import logger


class ModTapTask(Task):
    """If pressed long enough in combination with other keys, it turns into a modifier.

    Can be used to make home-row-modifiers.

    Works similar to the default of
    https://github.com/qmk/qmk_firmware/blob/78a0adfbb4d2c4e12f93f2a62ded0020d406243e/docs/tap_hold.md#comparison-comparison
    """

    argument_configs = [
        ArgumentConfig(
            name="default",
            position=0,
            types=[str],
            is_symbol=True,
        ),
        ArgumentConfig(
            name="modifier",
            position=1,
            types=[str],
            is_symbol=True,
        ),
        ArgumentConfig(
            name="tapping_term",
            position=2,
            types=[int, float],
            default=200,
        ),
    ]

    async def run(self, callback) -> None:
        tapping_term = self.get_argument("tapping_term").get_value() / 1000
        jamming_asyncio_events: Deque[asyncio.Event] = deque()

        async def listener(event: InputEvent) -> None:
            trigger = self.mapping.input_combination[-1]
            if event.type_and_code == trigger.type_and_code:
                # We don't block the event that would set _trigger_release_event.
                return

            if event.type != EV_KEY:
                return

            asyncio_event = asyncio.Event()
            jamming_asyncio_events.append(asyncio_event)
            # Make the EventReader wait until the mod_tap macro allows it to continue
            # processing the event. Because we want to wait until mod_tap injected the
            # modifier.
            await asyncio_event.wait()

        self.add_event_listener(listener)

        timeout = asyncio.Task(asyncio.sleep(tapping_term))
        await asyncio.wait(
            [asyncio.Task(self._trigger_release_event.wait()), timeout],
            return_when=asyncio.FIRST_COMPLETED,
        )
        has_timed_out = timeout.done()

        if has_timed_out:
            # The timeout happened before the trigger got released.
            # We therefore modify stuff.
            symbol = self.get_argument("modifier").get_value()
            logger.debug("Modifying with %s", symbol)
        else:
            # The trigger got released before the timeout.
            # We therefore do not modify stuff.
            symbol = self.get_argument("default").get_value()
            logger.debug("Writing default %s", symbol)

        code = keyboard_layout.get(symbol)
        callback(EV_KEY, code, 1)
        await self.keycode_pause()

        # Now that we know if the key was pressed with the intention of modifying other
        # keys, we can let the jammed keys go on their journey through the handlers.
        # Those other handlers may map them to other keys and stuff.
        while len(jamming_asyncio_events) > 0:
            asyncio_event = jamming_asyncio_events.popleft()
            asyncio_event.set()
            await self.keycode_pause()
            await self.throttle()
            # While we are emptying the queue, more events might still arrive and add
            # to the queue.

        # We remove this as late as possible, because if more keys are pressed while
        # jamming_asyncio_events is still being taken care of, they should wait until
        # all is done. This ensures the order of all events that are pressed, until
        # mod_tap is completely finished.
        self.remove_event_listener(listener)

        # Keep the modifier pressed until the input/trigger is released
        await self._trigger_release_event.wait()
        callback(EV_KEY, code, 0)

        await self.keycode_pause()

    async def throttle(self) -> None:
        # In case the keycode_pause ist set to 0ms, we need to give the event handlers
        # a chance to inject the withheld events, before we go on. This ensures the
        # correct order of injections. Since we are using asyncio, something like
        # `callback(EV_KEY, code, 0)` might be faster than the event handlers, even if
        # it is the last step of the macro.
        if self.mapping.macro_key_sleep_ms == 0:
            await asyncio.sleep(0.01)
