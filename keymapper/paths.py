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


"""Path constants to be used.

Is a module so that tests can modify them.
"""


import os
import subprocess


# since this needs to run as sudo,
# get the home dir of the user who called sudo.
who = subprocess.check_output('who').decode().split()[0]

# the path in home, is symlinked with SYMBOLS_PATH
CONFIG_PATH = os.path.join('/home', who, '.config/key-mapper')

# should not contain spaces
SYMBOLS_PATH = os.path.join(
    '/usr/share/X11/xkb/symbols/key-mapper',
    who.replace(' ', '_')
)

# those are the same for every preset and user
KEYCODES_PATH = '/usr/share/X11/xkb/keycodes/key-mapper'


def get_home_path(device, preset=None):
    """Get the path to the config file in /usr."""
    device = device.strip()
    if preset is not None:
        preset = preset.strip()
        return os.path.join(CONFIG_PATH, device, preset).replace(' ', '_')
    else:
        return os.path.join(CONFIG_PATH, device.replace(' ', '_'))


def get_usr_path(device, preset=None):
    """Get the path to the config file in /usr.

    This folder is a symlink and the files are in ~/.config/key-mapper

    If preset is omitted, returns the folder for the device.
    """
    device = device.strip()
    if preset is not None:
        preset = preset.strip()
        return os.path.join(SYMBOLS_PATH, device, preset).replace(' ', '_')
    else:
        return os.path.join(SYMBOLS_PATH, device.replace(' ', '_'))
