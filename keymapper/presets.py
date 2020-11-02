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
from keymapper.config import get_config, get_config_path
from keymapper.X import find_devices


def get_presets(device):
    """Get all configured presets for the device, sorted by modification date.

    Parameters
    ----------
    device : string
    """
    device_folder = os.path.join(SYMBOLS_PATH, device.replace(' ', '_'))
    if not os.path.exists(device_folder):
        os.makedirs(get_config_path(device_folder))
    presets = os.listdir(get_config_path(device_folder))
    logger.debug('Presets in "%s": %s', device_folder, ', '.join(presets))
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
        name = f'new preset {i}'

    # trigger the creation of a new config file:
    get_config(device, name)
    return name


def get_mappings(device, preset):
    """Get all configured buttons of the preset.

    Parameters
    ----------
    device : string
    preset : string
    """
    pass


def find_newest_preset():
    """Get a tuple of (device, preset) that was most recently modified.

    If no device has been configured yet, return arbitrarily.
    """
    # sort the oldest files to the front
    paths = sorted(
        glob.glob(os.path.join(SYMBOLS_PATH, '*/*')),
        key=os.path.getmtime
    )

    # map "vendor_keyboard" to "vendor keyboard"
    device_mapping = {
        name.replace(' ', '_'): name
        for name in find_devices().keys()
    }

    newest_path = None
    while len(paths) > 0:
        # take the newest path
        path = paths.pop()
        preset = os.path.split(path)[1]
        device_underscored = os.path.split(os.path.split(path)[0])[1]
        if device_mapping.get(device_underscored) is not None:
            # this device is online
            newest_path = path
            break

    if newest_path is None:
        logger.debug('None of the configured devices is currently online.')
        # return anything
        device = list(find_devices().keys())[0]
        preset = (get_presets(device) or [None])[0]
        return device, preset

    device = device_mapping.get(device_underscored)

    return device, preset
