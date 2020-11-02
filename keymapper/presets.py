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


"""Helperfunctions to find device ids, names, and to load configs."""


import os
import glob
import subprocess
from pathlib import Path

from keymapper.paths import CONFIG_PATH, SYMBOLS_PATH
from keymapper.logger import logger
from keymapper.X import find_devices, generate_setxkbmap_config


def get_presets(device):
    """Get all configured presets for the device, sorted by modification date.

    Parameters
    ----------
    device : string
    """
    device_folder = os.path.join(CONFIG_PATH, device)
    if not os.path.exists(device_folder):
        os.makedirs(device_folder)
    presets = os.listdir(device_folder)
    return presets


def create_preset(device, name=None):
    """Create an empty preset."""
    existing_names = get_presets(device)
    if name is None:
        name = 'new preset'

    # find a name that is not already taken
    i = 1
    while name in existing_names:
        i += 1
        name = f'{name} {i}'

    generate_setxkbmap_config(device, name, [])
    return name


def get_mappings(device, preset):
    """Get all configured buttons of the preset.

    Parameters
    ----------
    device : string
    preset : string
    """
    pass


def get_any_preset():
    """Return the first found tuple of (device, preset)."""
    any_device = list(find_devices().keys())[0]
    any_preset = (get_presets(any_device) or [None])[0]
    return any_device, any_preset


def find_newest_preset():
    """Get a tuple of (device, preset) that was most recently modified.

    If no device has been configured yet, return arbitrarily.
    """

    # sort the oldest files to the front
    paths = sorted(
        glob.glob(os.path.join(CONFIG_PATH, '*/*')),
        key=os.path.getmtime
    )

    if len(paths) == 0:
        logger.debug('No presets found.')
        return get_any_preset()

    online_devices = find_devices().keys()

    newest_path = None
    while len(paths) > 0:
        # take the newest path
        path = paths.pop()
        preset = os.path.split(path)[1]
        device = os.path.split(os.path.split(path)[0])[1]
        if device in online_devices:
            newest_path = path
            break

    if newest_path is None:
        logger.debug('None of the configured devices is currently online.')
        return get_any_preset()

    return device, preset
