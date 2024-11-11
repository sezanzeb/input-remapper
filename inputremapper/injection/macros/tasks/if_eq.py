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

from inputremapper.injection.macros.argument import ArgumentConfig
from inputremapper.injection.macros.macro import Macro
from inputremapper.injection.macros.task import Task


class IfEqTask(Task):
    """Compare two values."""

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
            name="then",
            position=2,
            types=[Macro, None],
        ),
        ArgumentConfig(
            name="else",
            position=3,
            types=[Macro, None],
        ),
    ]

    async def run(self, callback) -> None:
        value_1 = self.get_argument("value_1").get_value()
        value_2 = self.get_argument("value_2").get_value()
        then = self.get_argument("then").get_value()
        else_ = self.get_argument("else").get_value()

        if value_1 == value_2:
            if then is not None:
                await then.run(callback)
        elif else_ is not None:
            await else_.run(callback)
