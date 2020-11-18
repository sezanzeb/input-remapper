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


"""Path constants to be used."""


import os

EMPTY_SYMBOLS = '/usr/share/X11/xkb/symbols/key-mapper-empty'
CONFIG = os.path.join('/home', os.getlogin(), '.config/key-mapper')


def get_config_path(device=None, preset=None):
    """Get a path to the stored preset, or to store a preset to."""
    if device is None:
        return CONFIG
    if preset is None:
        return os.path.join(CONFIG, device)
    return os.path.join(CONFIG, device, preset)
