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

from inputremapper.configs.validation_errors import MacroError
from inputremapper.injection.macros.argument import ArgumentConfig
from inputremapper.injection.macros.task import Task
from inputremapper.logging.logger import logger


class AddTask(Task):
    """Add a number to a variable."""

    argument_configs = [
        ArgumentConfig(
            name="variable",
            position=0,
            types=[int, float, None],
            is_variable_name=True,
        ),
        ArgumentConfig(
            name="value",
            position=1,
            types=[int, float],
        ),
    ]

    async def run(self, callback) -> None:
        argument = self.get_argument("variable")
        try:
            current = argument.get_value()
        except MacroError:
            return

        if current is None:
            logger.debug(
                '"%s" initialized with 0',
                self.arguments["variable"]._variable.get_name(),
            )
            argument.set_value(0)
            current = 0

        addend = self.get_argument("value").get_value()

        if not isinstance(current, (int, float)):
            logger.error(
                'Expected variable "%s" to contain a number, but got "%s"',
                argument.get_value(),
                current,
            )
            return

        logger.debug("%s += %s", current, addend)
        argument.set_value(current + addend)
