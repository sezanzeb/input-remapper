# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2022 sezanzeb <proxima@sezanzeb.de>
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


"""Utility functions."""

import sys
from hashlib import md5
from typing import Optional

import evdev


def is_service() -> bool:
    return sys.argv[0].endswith("input-remapper-service")


def get_device_hash(device: evdev.InputDevice) -> str:
    """get a unique hash for the given device"""
    # the builtin hash() function can not be used because it is randomly
    # seeded at python startup.
    # a non-cryptographic hash would be faster but there is none in the standard lib
    s = str(device.capabilities(absinfo=False)) + device.name
    return md5(s.encode()).hexdigest()


def get_evdev_constant_name(type_: int, code: int, *_) -> Optional[str]:
    """Handy function to get the evdev constant name."""
    # this is more readable than
    #   type_, code = event.type_and_code
    #   name = evdev.ecodes.bytype[type_][code]
    name = evdev.ecodes.bytype.get(type_, {}).get(code)
    if isinstance(name, list):
        return name[0]

    return name
