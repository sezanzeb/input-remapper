#!/usr/bin/env python3
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2026 sezanzeb <4t1pzast9@mozmail.com>
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

from inputremapper.configs.mapping import Mapping


def mapping_from_combination(
    input_combination=None,
    target_uinput="keyboard",
    output_symbol="a",
):
    """Convenient function to get a valid mapping."""
    if not input_combination:
        input_combination = [{"type": 99, "code": 99, "analog_threshold": 99}]

    mapping = Mapping(
        input_combination=input_combination,
        target_uinput=target_uinput,
        output_symbol=output_symbol,
    )
    return mapping
