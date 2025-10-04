# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2025 sezanzeb <b8x45ygc9@mozmail.com>
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

from __future__ import annotations

import asyncio
import enum
import json
import multiprocessing
import os
import re
import threading
import traceback
from collections import defaultdict
from enum import unique
from typing import List, Optional, Tuple, Dict

import evdev
from evdev import InputDevice
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

from inputremapper.configs.global_config import GlobalConfig
from inputremapper.configs.paths import PathUtils
from inputremapper.logging.logger import logger
from inputremapper.utils import get_device_hash

TABLET_KEYS = [
    evdev.ecodes.BTN_STYLUS,
    evdev.ecodes.BTN_TOOL_BRUSH,
    evdev.ecodes.BTN_TOOL_PEN,
    evdev.ecodes.BTN_TOOL_RUBBER,
]


class DeviceType(str, enum.Enum):
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


def classify(device) -> DeviceType:
    """Figure out what kind of device this is.

    Use this instead of functions like _is_keyboard to avoid getting false
    positives.
    """
    capabilities = device.capabilities(absinfo=False)

    if _is_graphics_tablet(capabilities):
        # check this before is_gamepad to avoid classifying abs_x
        # as joysticks when they are actually stylus positions
        return DeviceType.GRAPHICS_TABLET

    if _is_touchpad(capabilities):
        return DeviceType.TOUCHPAD

    if _is_gamepad(capabilities):
        return DeviceType.GAMEPAD

    if _is_mouse(capabilities):
        return DeviceType.MOUSE

    if _is_camera(capabilities):
        return DeviceType.CAMERA

    if _is_keyboard(capabilities):
        # very low in the chain to avoid classifying most devices
        # as keyboard, because there are many with ev_key capabilities
        return DeviceType.KEYBOARD

    return DeviceType.UNKNOWN


DENYLIST = [".*Yubico.*YubiKey.*", "Eee PC WMI hotkeys"]


def is_denylisted(device: evdev.InputDevice):
    """Check if a device should not be used in input-remapper.

    Parameters
    ----------
    device
    """
    for name in DENYLIST:
        if re.match(name, str(device.name), re.IGNORECASE):
            return True

    return False


class Group:
    """Groups multiple devnodes together.

    For example, name could be "Logitech USB Keyboard", devices
    might contain "Logitech USB Keyboard System Control" and "Logitech USB
    Keyboard". paths is a list of files in /dev/input that belong to the
    devices.

    They are grouped by usb port.

    Members
    -------
    name : str
        A human-readable name, generated from .names, that should always
        look the same for a device model. It is used to generate the
        presets folder structure
    """

    def __init__(
        self,
        paths: List[os.PathLike],
        names: List[str],
        types: List[DeviceType | str],
        key: str,
        name: Optional[str] = None,
    ) -> None:
        """Specify a group

        Parameters
        ----------
        paths
            Paths in /dev/input of the grouped devices
        names
            Names of the grouped devices
        types
            Types of the grouped devices
        key
            Unique identifier of the group.

            It should be human readable and if possible equal to group.name.
            To avoid multiple groups having the same key, a number starting
            with 2 followed by a whitespace should be added to it:
            "key", "key 2", "key 3", ..., which allows to autoload different
            presets if multiple of the same device are connected.

            This is important for the autoloading configuration. If the key
            changed over reboots, then autoloading would break.
        name
            The name of the whole group. Defaults to the shortest of names.
            Used for the preset folder.

            The name should refer to a kind of device, not to a unique device.
            So two gamepads of the same make share the same preset folder.
        """
        if name is None:
            # There might be multiple groups with the same name here when
            # two similar devices are connected to the computer.
            self.name = sorted(names, key=len)[0]
        else:
            self.name = name

        self.key = key

        self.paths = paths
        self.names = names
        self.types = [DeviceType(type_) for type_ in types]

    def get_preset_path(self, preset: Optional[str] = None) -> str:
        """Get a path to the stored preset, or to store a preset to.

        This path is unique per device-model, not per group. Groups
        of the same model share the same preset paths.
        """
        return PathUtils.get_preset_path(self.name, preset)

    def get_devices(self) -> List[evdev.InputDevice]:
        devices: List[evdev.InputDevice] = []
        for path in self.paths:
            try:
                devices.append(evdev.InputDevice(path))
            except (FileNotFoundError, OSError):
                logger.error('Could not find "%s"', path)
                continue
        return devices

    def dumps(self):
        """Return a string representing this object."""
        return json.dumps(
            dict(
                paths=self.paths,
                names=self.names,
                types=self.types,
                key=self.key,
                name=self.name,
            ),
        )

    @classmethod
    def loads(cls, serialized: str):
        """Load a serialized representation."""
        group = cls(**json.loads(serialized))
        return group

    def __repr__(self):
        return f"<Group ({self.key}) at {hex(id(self))}>"


class _FindGroups(threading.Thread):
    """Thread to get the devices that can be worked with.

    Since InputDevice destructors take quite some time, do this
    asynchronously so that they can take as much time as they want without
    slowing down the initialization.
    """

    def __init__(
        self,
        global_config: GlobalConfig,
        pipe: multiprocessing.Pipe,
    ) -> None:
        """Construct the process.

        Parameters
        ----------
        pipe
            used to communicate the result
        """
        self.global_config = global_config
        self.pipe = pipe
        super().__init__()

    def run(self) -> None:
        # evdev needs asyncio to work
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        if self.global_config.get(["groups", "map_individually"]):
            result = self._group_by_unique_key()
        else:
            result = self._group_all_into_one()

        self.pipe.send(json.dumps([group.dumps() for group in result]))
        loop.close()  # avoid resource allocation warnings
        # now that everything is sent via the pipe, the InputDevice
        # destructors can go on and take ages to complete in the thread
        # without blocking anything

    def _group_by_unique_key(self) -> List[Group]:
        """Do what get_groups describes."""
        logger.debug("Grouping by unique key")
        # group them together by usb device because there could be stuff like
        # "Logitech USB Keyboard" and "Logitech USB Keyboard Consumer Control"
        grouped: Dict[str, List[Tuple[str, str, DeviceType]]] = defaultdict(list)
        for device in self._get_relevant_input_devices():
            key = self._get_unique_key(device)
            device_type = classify(device)
            grouped[key].append((device.name, device.path, device_type))

        custom_groups = self.global_config.get(["groups", "custom_groups"])

        # now write down all the paths of that group
        result = []
        used_names = set()
        for group in grouped.values():
            names = [entry[0] for entry in group]
            devs = [entry[1] for entry in group]

            # generate a human-readable key
            if devs[0] in custom_groups:
                unique_name = custom_groups[devs[0]]
            else:
                shortest_name = sorted(names, key=len)[0]
                unique_name = shortest_name
                i = 2
                while unique_name in used_names:
                    unique_name = f"{shortest_name} {i}"
                    i += 1

            used_names.add(unique_name)

            group = Group(
                key=unique_name,
                paths=devs,
                names=names,
                types=sorted(
                    list({item[2] for item in group if item[2] != DeviceType.UNKNOWN})
                ),
            )

            result.append(group)

        return result

    def _group_all_into_one(self) -> List[Group]:
        """Group all devices together into one group."""
        logger.debug("Creating one group for all devices")

        devices = self._get_relevant_input_devices()
        if len(devices) == 0:
            return []

        types = set()
        for device in devices:
            device_type = classify(device)
            if device_type != DeviceType.UNKNOWN:
                types.add(classify(device))

        group = Group(
            key="All devices",
            paths=[device.path for device in devices],
            names=[device.name for device in devices],
            types=sorted(list(types)),
            name="All devices",
        )

        return [group]

    def _get_unique_key(self, device: evdev.InputDevice) -> str:
        """Find a string key that is unique for a single hardware device.

        All InputDevices in /dev/input that originate from the same physical
        hardware device should return the same key via this function.
        """
        custom_groups = self.global_config.get(["groups", "custom_groups"])
        if device.name in custom_groups:
            return custom_groups[device.name]

        # Keys that should not be used:
        # - device.phys is empty sometimes and varies across virtual
        #   subdevices
        # - device.version varies across subdevices
        return (
            # device.info bustype, vendor and product are unique for
            # a product, but multiple similar device models would be grouped
            # in the same group
            f"{device.info.bustype}_"
            f"{device.info.vendor}_"
            f"{device.info.product}_"
            # device.uniq is empty most of the time. It seems to be the only way to
            # distinguish multiple connected bluetooth gamepads
            f"{device.uniq}_"
            # deivce.phys if "/input..." is removed from it, because the first
            # chunk seems to be unique per hardware (if it's not completely empty)
            f'{device.phys.split("/")[0] or "-"}'
        )

    def _get_relevant_input_devices(self) -> List[InputDevice]:
        devices = []
        for path in evdev.list_devices():
            device = self._filter_device(path)
            if device is None:
                continue

            device_type = classify(device)
            key = self._get_unique_key(device)

            logger.debug(
                'Found %s "%s" at "%s", hash "%s", key "%s"',
                device_type.value,
                device.name,
                path,
                get_device_hash(device),
                key,
            )

            devices.append(device)

        return devices

    def _filter_device(self, path: str) -> Optional[InputDevice]:
        """Check if input-remapper should even attempt to map the device.

        Return None if not. Otherwise, return the device.
        """
        try:
            device = evdev.InputDevice(path)
        except Exception as error:
            # Observed exceptions in journalctl:
            # - "SystemError: <built-in function ioctl_EVIOCGVERSION> returned NULL
            # without setting an error"
            # - "FileNotFoundError: [Errno 2] No such file or directory:
            # '/dev/input/event12'"
            logger.error(
                'Failed to access path "%s": %s %s',
                path,
                error.__class__.__name__,
                str(error),
            )
            return None

        if device.name == "Power Button":
            return None

        device_type = classify(device)

        if device_type == DeviceType.CAMERA:
            return None

        # https://www.kernel.org/doc/html/latest/input/event-codes.html
        capabilities = device.capabilities(absinfo=False)

        key_capa = capabilities.get(EV_KEY)
        abs_capa = capabilities.get(EV_ABS)
        rel_capa = capabilities.get(EV_REL)

        if key_capa is None and abs_capa is None and rel_capa is None:
            # skip devices that don't provide buttons or axes that can be mapped
            logger.debug('"%s" has no useful capabilities', device.name)
            return None

        if is_denylisted(device):
            logger.debug('"%s" is denylisted', device.name)
            return None

        return device


class Groups:
    """Contains and manages all groups."""

    def __init__(self, global_config: GlobalConfig):
        self.global_config = global_config
        self._groups: List[Group] = None

    def __getattribute__(self, key: str):
        """To lazy load group info only when needed.

        For example, this helps to keep logs of input-remapper-control clear when it
        doesn't need it the information.
        """
        if key == "_groups" and object.__getattribute__(self, "_groups") is None:
            object.__setattr__(self, "_groups", [])
            object.__getattribute__(self, "refresh")()

        return object.__getattribute__(self, key)

    def refresh(self):
        """Look for devices and group them together.

        Since this needs to do some stuff with /dev and spawn processes the
        result is cached. Use refresh_groups if you need up to date
        devices.
        """
        # The config affects the grouping, check for changes.
        # This is also important during startup, because the daemon will first load the
        # config, then load groups, and is then informed of a different config location.
        self.global_config.load_config()

        pipe = multiprocessing.Pipe()
        _FindGroups(self.global_config, pipe[1]).start()
        # block until groups are available
        self.loads(pipe[0].recv())

        if len(self._groups) == 0:
            logger.error("Did not find any input device")
        else:
            keys = [f'"{group.key}"' for group in self._groups]
            logger.info("Found %s", ", ".join(keys))

    def filter(self, include_inputremapper: bool = False) -> List[Group]:
        """Filter groups."""
        result = []
        for group in self._groups:
            name = group.name
            if not include_inputremapper and name.startswith("input-remapper"):
                continue

            result.append(group)

        return result

    def set_groups(self, new_groups: List[Group]):
        """Overwrite all groups."""
        logger.debug("Overwriting groups with %s", new_groups)
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

    def loads(self, dump: str):
        """Load a serialized representation created via dumps."""
        self._groups = [Group.loads(group) for group in json.loads(dump)]

    def find(
        self,
        name: Optional[str] = None,
        key: Optional[str] = None,
        path: Optional[str] = None,
        include_inputremapper: bool = False,
    ) -> Optional[Group]:
        """Find a group that matches the provided parameters.

        Parameters
        ----------
        name
            "USB Keyboard"
            Not unique, will return the first group that matches.
        key
            "USB Keyboard", "USB Keyboard 2", ...
        path
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
