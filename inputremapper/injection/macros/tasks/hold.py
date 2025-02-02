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

from evdev.ecodes import EV_KEY

from inputremapper.configs.keyboard_layout import keyboard_layout
from inputremapper.injection.macros.argument import ArgumentConfig
from inputremapper.injection.macros.macro import Macro
from inputremapper.injection.macros.task import Task


class HoldTask(Task):
    """Loop the macro until the trigger-key is released."""

    argument_configs = [
        ArgumentConfig(
            name="macro",
            position=0,
            types=[Macro, str, None],
        )
    ]

    async def run(self, callback) -> None:
        macro = self.get_argument("macro").get_value()

        if macro is None:
            await self._trigger_release_event.wait()
            return

        if isinstance(macro, str):
            # if macro is a key name, hold down the key while the
            # keyboard key is physically held down
            symbol = macro
            self.get_argument("macro").assert_is_symbol(symbol)

            code = keyboard_layout.get(symbol)
            callback(EV_KEY, code, 1)
            await self._trigger_release_event.wait()
            callback(EV_KEY, code, 0)

        if isinstance(macro, Macro):
            # repeat the macro forever while the key is held down
            while self.is_holding():
                # run the child macro completely to avoid
                # not-releasing any key
                await macro.run(callback)
                # give some other code a chance to run
                await asyncio.sleep(1 / 1000)
