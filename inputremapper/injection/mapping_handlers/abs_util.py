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

from typing import Tuple

import evdev
from evdev.ecodes import EV_ABS, ABS_GAS, ABS_BRAKE

from inputremapper.input_event import InputEvent


def calculate_trigger_point(
    event: InputEvent,
    analog_threshold: int,
    source: evdev.InputDevice,
) -> Tuple[float, float]:
    """Calculate the threshold and resting point of the axis.

    If an EV_ABS events value suprasses the threshold, it should be considered pressed.
    The resting point might be the middle value for a joystick: 0, *128*, 256 or
    -128, *0*, 128. Or it might be the minimum value of the shoulder triggers: *0* 256.
    """
    absinfo = dict(source.capabilities(absinfo=True)[EV_ABS])  # type: ignore
    abs_min = absinfo[event.code].min
    abs_max = absinfo[event.code].max

    assert analog_threshold
    if abs_min == -1 and abs_max == 1:
        # this is a hat switch
        # return +-1
        return (
            analog_threshold // abs(analog_threshold),
            0,
        )

    if event.code in [ABS_GAS, ABS_BRAKE]:
        threshold = abs_max * analog_threshold / 100
        # For the L/R triggers, there is only one direction, and the resting
        # position is the same as the min_abs.
        middle = abs_min
        return threshold, middle

    half_range = (abs_max - abs_min) / 2
    middle = half_range + abs_min
    trigger_offset = half_range * analog_threshold / 100
    # Examples for threshold of +50:
    # -128 to 128. half_range is 128. middle is 0. trigger_offset is 64 (and above)
    # 0 to 128. half_range is 64. middle is 64. trigger_offset is 96 (and above)

    # threshold, middle
    threshold = middle + trigger_offset
    return threshold, middle
