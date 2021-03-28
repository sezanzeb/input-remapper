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


"""Device and evdev stuff that is independent from the display server."""


import multiprocessing
import threading
import time
import asyncio

import evdev
from evdev.ecodes import EV_KEY, EV_ABS, KEY_CAMERA, EV_REL, BTN_STYLUS, \
    BTN_A, ABS_MT_POSITION_X, REL_X, KEY_A, BTN_LEFT

from keymapper.logger import logger


_devices = None

TABLET_KEYS = [
    evdev.ecodes.BTN_STYLUS,
    evdev.ecodes.BTN_TOOL_BRUSH,
    evdev.ecodes.BTN_TOOL_PEN,
    evdev.ecodes.BTN_TOOL_RUBBER
]

GAMEPAD = 'gamepad'
KEYBOARD = 'keyboard'
MOUSE = 'mouse'
TOUCHPAD = 'touchpad'
GRAPHICS_TABLET = 'graphics-tablet'
CAMERA = 'camera'
UNKNOWN = 'unknown'

# sort types that most devices would fall in easily to the right
PRIORITIES = [
    GRAPHICS_TABLET, TOUCHPAD, MOUSE, GAMEPAD, KEYBOARD, CAMERA, UNKNOWN
]


if not hasattr(evdev.InputDevice, 'path'):
    # for evdev < 1.0.0 patch the path property
    @property
    def path(device):
        return device.fn

    evdev.InputDevice.path = path


def _is_gamepad(capabilities):
    """Check if joystick movements are available for mapping."""
    if len(capabilities.get(EV_REL, [])) > 0:
        return False

    if BTN_A not in capabilities.get(EV_KEY, []):
        return False

    # joysticks
    abs_capabilities = capabilities.get(EV_ABS, [])
    if evdev.ecodes.ABS_X not in abs_capabilities:
        return False
    if evdev.ecodes.ABS_Y not in abs_capabilities:
        return False

    return True


def _is_mouse(capabilities):
    """Check if the capabilities represent those of a mouse."""
    if not REL_X in capabilities.get(EV_REL, []):
        return False

    if not BTN_LEFT in capabilities.get(EV_KEY, []):
        return False

    return True


def _is_graphics_tablet(capabilities):
    """Check if the capabilities represent those of a graphics tablet."""
    if BTN_STYLUS in capabilities.get(EV_KEY, []):
        return True
    return False


def _is_touchpad(capabilities):
    """Check if the capabilities represent those of a touchpad."""
    if ABS_MT_POSITION_X in capabilities.get(EV_ABS, []):
        return True
    return False


def _is_keyboard(capabilities):
    """Check if the capabilities represent those of a keyboard."""
    if KEY_A in capabilities.get(EV_KEY, []):
        return True
    return False


def _is_camera(capabilities):
    """Check if the capabilities represent those of a camera."""
    key_capa = capabilities.get(EV_KEY)
    return key_capa and len(key_capa) == 1 and key_capa[0] == KEY_CAMERA


def classify(device):
    """Figure out what kind of device this is.

    Use this instead of functions like _is_keyboard to avoid getting false
    positives.
    """
    capabilities = device.capabilities(absinfo=False)

    if _is_graphics_tablet(capabilities):
        # check this before is_gamepad to avoid classifying abs_x
        # as joysticks when they are actually stylus positions
        return GRAPHICS_TABLET

    if _is_touchpad(capabilities):
        return TOUCHPAD

    if _is_mouse(capabilities):
        return MOUSE

    if _is_gamepad(capabilities):
        return GAMEPAD

    if _is_camera(capabilities):
        return CAMERA

    if _is_keyboard(capabilities):
        # very low in the chain to avoid classifying most devices
        # as keyboard, because there are many with ev_key capabilities
        return KEYBOARD

    return UNKNOWN


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

            device_type = classify(device)

            if device_type == CAMERA:
                continue

            # https://www.kernel.org/doc/html/latest/input/event-codes.html
            capabilities = device.capabilities(absinfo=False)

            key_capa = capabilities.get(EV_KEY)

            if key_capa is None and device_type != GAMEPAD:
                # skip devices that don't provide buttons that can be mapped
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
                'Found "%s", "%s", "%s", type: %s',
                info, path, name, device_type
            )

            grouped[info].append((name, path, device_type))

        # now write down all the paths of that group
        result = {}
        for group in grouped.values():
            names = [entry[0] for entry in group]
            devs = [entry[1] for entry in group]

            # find the most specific type from all devices per group.
            # e.g. a device with mouse and keyboard subdevices is a mouse.
            types = sorted([entry[2] for entry in group], key=PRIORITIES.index)
            device_type = types[0]

            shortest_name = sorted(names, key=len)[0]
            result[shortest_name] = {
                'paths': devs,
                'devices': names,
                'type': device_type
            }

        self.pipe.send(result)


def refresh_devices():
    """This can be called to discover new devices.

    Only call this if appropriate permissions are available, otherwise
    the object may be empty afterwards.
    """
    # it may take a little bit of time until devices are visible after
    # changes
    time.sleep(0.1)
    global _devices
    _devices = None
    return get_devices()


def set_devices(devices):
    """Overwrite the object containing the devices."""
    global _devices
    _devices = devices


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
