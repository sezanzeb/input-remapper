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

from keymapper.paths import CONFIG_PATH, get_home_path
from keymapper.logger import logger
from keymapper.linux import get_devices


def get_presets(device):
    """Get all configured presets for the device, sorted by modification date.

    Parameters
    ----------
    device : string
    """
    device_folder = get_home_path(device)
    if not os.path.exists(device_folder):
        os.makedirs(device_folder)
    presets = [
        os.path.basename(path)
        for path in sorted(
            glob.glob(os.path.join(device_folder, '*')),
            key=os.path.getmtime
        )
    ]
    # the highest timestamp to the front
    presets.reverse()
    return presets


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
    any_device = list(get_devices().keys())[0]
    any_preset = (get_presets(any_device) or [None])[0]
    return any_device, any_preset


def find_newest_preset():
    """Get a tuple of (device, preset) that was most recently modified.

    If no device has been configured yet, return arbitrarily.
    """
    # sort the oldest files to the front in order to use pop to get the newest
    paths = sorted(
        glob.glob(os.path.join(CONFIG_PATH, '*/*')),
        key=os.path.getmtime
    )

    if len(paths) == 0:
        logger.debug('No presets found.')
        return get_any_preset()

    online_devices = [
        device.replace(' ', '_')
        for device in get_devices().keys()
    ]

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

    # ui: no underscores, filesystem: no whitespaces
    device = device and device.replace('_', ' ')
    preset = preset and preset.replace('_', ' ')

    logger.debug('The newest preset is "%s", "%s"', device, preset)

    return device, preset
