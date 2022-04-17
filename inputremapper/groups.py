#!/usr/bin/python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2022 sezanzeb <proxima@sezanzeb.de>
#
# This file is part of input-remapper.
#
# input-remapper is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# input-remapper is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with input-remapper.  If not, see <https://www.gnu.org/licenses/>.


"""Find, classify and group devices.

Because usually connected devices pop up multiple times in /dev/input,
in order to provide multiple types of input devices (e.g. a keyboard and a
graphics-tablet at the same time)

Those groups are what is being displayed in the device dropdown, and
events are being read from all of the paths of an individual group in the gui
and the injector.
"""


import re
import multiprocessing
import threading
import asyncio
import json
from typing import List

import evdev
from evdev.ecodes import (
    EV_KEY,
    EV_ABS,
    KEY_CAMERA,
    EV_REL,
    BTN_STYLUS,
    ABS_MT_POSITION_X,
    REL_X,
    KEY_A,
    BTN_LEFT,
    REL_Y,
    REL_WHEEL,
)

from inputremapper.logger import logger
from inputremapper.configs.paths import get_preset_path


TABLET_KEYS = [
    evdev.ecodes.BTN_STYLUS,
    evdev.ecodes.BTN_TOOL_BRUSH,
    evdev.ecodes.BTN_TOOL_PEN,
    evdev.ecodes.BTN_TOOL_RUBBER,
]

GAMEPAD = "gamepad"
KEYBOARD = "keyboard"
MOUSE = "mouse"
TOUCHPAD = "touchpad"
GRAPHICS_TABLET = "graphics-tablet"
CAMERA = "camera"
UNKNOWN = "unknown"


if not hasattr(evdev.InputDevice, "path"):
    # for evdev < 1.0.0 patch the path property
    @property
    def path(device):
        return device.fn

    evdev.InputDevice.path = path


def _is_gamepad(capabilities):
    """Check if joystick movements are available for preset."""
    # A few buttons that indicate a gamepad
    buttons = {
        evdev.ecodes.BTN_BASE,
        evdev.ecodes.BTN_A,
        evdev.ecodes.BTN_THUMB,
        evdev.ecodes.BTN_TOP,
        evdev.ecodes.BTN_DPAD_DOWN,
        evdev.ecodes.BTN_GAMEPAD,
    }
    if not buttons.intersection(capabilities.get(EV_KEY, [])):
        # no button is in the key capabilities
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
    # Based on observation, those capabilities need to be present to get an
    # UInput recognized as mouse

    # mouse movements
    if not REL_X in capabilities.get(EV_REL, []):
        return False
    if not REL_Y in capabilities.get(EV_REL, []):
        return False

    # at least the vertical mouse wheel
    if not REL_WHEEL in capabilities.get(EV_REL, []):
        return False

    # and a mouse click button
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

    if _is_gamepad(capabilities):
        return GAMEPAD

    if _is_mouse(capabilities):
        return MOUSE

    if _is_camera(capabilities):
        return CAMERA

    if _is_keyboard(capabilities):
        # very low in the chain to avoid classifying most devices
        # as keyboard, because there are many with ev_key capabilities
        return KEYBOARD

    return UNKNOWN


DENYLIST = [".*Yubico.*YubiKey.*", "Eee PC WMI hotkeys"]


def is_denylisted(device):
    """Check if a device should not be used in input-remapper.

    Parameters
    ----------
    device : InputDevice
    """
    for name in DENYLIST:
        if re.match(name, str(device.name), re.IGNORECASE):
            return True

    return False


def get_unique_key(device):
    """Find a string key that is unique for a single hardware device.

    All InputDevices in /dev/input that originate from the same physical
    hardware device should return the same key via this function.

    Parameters
    ----------
    device : InputDevice
    """
    # Keys that should not be used:
    # - device.phys is empty sometimes and varies across virtual
    #   subdevices
    # - device.version varies across subdevices
    # - device.uniq is empty most of the time, I don't know what this is
    #   supposed to be
    return (
        # device.info bustype, vendor and product are unique for
        # a product, but multiple similar device models would be grouped
        # in the same group
        f"{device.info.bustype}_"
        f"{device.info.vendor}_"
        f"{device.info.product}_"
        # deivce.phys if "/input..." is removed from it, because the first
        # chunk seems to be unique per hardware (if it's not completely empty)
        f'{device.phys.split("/")[0] or "-"}'
    )


class _Group:
    """Groups multiple devnodes together.

    For example, name could be "Logitech USB Keyboard", devices
    might contain "Logitech USB Keyboard System Control" and "Logitech USB
    Keyboard". paths is a list of files in /dev/input that belong to the
    devices.

    They are grouped by usb port.

    Members
    -------
    name : str
        A human readable name, generated from .names, that should always
        look the same for a device model. It is used to generate the
        presets folder structure
    """

    def __init__(self, paths: List[str], names: List[str], types: List[str], key: str):
        """Specify a group

        Parameters
        ----------
        paths : str[]
            Paths in /dev/input of the grouped devices
        names : str[]
            Names of the grouped devices
        types : str[]
            Types of the grouped devices
        key : str
            Unique identifier of the group.

            It should be human readable and if possible equal to group.name.
            To avoid multiple groups having the same key, a number starting
            with 2 followed by a whitespace should be added to it:
            "key", "key 2", "key 3", ...

            This is important for the autoloading configuration. If the key
            changed over reboots, then autoloading would break.
        """
        # There might be multiple groups with the same name here when two
        # similar devices are connected to the computer.
        self.name: str = sorted(names, key=len)[0]

        self.key = key

        self.paths = paths
        self.names = names
        self.types = types

    def get_preset_path(self, preset=None):
        """Get a path to the stored preset, or to store a preset to.

        This path is unique per device-model, not per group. Groups
        of the same model share the same preset paths.
        """
        return get_preset_path(self.name, preset)

    def dumps(self):
        """Return a string representing this object."""
        return json.dumps(
            dict(paths=self.paths, names=self.names, types=self.types, key=self.key)
        )

    @classmethod
    def loads(cls, serialized):
        """Load a serialized representation."""
        group = cls(**json.loads(serialized))
        return group

    def __repr__(self):
        return f"Group({self.key})"


class _FindGroups(threading.Thread):
    """Thread to get the devices that can be worked with.

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
        """Do what get_groups describes."""
        # evdev needs asyncio to work
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        logger.debug("Discovering device paths")

        # group them together by usb device because there could be stuff like
        # "Logitech USB Keyboard" and "Logitech USB Keyboard Consumer Control"
        grouped = {}
        for path in evdev.list_devices():
            try:
                device = evdev.InputDevice(path)
            except Exception as error:
                # Observed exceptions in journalctl:
                # - "SystemError: <built-in function ioctl_EVIOCGVERSION> returned NULL
                # without setting an error"
                # - "FileNotFoundError: [Errno 2] No such file or directory:
                # '/dev/input/event12'"
                logger.error("Failed to access %s: %s", path, str(error))
                continue

            if device.name == "Power Button":
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

            if is_denylisted(device):
                continue

            key = get_unique_key(device)
            if grouped.get(key) is None:
                grouped[key] = []

            logger.debug(
                'Found "%s", "%s", "%s", type: %s', key, path, device.name, device_type
            )

            grouped[key].append((device.name, path, device_type))

        # now write down all the paths of that group
        result = []
        used_keys = set()
        for group in grouped.values():
            names = [entry[0] for entry in group]
            devs = [entry[1] for entry in group]

            # generate a human readable key
            shortest_name = sorted(names, key=len)[0]
            key = shortest_name
            i = 2
            while key in used_keys:
                key = f"{shortest_name} {i}"
                i += 1
            used_keys.add(key)

            group = _Group(
                key=key,
                paths=devs,
                names=names,
                types=sorted(list({item[2] for item in group if item[2] != UNKNOWN})),
            )

            result.append(group.dumps())

        self.pipe.send(json.dumps(result))
        # now that everything is sent via the pipe, the InputDevice
        # destructors can go on an take ages to complete in the thread
        # without blocking anything


class _Groups:
    """Contains and manages all groups."""

    def __init__(self):
        self._groups: List[_Group] = None

    def __getattribute__(self, key):
        """To lazy load group info only when needed.

        For example, this helps to keep logs of input-remapper-control clear when it doesnt
        need it the information.
        """
        if key == "_groups" and object.__getattribute__(self, "_groups") is None:
            object.__setattr__(self, "_groups", {})
            object.__getattribute__(self, "refresh")()

        return object.__getattribute__(self, key)

    def refresh(self):
        """Look for devices and group them together.

        Since this needs to do some stuff with /dev and spawn processes the
        result is cached. Use refresh_groups if you need up to date
        devices.
        """
        pipe = multiprocessing.Pipe()
        _FindGroups(pipe[1]).start()
        # block until groups are available
        self.loads(pipe[0].recv())

        if len(self._groups) == 0:
            logger.debug("Did not find any input device")
        else:
            keys = [f'"{group.key}"' for group in self._groups]
            logger.info("Found %s", ", ".join(keys))

    def filter(self, include_inputremapper=False):
        """Filter groups."""
        result = []
        for group in self._groups:
            name = group.name
            if not include_inputremapper and name.startswith("input-remapper"):
                continue

            result.append(group)

        return result

    def set_groups(self, new_groups):
        """Overwrite all groups."""
        self._groups = new_groups

    def list_group_names(self) -> List[str]:
        """Return a list of all 'name' properties of the groups."""
        return [
            group.name
            for group in self._groups
            if not group.name.startswith("input-remapper")
        ]

    def __len__(self):
        return len(self._groups)

    def __iter__(self):
        return iter(self._groups)

    def dumps(self):
        """Create a deserializable string representation."""
        return json.dumps([group.dumps() for group in self._groups])

    def loads(self, dump):
        """Load a serialized representation created via dumps."""
        self._groups = [_Group.loads(group) for group in json.loads(dump)]

    def find(
        self,
        name: str = None,
        key: str = None,
        path: str = None,
        include_inputremapper: bool = False,
    ) -> _Group:
        """Find a group that matches the provided parameters.

        Parameters
        ----------
        name : str
            "USB Keyboard"
            Not unique, will return the first group that matches.
        key : str
            "USB Keyboard", "USB Keyboard 2", ...
        path : str
            "/dev/input/event3"
        """
        for group in self._groups:
            if not include_inputremapper and group.name.startswith("input-remapper"):
                continue

            if name and group.name != name:
                continue

            if key and group.key != key:
                continue

            if path and path not in group.paths:
                continue

            return group

        return None


groups = _Groups()
