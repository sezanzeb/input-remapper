#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2020 sezanzeb <proxima@hip70890b.de>
#
# This file is part of key-mapper.
#
# key-mapper is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# key-mapper is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with key-mapper.  If not, see <https://www.gnu.org/licenses/>.


"""Utility functions for all other modules in keymapper.dev"""


import evdev
from evdev.ecodes import EV_ABS


def max_abs(device):
    """Figure out the maximum value of EV_ABS events of that device.

    Like joystick movements or triggers.
    """
    # since input_device.absinfo(EV_ABS).max is too new for (some?) ubuntus,
    # figure out the max value via the capabilities
    capabilities = device.capabilities(absinfo=True)

    if EV_ABS not in capabilities:
        return None

    absinfos = [
        entry[1] for entry in
        capabilities[EV_ABS]
        if isinstance(entry, tuple) and isinstance(entry[1], evdev.AbsInfo)
    ]

    if len(absinfos) == 0:
        return None

    return absinfos[0].max
