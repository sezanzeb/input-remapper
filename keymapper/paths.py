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

# the path that contains ALL symbols, not just ours
X11_SYMBOLS = '/usr/share/X11/xkb/symbols'

# should not contain spaces
# getlogin gets the user who ran sudo
USERS_SYMBOLS = os.path.join(
    '/usr/share/X11/xkb/symbols/key-mapper',
    os.getlogin().replace(' ', '_')
)

# those are the same for every preset and user, they are needed to make the
# presets work.
KEYCODES_PATH = '/usr/share/X11/xkb/keycodes/key-mapper'


def get_usr_path(device=None, preset=None):
    """Get the path to the config file in /usr.

    This folder is a symlink and the files are in ~/.config/key-mapper

    If preset is omitted, returns the folder for the device.
    """
    if device is None:
        return USERS_SYMBOLS

    device = device.strip()

    if preset is not None:
        preset = preset.strip()
        return os.path.join(USERS_SYMBOLS, device, preset).replace(' ', '_')

    if device is not None:
        return os.path.join(USERS_SYMBOLS, device.replace(' ', '_'))


DEFAULT_SYMBOLS = get_usr_path('default')
EMPTY_SYMBOLS = get_usr_path('empty')
