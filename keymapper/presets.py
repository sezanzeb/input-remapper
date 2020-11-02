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
import evdev

from keymapper.paths import CONFIG_PATH
from keymapper.logger import logger
from keymapper.X import create_setxkbmap_config


_devices = None


def get_devices():
    """Get a mapping of {name: [paths]} for input devices."""
    # cache the result, this takes a second to complete
    global _devices
    if _devices is not None:
        return _devices

    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    # group them together by usb device because there could be stuff like
    # "Logitech USB Keyboard" and "Logitech USB Keyboard Consumer Control"
    grouped = {}
    for device in devices:
        usb = device.phys.split('/')[0]
        if grouped.get(usb) is None:
            grouped[usb] = []
        grouped[usb].append((device.name, device.path))
    # now write down all the paths of that group
    result = {}
    for group in grouped.values():
        names = [entry[0] for entry in group]
        devs = [entry[1] for entry in group]
        shortest_name = sorted(names, key=len)[0]
        result[shortest_name] = devs

    _devices = result
    logger.info('Found %s', ', '.join([f'"{name}"' for name in result]))
    return result


def get_presets(device):
    """Get all configured presets for the device, sorted by modification date.

    Parameters
    ----------
    device : string
    """
    device_folder = os.path.join(CONFIG_PATH, device)
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


def create_preset(device, name=None):
    """Create an empty preset."""
    existing_names = get_presets(device)
    if name is None:
        name = 'new preset'

    # find a name that is not already taken
    if name in existing_names:
        i = 2
        while f'{name} {i}' in existing_names:
            i += 1
        name = f'{name} {i}'

    create_setxkbmap_config(device, name, [])
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
    any_device = list(get_devices().keys())[0]
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
        logger.debug('None of the configured devices is currently online.')
        return get_any_preset()

    logger.debug('The newest preset is "%s", "%s"', device, preset)

    return device, preset
