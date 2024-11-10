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

from evdev.ecodes import ecodes

from inputremapper.injection.macros.argument import ArgumentConfig
from inputremapper.injection.macros.task import Task


class EventTask(Task):
    """Write any event.

    For example event(EV_KEY, KEY_A, 1)
    """

    argument_configs = [
        ArgumentConfig(
            name="type",
            position=0,
            types=[str, int],
        ),
        ArgumentConfig(
            name="code",
            position=1,
            types=[str, int],
        ),
        ArgumentConfig(
            name="value",
            position=2,
            types=[int],
        ),
    ]

    async def run(self, handler) -> None:
        type_ = self.get_argument("type").get_value()
        code = self.get_argument("code").get_value()
        value = self.get_argument("value").get_value()

        if isinstance(type_, str):
            type_ = ecodes[type_.upper()]
        if isinstance(code, str):
            self.get_argument("code").assert_is_symbol(code)
            code = ecodes[code.upper()]

        handler(type_, code, value)
        await self.keycode_pause()
