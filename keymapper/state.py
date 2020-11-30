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


"""Create some singleton objects that are needed for the app to work."""


import stat
import re
import subprocess
import evdev

from keymapper.mapping import Mapping


# offset between xkb and linux keycodes. linux keycodes are lower
KEYCODE_OFFSET = 8


def populate_system_mapping():
    """Get a mapping of all available names to their keycodes."""
    mapping = {}

    xmodmap = subprocess.check_output(['xmodmap', '-pke']).decode() + '\n'
    mappings = re.findall(r'(\d+) = (.+)\n', xmodmap)
    for keycode, names in mappings:
        for name in names.split():
            mapping[name] = int(keycode)

    for name, ecode in evdev.ecodes.ecodes.items():
        mapping[name] = ecode + KEYCODE_OFFSET

    return mapping


def clear_system_mapping():
    """Remove all mapped keys. Only needed for tests."""
    for key in system_mapping:
        del system_mapping[key]


# one mapping object for the whole application that holds all
# customizations, as shown in the UI
custom_mapping = Mapping()

# this mapping represents the xmodmap output, which stays constant
system_mapping = populate_system_mapping()

# permissions for files created in /usr
_PERMISSIONS = stat.S_IREAD | stat.S_IWRITE | stat.S_IRGRP | stat.S_IROTH
