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


class WhileEqTask(Task):
    """Repeat a macro while two values are equal.

    Named to mirror `if_eq(value_1, value_2, then, else)`. Unlike `toggle`,
    which starts/stops on repeated presses of the same trigger, `while_eq`
    is driven by a `set()`/`add()` variable that any other mapping can
    write to, so a *different* key can stop the loop. Unlike `repeat`, the
    variable is re-read every iteration instead of a fixed count being
    decided once at the start, so the loop actually returns (freeing the
    macro to be re-triggered) as soon as the condition flips, rather than
    idling through a fixed budget.
    """

    argument_configs = [
        ArgumentConfig(
            name="value_1",
            position=0,
            types=[str, int, float],
        ),
        ArgumentConfig(
            name="value_2",
            position=1,
            types=[str, int, float],
        ),
        ArgumentConfig(
            name="macro",
            position=2,
            types=[Macro],
        ),
    ]

    async def run(self, callback) -> None:
        value_1 = self.get_argument("value_1")
        value_2 = self.get_argument("value_2")
        macro = self.get_argument("macro").get_value()

        # Both are re-read every iteration, so that $variables are up to date.
        while value_1.get_value() == value_2.get_value():
            await macro.run(callback)
            await asyncio.sleep(1 / 1000)
