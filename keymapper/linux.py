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


"""Device and evdev stuff that is independent from the display server."""


import subprocess

import evdev

from keymapper.logger import logger


_devices = None


def can_grab(path):
    """Can input events from the device be read?

    Parameters
    ----------
    path : string
        Path in dev, for example '/dev/input/event7'
    """
    p = subprocess.run(['fuser', '-v', path])
    return p.returncode == 1


class KeycodeReader:
    """Keeps reading keycodes in the background for the UI to use.

    A new arriving keycode indicates that a button was pressed, so the
    UI can keep checking for a new keycode on this object and act like the
    keycode went right to the input box.

    GTK inputs cannot listen on keys that don't write a character, so
    they have to repeatedly ask for new data (in this solution).
    """
    def __init__(self):
        self.virtual_devices = []

    def clear(self):
        """Next time when reading don't return the previous keycode."""
        # read all of them to clear the buffer or whatever
        for virtual_device in self.virtual_devices:
            while virtual_device.read_one():
                pass

    def start_reading(self, device):
        """Tell the evdev lib to start looking for keycodes.

        If read is called without prior start_reading, no keycodes
        will be available.
        """
        logger.debug('Starting reading keycodes for %s', device)

        # Watch over each one of the potentially multiple devices per hardware
        paths = _devices[device]['paths']
        self.virtual_devices = [
            evdev.InputDevice(path)
            for path in paths[:1]
        ]

    def read(self):
        """Get the newest key or None if none was pressed."""
        newest_keycode = None
        for virtual_device in self.virtual_devices:
            while True:
                event = virtual_device.read_one()
                if event is None:
                    break
                elif event.type == evdev.ecodes.EV_KEY and event.value == 1:
                    # value: 1 for down, 0 for up, 2 for hold.
                    # this happens to report key codes that are 8 lower
                    # than the ones reported by xev
                    newest_keycode = event.code + 8
        return newest_keycode


keycode_reader = KeycodeReader()


def get_devices():
    """Group devices and get relevant infos per group.

    Returns a list containing mappings of
    {group_name: {paths: [paths], devices: [names]} for input devices.

    For example, group_name could be "Logitech USB Keyboard", devices might
    contain "Logitech USB Keyboard System Control" and "Logitech USB Keyboard".
    paths is a list of files in /dev/input that belong to the devices.

    They are grouped by usb port.
    """
    # cache the result, this takes a second to complete
    global _devices
    if _devices is not None:
        return _devices

    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]

    # group them together by usb device because there could be stuff like
    # "Logitech USB Keyboard" and "Logitech USB Keyboard Consumer Control"
    grouped = {}
    for device in devices:
        # only keyboard devices
        # https://www.kernel.org/doc/html/latest/input/event-codes.html
        if evdev.ecodes.EV_KEY not in device.capabilities().keys():
            continue

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
        result[shortest_name] = {
            'paths': devs,
            'devices': names
        }

    _devices = result
    logger.info('Found %s', ', '.join([f'"{name}"' for name in result]))
    return result
