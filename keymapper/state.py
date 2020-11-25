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

from keymapper.mapping import Mapping


def parse_xmodmap(mapping):
    """Read the output of xmodmap into a mapping."""
    xmodmap = subprocess.check_output(['xmodmap', '-pke']).decode() + '\n'
    mappings = re.findall(r'(\d+) = (.+)\n', xmodmap)
    for keycode, characters in mappings:
        # this is the "array" format needed for symbols files
        character = ', '.join(characters.split())
        mapping.change(
            previous_keycode=None,
            new_keycode=int(keycode),
            character=character
        )


# one mapping object for the whole application that holds all
# customizations, as shown in the UI
custom_mapping = Mapping()

# this mapping represents the xmodmap output, which stays constant
system_mapping = Mapping()
parse_xmodmap(system_mapping)

# permissions for files created in /usr
_PERMISSIONS = stat.S_IREAD | stat.S_IWRITE | stat.S_IRGRP | stat.S_IROTH
