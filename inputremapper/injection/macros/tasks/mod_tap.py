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
from typing import List

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

        recorded_input_events: List[InputEvent] = []

        async def listener(event: InputEvent) -> bool:
            if event.type_and_code == self.mapping.input_combination[-1].type_and_code:
                # This event triggered the macro, we don't hide it. We need this to
                # fire `_trigger_release_event`.
                return False

            if event.type != EV_KEY:
                # False = allow forwarding right away
                return False

            nonlocal recorded_input_events
            # Remember all incoming key events while the trigger is being held
            recorded_input_events.append(event)
            # and stop them from being injected/forwarded.
            return True

        self.add_event_listener(listener)

        timeout = asyncio.Task(asyncio.sleep(tapping_term))
        await asyncio.wait(
            [asyncio.Task(self._trigger_release_event.wait()), timeout],
            return_when=asyncio.FIRST_COMPLETED,
        )
        has_timed_out = timeout.done()

        self.remove_event_listener(listener)

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
        # keys, we can replay all recorded keys.
        for event in recorded_input_events:
            logger.debug("Replaying event %s", event)
            # There is no guarantee that the target uinput of a given mapping has the
            # necessary capability, so we use the forward_uinput instead of the
            # callback.
            assert event.origin_hash is not None
            self.context.get_forward_uinput(event.origin_hash).write_event(event)
            await self.keycode_pause()

        await self._trigger_release_event.wait()
        callback(EV_KEY, code, 0)
        await self.keycode_pause()

        # TODO test that
        #  control-l-down a-down control-l-up a-up results in a regular ctrl+a
        #  combination, if done quickly enough, by replaying the control-l-up as well.
        #  And I wonder if the control-l-down and control-l-up also are required to
        #  be in the same uinput. make sure the test also tests that both control
        #  events are ending up in the correct forwarded uinput.
