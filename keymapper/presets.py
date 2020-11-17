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


"""Helperfunctions to find device ids, names, and to load presets."""


import os
import time
import glob

from keymapper.paths import get_usr_path, USERS_SYMBOLS
from keymapper.logger import logger
from keymapper.getdevices import get_devices


def get_presets(device):
    """Get all configured presets for the device, sorted by modification date.

    Parameters
    ----------
    device : string
    """
    device_folder = get_usr_path(device)
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
    return [preset.replace('_', ' ') for preset in presets]


def get_any_preset():
    """Return the first found tuple of (device, preset)."""
    devices = get_devices().keys()
    if len(devices) == 0:
        return None, None
    any_device = list(devices)[0].replace('_', ' ')
    any_preset = (get_presets(any_device) or [None])[0]
    if any_preset is not None:
        any_preset = any_preset.replace('_', ' ')
    return any_device, any_preset


def find_newest_preset(device=None):
    """Get a tuple of (device, preset) that was most recently modified.

    If no device has been configured yet, return an arbitrary device.

    Parameters
    ----------
    device : string
        If set, will return the newest preset for the device or None
    """
    # sort the oldest files to the front in order to use pop to get the newest
    if device is None:
        paths = sorted(
            glob.glob(os.path.join(USERS_SYMBOLS, '*/*')),
            key=os.path.getmtime
        )
    else:
        paths = sorted(
            glob.glob(os.path.join(get_usr_path(device), '*')),
            key=os.path.getmtime
        )

    if len(paths) == 0:
        logger.debug('No presets found')
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
        logger.debug('None of the configured devices is currently online')
        return get_any_preset()

    # ui: no underscores, filesystem: no whitespaces
    device = device and device.replace('_', ' ')
    preset = preset and preset.replace('_', ' ')

    logger.debug('The newest preset is "%s", "%s"', device, preset)

    return device, preset


def delete_preset(device, preset):
    """Delete a preset from the file system."""
    preset_path = get_usr_path(device, preset)
    if not os.path.exists(preset_path):
        logger.debug('Cannot remove non existing path "%s"', preset_path)
        return

    logger.info('Removing "%s"', preset_path)
    os.remove(preset_path)

    device_path = get_usr_path(device)
    if os.path.exists(device_path) and len(os.listdir(device_path)) == 0:
        logger.debug('Removing empty dir "%s"', device_path)
        os.rmdir(device_path)


def rename_preset(device, old_preset_name, new_preset_name):
    """Rename a preset while avoiding name conflicts."""
    new_preset_name = new_preset_name.strip()
    # find a name that is not already taken
    if os.path.exists(get_usr_path(device, new_preset_name)):
        i = 2
        while os.path.exists(get_usr_path(device, f'{new_preset_name} {i}')):
            i += 1
        new_preset_name = f'{new_preset_name} {i}'
    logger.info('Moving "%s" to "%s"', old_preset_name, new_preset_name)
    os.rename(
        get_usr_path(device, old_preset_name),
        get_usr_path(device, new_preset_name)
    )
    # set the modification date to now
    now = time.time()
    os.utime(get_usr_path(device, new_preset_name), (now, now))
