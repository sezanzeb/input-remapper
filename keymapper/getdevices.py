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
from evdev.ecodes import EV_KEY, EV_ABS

from keymapper.logger import logger


_devices = None


if not hasattr(evdev.InputDevice, 'path'):
    # for evdev < 1.0.0 patch the path property
    @property
    def path(device):
        return device.fn

    evdev.InputDevice.path = path


def map_abs_to_rel(capabilities):
    """Check if joystick movements can and should be mapped."""
    # mapping buttons only works without ABS events in the capabilities,
    # possibly due to some intentional constraints in the os. So always
    # just map those events to REL if possible and remove ABS from
    # the capabilities, because ABS events prevent regular button
    # mappings from working,
    abs_capabilities = capabilities.get(EV_ABS)
    if abs_capabilities is not None:
        if evdev.ecodes.ABS_MT_TRACKING_ID in abs_capabilities:
            # check for some random mousepad capability
            return False

        if evdev.ecodes.BTN_TOOL_BRUSH in capabilities.get(EV_KEY, []):
            # a graphics tablet, not a gamepad
            return False
        if evdev.ecodes.BTN_STYLUS in capabilities.get(EV_KEY, []):
            # another graphics tablet test
            return False

        if evdev.ecodes.ABS_X in abs_capabilities:
            # can be a joystick or a mousepad (already handled), so it's
            # a joystick
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
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]

        # group them together by usb device because there could be stuff like
        # "Logitech USB Keyboard" and "Logitech USB Keyboard Consumer Control"
        grouped = {}
        for device in devices:
            if device.name == 'Power Button':
                continue

            # only keyboard devices
            # https://www.kernel.org/doc/html/latest/input/event-codes.html
            capabilities = device.capabilities(absinfo=False)
            if EV_KEY not in capabilities and EV_ABS not in capabilities:
                # or gamepads, because they can be mapped like a keyboard
                continue

            is_gamepad = map_abs_to_rel(capabilities)

            name = device.name
            path = device.path

            info = str(device.info)
            if grouped.get(info) is None:
                grouped[info] = []

            logger.spam('Found "%s", "%s", "%s"', info, path, name)

            grouped[info].append((name, path, is_gamepad))

        # now write down all the paths of that group
        result = {}
        for group in grouped.values():
            names = [entry[0] for entry in group]
            devs = [entry[1] for entry in group]
            is_gamepad = True in [entry[2] for entry in group]
            shortest_name = sorted(names, key=len)[0]
            result[shortest_name] = {
                'paths': devs,
                'devices': names,
                'gamepad': is_gamepad
            }

        self.pipe.send(result)


def refresh_devices():
    """Get new devices, e.g. new ones created by key-mapper.

    This should be called whenever devices in /dev are added or removed.
    """
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
            logger.error(
                'Did not find any device. If you added yourself to the '
                'needed groups (see `ls -l /dev/input`)  already, make sure '
                'you also logged out and back in.'
            )
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
