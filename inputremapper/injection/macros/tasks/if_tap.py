#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2025 sezanzeb <b8x45ygc9@mozmail.com>
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

from inputremapper.injection.macros.argument import ArgumentConfig
from inputremapper.injection.macros.macro import Macro
from inputremapper.injection.macros.task import Task


class IfTapTask(Task):
    """If a key was pressed quickly.

    macro key pressed -> if_tap starts -> key released -> then

    macro key pressed -> released (does other stuff in the meantime)
    -> if_tap starts -> pressed -> released -> then
    """

    argument_configs = [
        ArgumentConfig(
            name="then",
            position=0,
            types=[Macro, None],
            default=None,
        ),
        ArgumentConfig(
            name="else",
            position=1,
            types=[Macro, None],
            default=None,
        ),
        ArgumentConfig(
            name="timeout",
            position=2,
            types=[int, float],
            default=300,
        ),
    ]

    async def run(self, callback) -> None:
        then = self.get_argument("then").get_value()
        else_ = self.get_argument("else").get_value()
        timeout = self.get_argument("timeout").get_value() / 1000

        try:
            await asyncio.wait_for(self._wait(), timeout)
            if then:
                await then.run(callback)
        except asyncio.TimeoutError:
            if else_:
                await else_.run(callback)

    async def _wait(self):
        """Wait for a release, or if nothing pressed yet, a press and release."""
        if self.is_holding():
            await self._trigger_release_event.wait()
        else:
            await self._trigger_press_event.wait()
            await self._trigger_release_event.wait()
