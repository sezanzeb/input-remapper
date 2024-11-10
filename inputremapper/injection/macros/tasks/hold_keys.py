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

from evdev.ecodes import EV_KEY

from inputremapper.configs.keyboard_layout import keyboard_layout
from inputremapper.injection.macros.argument import ArgumentConfig, ArgumentFlags
from inputremapper.injection.macros.task import Task


class HoldKeysTask(Task):
    """Hold down multiple keys, equivalent to `a + b + c + ...`."""

    argument_configs = [
        ArgumentConfig(
            name="*symbols",
            position=ArgumentFlags.spread,
            types=[str],
            is_symbol=True,
        )
    ]

    async def run(self, handler) -> None:
        symbols = self.get_argument("*symbols").get_values()

        codes = [keyboard_layout.get(symbol) for symbol in symbols]

        for code in codes:
            handler(EV_KEY, code, 1)
            await self.keycode_pause()

        await self._trigger_release_event.wait()

        for code in codes[::-1]:
            handler(EV_KEY, code, 0)
            await self.keycode_pause()
