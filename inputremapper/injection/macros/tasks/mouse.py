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

from evdev._ecodes import REL_Y, REL_X

from inputremapper.injection.macros.argument import ArgumentConfig
from inputremapper.injection.macros.macro import InjectEventCallback
from inputremapper.injection.macros.tasks.mouse_xy import MouseXYTask


class MouseTask(MouseXYTask):
    """Move the mouse cursor."""

    argument_configs = [
        ArgumentConfig(
            name="direction",
            position=0,
            types=[str],
        ),
        ArgumentConfig(
            name="speed",
            position=1,
            types=[int, float],
        ),
        ArgumentConfig(
            name="acceleration",
            position=2,
            types=[int, float],
            default=1,
        ),
    ]

    async def run(self, callback: InjectEventCallback) -> None:
        direction = self.get_argument("direction").get_value()
        speed = self.get_argument("speed").get_value()
        acceleration = self.get_argument("acceleration").get_value()

        code = {
            "up": REL_Y,
            "down": REL_Y,
            "left": REL_X,
            "right": REL_X,
        }[direction.lower()]

        await self.axis(
            code,
            speed,
            acceleration,
            callback,
        )
