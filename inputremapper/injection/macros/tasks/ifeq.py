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


class DeprecatedIfEqTask(Task):
    """Old version of if_eq, kept for compatibility reasons.

    This can't support a comparison like ifeq("foo", $blub) with blub containing
    "foo" without breaking old functionality, because "foo" is treated as a
    variable name.
    """

    argument_configs = [
        ArgumentConfig(
            name="variable",
            position=0,
            types=[str],
            is_variable_name=True,
        ),
        ArgumentConfig(
            name="value",
            position=1,
            types=[str, float, int],
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

    async def run(self, handler) -> None:
        actual_value = self.get_argument("variable").get_value()
        value = self.get_argument("value").get_value()
        then = self.get_argument("then").get_value()
        else_ = self.get_argument("else").get_value()

        # The old ifeq function became somewhat incompatible with the new macro code.
        # I need to compare them as strings to keep this working.
        if str(actual_value) == str(value):
            if then is not None:
                await then.run(handler)
        elif else_ is not None:
            await else_.run(handler)
