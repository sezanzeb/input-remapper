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
from typing import Union

from evdev._ecodes import REL_Y, REL_X
from evdev.ecodes import EV_REL

from inputremapper.injection.macros.argument import ArgumentConfig
from inputremapper.injection.macros.macro import InjectEventCallback
from inputremapper.injection.macros.task import Task


class MouseXYTask(Task):
    """Move the mouse cursor."""

    argument_configs = [
        ArgumentConfig(
            name="x",
            position=0,
            types=[int, float],
            default=0,
        ),
        ArgumentConfig(
            name="y",
            position=1,
            types=[int, float],
            default=0,
        ),
        ArgumentConfig(
            name="acceleration",
            position=2,
            types=[int, float],
            default=1,
        ),
    ]

    async def run(self, callback: InjectEventCallback) -> None:
        x = self.get_argument("x").get_value()
        y = self.get_argument("y").get_value()
        acceleration = self.get_argument("acceleration").get_value()
        await asyncio.gather(
            self.axis(REL_X, x, acceleration, callback),
            self.axis(REL_Y, y, acceleration, callback),
        )

    async def axis(
        self,
        code: int,
        speed: Union[int, float],
        fractional_acceleration: Union[int, float],
        callback: InjectEventCallback,
    ) -> None:
        acceleration = speed * fractional_acceleration
        direction = -1 if speed < 0 else 1
        current_speed = 0.0
        displacement_accumulator = 0.0
        displacement = 0
        if acceleration <= 0:
            displacement = int(speed)

        while self.is_holding():
            # Cursors can only move by integers. To get smooth acceleration for
            # small acceleration values, the cursor needs to move by a pixel every
            # few iterations. This can be achieved by remembering the decimal
            # places that were cast away, and using them for the next iteration.
            if acceleration and abs(current_speed) < abs(speed):
                current_speed += acceleration
                current_speed = direction * min(abs(current_speed), abs(speed))
                displacement_accumulator += current_speed
                displacement = int(displacement_accumulator)
                displacement_accumulator -= displacement

            if displacement != 0:
                callback(EV_REL, code, displacement)

            await asyncio.sleep(1 / self.mapping.rel_rate)
