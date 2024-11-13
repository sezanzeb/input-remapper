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

from evdev.ecodes import EV_KEY

from inputremapper.injection.macros.argument import ArgumentConfig
from inputremapper.injection.macros.macro import Macro
from inputremapper.injection.macros.task import Task


class IfSingleTask(Task):
    """If a key was pressed without combining it."""

    argument_configs = [
        ArgumentConfig(
            name="then",
            position=0,
            types=[Macro, None],
        ),
        ArgumentConfig(
            name="else",
            position=1,
            types=[Macro, None],
        ),
        ArgumentConfig(
            name="timeout",
            position=2,
            types=[int, float, None],
            default=None,
        ),
    ]

    async def run(self, callback) -> None:
        another_key_pressed_event = asyncio.Event()
        then = self.get_argument("then").get_value()
        else_ = self.get_argument("else").get_value()

        async def listener(event) -> bool:
            if event.type != EV_KEY:
                # Ignore anything that is not a key
                return False

            if event.value == 1:
                # Another key was pressed
                another_key_pressed_event.set()
                return False

        self.add_event_listener(listener)

        timeout = self.get_argument("timeout").get_value()

        # Wait for anything of importance to happen, that would determine the
        # outcome of the if_single macro.
        await asyncio.wait(
            [
                asyncio.Task(another_key_pressed_event.wait()),
                asyncio.Task(self._trigger_release_event.wait()),
            ],
            timeout=timeout / 1000 if timeout else None,
            return_when=asyncio.FIRST_COMPLETED,
        )

        self.remove_event_listener(listener)

        if not self.is_holding():
            if then:
                await then.run(callback)
        else:
            # If the trigger has not been released, then `await asyncio.wait` above
            # could only have finished waiting due to a timeout, or because another
            # key was pressed.
            if else_:
                await else_.run(callback)
