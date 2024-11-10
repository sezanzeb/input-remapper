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

from evdev._ecodes import REL_Y, REL_X
from evdev.ecodes import EV_REL

from inputremapper.injection.macros.argument import ArgumentConfig
from inputremapper.injection.macros.task import Task


class MouseTask(Task):
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
            types=[int, float, None],
            default=None,
        ),
    ]

    async def run(self, handler) -> None:
        direction = self.get_argument("direction").get_value()
        speed = self.get_argument("speed").get_value()
        acceleration = self.get_argument("acceleration").get_value()

        code, value = {
            "up": (REL_Y, -1),
            "down": (REL_Y, 1),
            "left": (REL_X, -1),
            "right": (REL_X, 1),
        }[direction.lower()]

        current_speed = 0.0
        displacement_accumulator = 0.0
        displacement = 0
        if not acceleration:
            displacement = speed

        while self.is_holding():
            # Cursors can only move by integers. To get smooth acceleration for
            # small acceleration values, the cursor needs to move by a pixel every
            # few iterations. This can be achieved by remembering the decimal
            # places that were cast away, and using them for the next iteration.
            if acceleration and current_speed < speed:
                current_speed += acceleration
                current_speed = min(current_speed, speed)
                displacement_accumulator += current_speed
                displacement = int(displacement_accumulator)
                displacement_accumulator -= displacement

            handler(EV_REL, code, value * displacement)
            await asyncio.sleep(1 / self.mapping.rel_rate)
