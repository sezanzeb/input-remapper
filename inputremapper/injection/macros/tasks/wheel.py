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

import math

from evdev.ecodes import (
    EV_REL,
    REL_WHEEL_HI_RES,
    REL_HWHEEL_HI_RES,
    REL_WHEEL,
    REL_HWHEEL,
)

from inputremapper.injection.macros.argument import ArgumentConfig
from inputremapper.injection.macros.task import Task
from inputremapper.injection.macros.tasks.util import precise_iteration_frequency


class WheelTask(Task):
    """Move the scroll wheel."""

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
    ]

    async def run(self, callback) -> None:
        direction = self.get_argument("direction").get_value()

        # 120, see https://www.kernel.org/doc/html/latest/input/event-codes.html#ev-rel
        code, value = {
            "up": ([REL_WHEEL, REL_WHEEL_HI_RES], [1 / 120, 1]),
            "down": ([REL_WHEEL, REL_WHEEL_HI_RES], [-1 / 120, -1]),
            "left": ([REL_HWHEEL, REL_HWHEEL_HI_RES], [1 / 120, 1]),
            "right": ([REL_HWHEEL, REL_HWHEEL_HI_RES], [-1 / 120, -1]),
        }[direction.lower()]

        speed = self.get_argument("speed").get_value()
        remainder = [0.0, 0.0]

        async for _ in precise_iteration_frequency(self.mapping.rel_rate):
            if not self.is_holding():
                return

            for i in range(0, 2):
                float_value = value[i] * speed + remainder[i]
                remainder[i] = math.fmod(float_value, 1)
                if abs(float_value) >= 1:
                    callback(EV_REL, code[i], int(float_value))
