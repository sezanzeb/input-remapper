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


# xkb uses keycodes that are 8 higher than those from evdev
XKB_KEYCODE_OFFSET = 8


class SystemMapping:
    """Stores information about all available keycodes."""
    def __init__(self):
        """Construct the system_mapping."""
        self._mapping = {}
        self.populate()

    def populate(self):
        """Get a mapping of all available names to their keycodes."""
        self.clear()
        xmodmap = subprocess.check_output(['xmodmap', '-pke']).decode() + '\n'
        mappings = re.findall(r'(\d+) = (.+)\n', xmodmap)
        for keycode, names in mappings:
            # there might be multiple, like:
            # keycode  64 = Alt_L Meta_L Alt_L Meta_L
            # keycode 204 = NoSymbol Alt_L NoSymbol Alt_L
            # Alt_L should map to code 64. Writing code 204 only works
            # if a modifier is applied at the same time. So take the first
            # one.
            name = names.split()[0]
            self._set(name, int(keycode) - XKB_KEYCODE_OFFSET)

        for keycode, names in mappings:
            # but since KP may be mapped like KP_Home KP_7 KP_Home KP_7,
            # make another pass and add all of them if they don't already
            # exist. don't overwrite any keycodes.
            for name in names.split():
                if self.get(name) is None:
                    self._set(name, int(keycode) - XKB_KEYCODE_OFFSET)

        for name, ecode in evdev.ecodes.ecodes.items():
            self._set(name, ecode)

    def _set(self, name, code):
        """Map name to code."""
        self._mapping[str(name).lower()] = code

    def get(self, name):
        """Return the code mapped to the key."""
        return self._mapping.get(str(name).lower())

    def clear(self):
        """Remove all mapped keys. Only needed for tests."""
        keys = list(self._mapping.keys())
        for key in keys:
            del self._mapping[key]


# one mapping object for the whole application that holds all
# customizations, as shown in the UI
custom_mapping = Mapping()

# this mapping represents the xmodmap output, which stays constant
system_mapping = SystemMapping()

# permissions for files created in /usr
_PERMISSIONS = stat.S_IREAD | stat.S_IWRITE | stat.S_IRGRP | stat.S_IROTH
