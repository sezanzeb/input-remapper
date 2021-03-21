#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@sezanzeb.de>
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
import re

from keymapper.paths import get_preset_path, mkdir, CONFIG_PATH
from keymapper.logger import logger
from keymapper.getdevices import get_devices


def migrate_path():
    """Migrate the folder structure from < 0.4.0.

    Move existing presets into the new subfolder "presets"
    """
    new_preset_folder = os.path.join(CONFIG_PATH, 'presets')
    if not os.path.exists(get_preset_path()) and os.path.exists(CONFIG_PATH):
        logger.info('Migrating presets from < 0.4.0...')
        devices = os.listdir(CONFIG_PATH)
        mkdir(get_preset_path())
        for device in devices:
            path = os.path.join(CONFIG_PATH, device)
            if os.path.isdir(path):
                target = path.replace(CONFIG_PATH, new_preset_folder)
                logger.info('Moving "%s" to "%s"', path, target)
                os.rename(path, target)
        logger.info('done')


migrate_path()


def get_available_preset_name(device, preset='new preset', copy=False):
    """Increment the preset name until it is available."""
    if device is None:
        # endless loop otherwise
        raise ValueError('Device may not be None')

    preset = preset.strip()

    if copy and not re.match(r'^.+\scopy( \d+)?$', preset):
        preset = f'{preset} copy'

    # find a name that is not already taken
    if os.path.exists(get_preset_path(device, preset)):
        # if there already is a trailing number, increment it instead of
        # adding another one
        match = re.match(r'^(.+) (\d+)$', preset)
        if match:
            preset = match[1]
            i = int(match[2]) + 1
        else:
            i = 2

        while os.path.exists(get_preset_path(device, f'{preset} {i}')):
            i += 1

        return f'{preset} {i}'

    return preset


def get_presets(device):
    """Get all presets for the device and user, starting with the newest.

    Parameters
    ----------
    device : string
    """
    device_folder = get_preset_path(device)
    mkdir(device_folder)

    paths = glob.glob(os.path.join(device_folder, '*.json'))
    presets = [
        os.path.splitext(os.path.basename(path))[0]
        for path in sorted(paths, key=os.path.getmtime)
    ]
    # the highest timestamp to the front
    presets.reverse()
    return presets


def get_any_preset():
    """Return the first found tuple of (device, preset)."""
    devices = get_devices().keys()
    if len(devices) == 0:
        return None, None
    any_device = list(devices)[0]
    any_preset = (get_presets(any_device) or [None])[0]
    return any_device, any_preset


def find_newest_preset(device=None):
    """Get a tuple of (device, preset) that was most recently modified
    in the users home directory.

    If no device has been configured yet, return an arbitrary device.

    Parameters
    ----------
    device : string
        If set, will return the newest preset for the device or None
    """
    # sort the oldest files to the front in order to use pop to get the newest
    if device is None:
        paths = sorted(
            glob.glob(os.path.join(get_preset_path(), '*/*.json')),
            key=os.path.getmtime
        )
    else:
        paths = sorted(
            glob.glob(os.path.join(get_preset_path(device), '*.json')),
            key=os.path.getmtime
        )

    if len(paths) == 0:
        logger.debug('No presets found')
        return get_any_preset()

    online_devices = get_devices().keys()

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

    preset = os.path.splitext(preset)[0]
    logger.debug('The newest preset is "%s", "%s"', device, preset)

    return device, preset


def delete_preset(device, preset):
    """Delete one of the users presets."""
    preset_path = get_preset_path(device, preset)
    if not os.path.exists(preset_path):
        logger.debug('Cannot remove non existing path "%s"', preset_path)
        return

    logger.info('Removing "%s"', preset_path)
    os.remove(preset_path)

    device_path = get_preset_path(device)
    if os.path.exists(device_path) and len(os.listdir(device_path)) == 0:
        logger.debug('Removing empty dir "%s"', device_path)
        os.rmdir(device_path)


def rename_preset(device, old_preset_name, new_preset_name):
    """Rename one of the users presets while avoiding name conflicts."""
    if new_preset_name == old_preset_name:
        return None

    new_preset_name = get_available_preset_name(device, new_preset_name)
    logger.info('Moving "%s" to "%s"', old_preset_name, new_preset_name)
    os.rename(
        get_preset_path(device, old_preset_name),
        get_preset_path(device, new_preset_name)
    )
    # set the modification date to now
    now = time.time()
    os.utime(get_preset_path(device, new_preset_name), (now, now))
    return new_preset_name
