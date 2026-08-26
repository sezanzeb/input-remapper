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

    async def run(self, callback) -> None:
        symbols = self.get_argument("*symbols").get_values()

        codes = [keyboard_layout.get(symbol) for symbol in symbols]

        held_codes = set()
        for code in codes:
            if code in held_codes:
                # Release and re-press to support duplicate keys in a sequence
                callback(EV_KEY, code, 0)
                await self.keycode_pause()
            callback(EV_KEY, code, 1)
            held_codes.add(code)
            await self.keycode_pause()

        await self._trigger_release_event.wait()

        # Release each unique code once, in reverse order of first appearance
        seen = set()
        unique_codes_reversed = []
        for code in reversed(codes):
            if code not in seen:
                seen.add(code)
                unique_codes_reversed.append(code)

        for code in unique_codes_reversed:
            callback(EV_KEY, code, 0)
            await self.keycode_pause()
