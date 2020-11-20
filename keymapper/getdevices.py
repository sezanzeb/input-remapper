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


import multiprocessing

import evdev

from keymapper.logger import logger
from keymapper.config import config


_devices = None


class _GetDevicesProcess(multiprocessing.Process):
    """Process to get the devices that can be worked with.

    Since InputDevice destructors take quite some time, do this
    asynchronously so that they can take as much time as they want without
    slowing down the initialization. To avoid evdevs asyncio stuff spamming
    errors, do this with multiprocessing and not multithreading.
    TODO to threading, make eventloop
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
        logger.debug('Discovering device paths')
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]

        # group them together by usb device because there could be stuff like
        # "Logitech USB Keyboard" and "Logitech USB Keyboard Consumer Control"
        grouped = {}
        for device in devices:
            if device.phys.startswith('key-mapper'):
                # injector device, not really periphery
                continue

            # only keyboard devices
            # https://www.kernel.org/doc/html/latest/input/event-codes.html
            capabilities = device.capabilities().keys()
            if evdev.ecodes.EV_KEY not in capabilities:
                continue

            if (
                not config.may_modify_movement_devices()
                and evdev.ecodes.EV_REL in capabilities
            ):
                # skip devices that control movement to avoid affecting
                # their performance due to the amount of their events.
                # TODO add checkbox to automatically load
                #  a preset on login
                logger.debug(
                    'Skipping %s to avoid impairing mouse movement',
                    device.path
                )
                continue

            usb = device.phys.split('/')[0]
            if grouped.get(usb) is None:
                grouped[usb] = []

            logger.debug('Found "%s", %s, %s', device.name, device.path, usb)

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

        self.pipe.send(result)


def refresh_devices():
    """Get new devices, e.g. new ones created by key-mapper."""
    global _devices
    _devices = None
    return get_devices()


def get_devices():
    """Group devices and get relevant infos per group.

    Returns a list containing mappings of
    {group_name: {paths: [paths], devices: [names]} for input devices.

    For example, group_name could be "Logitech USB Keyboard", devices might
    contain "Logitech USB Keyboard System Control" and "Logitech USB Keyboard".
    paths is a list of files in /dev/input that belong to the devices.

    They are grouped by usb port.
    """
    global _devices
    if _devices is None:
        pipe = multiprocessing.Pipe()
        _GetDevicesProcess(pipe[1]).start()
        # block until devices are available
        _devices = pipe[0].recv()
        logger.info('Found %s', ', '.join([f'"{name}"' for name in _devices]))
    return _devices
