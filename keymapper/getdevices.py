#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@hip70890b.de>
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


import multiprocessing
import threading
import time
import asyncio

import evdev
from evdev.ecodes import EV_KEY, EV_ABS, KEY_CAMERA

from keymapper.logger import logger


_devices = None


TABLET_KEYS = [
    evdev.ecodes.BTN_STYLUS,
    evdev.ecodes.BTN_TOOL_BRUSH,
    evdev.ecodes.BTN_TOOL_PEN,
    evdev.ecodes.BTN_TOOL_RUBBER
]


if not hasattr(evdev.InputDevice, 'path'):
    # for evdev < 1.0.0 patch the path property
    @property
    def path(device):
        return device.fn

    evdev.InputDevice.path = path


def is_gamepad(device):
    """Check if joystick movements are available for mapping.

    Parameters
    ----------
    device : InputDevice
    """
    capabilities = device.capabilities(absinfo=False)
    abs_capabilities = capabilities.get(EV_ABS)
    if abs_capabilities is not None:
        if evdev.ecodes.ABS_MT_TRACKING_ID in abs_capabilities:
            # check for some random mousepad capability
            return False

        # graphics tablet tests.
        # They use ABS_X and ABS_Y for moving the cursor
        keys = capabilities.get(EV_KEY, [])
        if [key for key in keys if key in TABLET_KEYS]:
            return False

        if evdev.ecodes.ABS_X in abs_capabilities:
            # can be a joystick or a mousepad (already handled), so it's
            # a joystick
            return True

        if evdev.ecodes.ABS_Y in abs_capabilities:
            return True

    return False


class _GetDevices(threading.Thread):
    """Process to get the devices that can be worked with.

    Since InputDevice destructors take quite some time, do this
    asynchronously so that they can take as much time as they want without
    slowing down the initialization.
    """
    def __init__(self, pipe):
        """Construct the process.

        Parameters
        ----------
        pipe : multiprocessing.Pipe
            used to communicate the result
        """
        self.pipe = pipe
        super().__init__()

    def run(self):
        """Do what get_devices describes."""
        # evdev needs asyncio to work
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        logger.debug('Discovering device paths')

        # group them together by usb device because there could be stuff like
        # "Logitech USB Keyboard" and "Logitech USB Keyboard Consumer Control"
        grouped = {}
        for path in evdev.list_devices():
            device = evdev.InputDevice(path)

            if device.name == 'Power Button':
                continue

            gamepad = is_gamepad(device)

            # https://www.kernel.org/doc/html/latest/input/event-codes.html
            capabilities = device.capabilities(absinfo=False)

            key_capa = capabilities.get(EV_KEY)

            if key_capa is None and not gamepad:
                # skip devices that don't provide buttons that can be mapped
                continue

            if key_capa and len(key_capa) == 1 and key_capa[0] == KEY_CAMERA:
                # skip cameras
                continue

            name = device.name
            path = device.path

            info = (
                f'{device.info.bustype},'
                f'{device.info.vendor},'
                f'{device.info.product}'
                # observed a case with varying versions within a device,
                # so only use the other three as index
            )
            if grouped.get(info) is None:
                grouped[info] = []

            logger.spam(
                'Found "%s", "%s", "%s" %s',
                info, path, name, '(gamepad)' if gamepad else ''
            )

            grouped[info].append((name, path, gamepad))

        # now write down all the paths of that group
        result = {}
        for group in grouped.values():
            names = [entry[0] for entry in group]
            devs = [entry[1] for entry in group]
            gamepad = True in [entry[2] for entry in group]
            shortest_name = sorted(names, key=len)[0]
            result[shortest_name] = {
                'paths': devs,
                'devices': names,
                'gamepad': gamepad
            }

        self.pipe.send(result)


def refresh_devices():
    """This can be called to discover new devices."""
    # it may take a little bit of time until devices are visible after
    # changes
    time.sleep(0.1)
    global _devices
    _devices = None
    return get_devices()


def get_devices(include_keymapper=False):
    """Group devices and get relevant infos per group.

    Returns a list containing mappings of
    {group_name: {paths: [paths], devices: [names]} for input devices.

    For example, group_name could be "Logitech USB Keyboard", devices might
    contain "Logitech USB Keyboard System Control" and "Logitech USB Keyboard".
    paths is a list of files in /dev/input that belong to the devices.

    They are grouped by usb port.

    Since this needs to do some stuff with /dev and spawn processes the
    result is cached. Use refresh_devices if you need up to date
    devices.
    """
    global _devices
    if _devices is None:
        pipe = multiprocessing.Pipe()
        _GetDevices(pipe[1]).start()
        # block until devices are available
        _devices = pipe[0].recv()
        if len(_devices) == 0:
            logger.error('Did not find any input device')
        else:
            names = [f'"{name}"' for name in _devices]
            logger.info('Found %s', ', '.join(names))

    # filter the result
    result = {}
    for device in _devices.keys():
        if not include_keymapper and device.startswith('key-mapper'):
            continue

        result[device] = _devices[device]

    return result
