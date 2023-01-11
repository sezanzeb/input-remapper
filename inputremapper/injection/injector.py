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


"""Keeps injecting keycodes in the background based on the preset."""
from __future__ import annotations

import asyncio
import enum
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Union

import evdev

from inputremapper.configs.input_config import InputCombination, InputConfig
from inputremapper.configs.preset import Preset
from inputremapper.groups import (
    _Group,
    classify,
    DeviceType,
)
from inputremapper.gui.messages.message_broker import MessageType
from inputremapper.injection.context import Context
from inputremapper.injection.event_reader import EventReader
from inputremapper.injection.numlock import set_numlock, is_numlock_on, ensure_numlock
from inputremapper.logger import logger
from inputremapper.utils import get_device_hash

CapabilitiesDict = Dict[int, List[int]]
GroupSources = List[evdev.InputDevice]

DEV_NAME = "input-remapper"


# messages sent to the injector process
class InjectorCommand(str, enum.Enum):
    CLOSE = "CLOSE"


# messages the injector process reports back to the service
class InjectorState(str, enum.Enum):
    """Possible States of the Injector."""

    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"
    NO_GRAB = "NO_GRAB"
    UPGRADE_EVDEV = "UPGRADE_EVDEV"


def is_in_capabilities(
    combination: InputCombination, capabilities: CapabilitiesDict
) -> bool:
    """Are this combination or one of its sub keys in the capabilities?"""
    for event in combination:
        if event.code in capabilities.get(event.type, []):
            return True

    return False


def get_udev_name(name: str, suffix: str) -> str:
    """Make sure the generated name is not longer than 80 chars."""
    max_len = 80  # based on error messages
    remaining_len = max_len - len(DEV_NAME) - len(suffix) - 2
    middle = name[:remaining_len]
    name = f"{DEV_NAME} {middle} {suffix}"
    return name


@dataclass(frozen=True)
class InjectorStateMessage:
    message_type = MessageType.injector_state
    state: Union[InjectorState]

    def active(self) -> bool:
        return self.state == InjectorState.RUNNING

    def inactive(self) -> bool:
        return self.state in [InjectorState.STOPPED, InjectorState.NO_GRAB]


class Injector:
    """Manages the Injection for one Preset"""

    group: _Group
    preset: Preset
    context: Optional[Context]
    _devices: List[evdev.InputDevice]
    _state: InjectorState
    _stop_event: asyncio.Event
    _injector_task: Optional[asyncio.Task]  # the _run() task if the injector is running

    regrab_timeout = 0.2

    def __init__(self, group: _Group, preset: Preset) -> None:
        """

        Parameters
        ----------
        group
            the device group
        """
        self.group = group
        self.preset = preset

        self._devices = self.group.get_devices()
        self._stop_event = asyncio.Event()
        self._injector_task = None

        # InputConfigs may not contain the origin_hash information, this will try to
        # make a good guess if the origin_hash information is missing or invalid.
        self._update_preset()
        self.context = Context(self.preset)  # must be after _update_preset

        # the injector starts stopped
        self._state = InjectorState.STOPPED

    def get_state(self) -> InjectorState:
        """Get the state of the injection."""
        return self._state

    async def start_injecting(self) -> None:
        """Start the Injector.

        Schedules the Injector coroutine in the event loop"""
        setup_done = asyncio.Event()
        self._injector_task = asyncio.create_task(self._run(setup_done))
        await asyncio.wait(
            [setup_done.wait(), self._injector_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

    @ensure_numlock
    def stop_injecting(self) -> None:
        """Stop injecting."""
        logger.info(
            f"Stopping the injection of Preset {self.preset.name} "
            f"for group {self.group.key}"
        )
        self._stop_event.set()

    def _find_input_device(
        self, input_config: InputConfig
    ) -> Optional[evdev.InputDevice]:
        """find the InputDevice specified by the InputConfig

        ensures the devices supports the type and code specified by the InputConfig"""
        devices_by_hash = {get_device_hash(device): device for device in self._devices}

        # mypy thinks None is the wrong type for dict.get()
        if device := devices_by_hash.get(input_config.origin_hash):  # type: ignore
            if input_config.code in device.capabilities(absinfo=False).get(
                input_config.type, []
            ):
                return device
        return None

    def _find_input_device_fallback(
        self, input_config: InputConfig
    ) -> Optional[evdev.InputDevice]:
        """find the InputDevice specified by the InputConfig fallback logic"""
        ranking = [
            DeviceType.KEYBOARD,
            DeviceType.GAMEPAD,
            DeviceType.MOUSE,
            DeviceType.TOUCHPAD,
            DeviceType.GRAPHICS_TABLET,
            DeviceType.CAMERA,
            DeviceType.UNKNOWN,
        ]
        candidates: List[evdev.InputDevice] = [
            device
            for device in self._devices
            if input_config.code
            in device.capabilities(absinfo=False).get(input_config.type, [])
        ]

        if len(candidates) > 1:
            # there is more than on input device which can be used for this
            # event we choose only one determined by the ranking
            return sorted(candidates, key=lambda d: ranking.index(classify(d)))[0]
        if len(candidates) == 1:
            return candidates.pop()

        logger.error(f"Could not find input for {input_config}")
        return None

    def _grab_devices(self) -> GroupSources:
        # find all devices which have an associated mapping
        # use a dict because the InputDevice is not directly hashable
        needed_devices = {}
        input_configs = set()

        # find all unique input_config's
        for mapping in self.preset:
            for input_config in mapping.input_combination:
                input_configs.add(input_config)

        # find all unique input_device's
        for input_config in input_configs:
            if not (device := self._find_input_device(input_config)):
                # there is no point in trying the fallback because
                # self._update_preset already did that.
                continue
            needed_devices[device.path] = device

        grabbed_devices = []
        for device in needed_devices.values():
            if device := self._grab_device(device):
                grabbed_devices.append(device)
        return grabbed_devices

    def _update_preset(self):
        """Update all InputConfigs in the preset to include correct origin_hash
        information."""
        mappings_by_input = defaultdict(list)
        for mapping in self.preset:
            for input_config in mapping.input_combination:
                mappings_by_input[input_config].append(mapping)

        for input_config in mappings_by_input:
            if self._find_input_device(input_config):
                continue

            if not (device := self._find_input_device_fallback(input_config)):
                # fallback failed, this mapping will be ignored
                logger.debug(f"failed to find origin device for {input_config}")
                continue

            for mapping in mappings_by_input[input_config]:
                combination: List[InputConfig] = list(mapping.input_combination)
                device_hash = get_device_hash(device)
                idx = combination.index(input_config)
                combination[idx] = combination[idx].modify(origin_hash=device_hash)
                mapping.input_combination = combination

    def _grab_device(self, device: evdev.InputDevice) -> Optional[evdev.InputDevice]:
        """Try to grab the device, return None if not possible.

        Without grab, original events from it would reach the display server
        even though they are mapped.
        """
        error = None
        for attempt in range(10):
            try:
                device.grab()
                logger.debug("Grab %s", device.path)
                return device
            except IOError as err:
                # it might take a little time until the device is free if
                # it was previously grabbed.
                error = err
                logger.debug("Failed attempts to grab %s: %d", device.path, attempt + 1)
                time.sleep(self.regrab_timeout)

        logger.error("Cannot grab %s, it is possibly in use", device.path)
        logger.error(str(error))
        return None

    @staticmethod
    def _copy_capabilities(input_device: evdev.InputDevice) -> CapabilitiesDict:
        """Copy capabilities for a new device."""
        ecodes = evdev.ecodes

        # copy the capabilities because the uinput is going
        # to act like the device.
        capabilities = input_device.capabilities(absinfo=True)

        # just like what python-evdev does in from_device
        if ecodes.EV_SYN in capabilities:
            del capabilities[ecodes.EV_SYN]
        if ecodes.EV_FF in capabilities:
            del capabilities[ecodes.EV_FF]

        if ecodes.ABS_VOLUME in capabilities.get(ecodes.EV_ABS, []):
            # For some reason an ABS_VOLUME capability likes to appear
            # for some users. It prevents mice from moving around and
            # keyboards from writing symbols
            capabilities[ecodes.EV_ABS].remove(ecodes.ABS_VOLUME)

        return capabilities

    def _create_forwarding_device(self, source: evdev.InputDevice) -> evdev.UInput:
        # copy as much information as possible, because libinput uses the extra
        # information to enable certain features like "Disable touchpad while
        # typing"
        try:
            forward_to = evdev.UInput(
                name=get_udev_name(source.name, "forwarded"),
                events=self._copy_capabilities(source),
                # phys=source.phys,  # this leads to confusion. the appearance of
                # a uinput with this "phys" property causes the udev rule to
                # autoload for the original device, overwriting our previous
                # attempts at starting an injection.
                vendor=source.info.vendor,
                product=source.info.product,
                version=source.info.version,
                bustype=source.info.bustype,
                input_props=source.input_props(),
            )
        except TypeError as e:
            if "input_props" in str(e):
                # UInput constructor doesn't support input_props and
                # source.input_props doesn't exist with old python-evdev versions.
                logger.error("Please upgrade your python-evdev version. Exiting")
                self._state = InjectorState.UPGRADE_EVDEV
                sys.exit(12)

            raise e
        return forward_to

    async def _run(self, setup_done: asyncio.Event) -> None:
        """The injection worker that keeps injecting until stop_injecting is called."""
        logger.info('Starting injecting the preset for "%s"', self.group.key)

        # grab devices as early as possible. If events appear that won't get
        # released anymore before the grab they appear to be held down forever
        if len(sources := self._grab_devices()) == 0:
            logger.error("Did not grab any device")
            self._state = InjectorState.NO_GRAB
            return

        numlock_state = is_numlock_on()
        coroutines = []

        for source in sources:
            forward_to = self._create_forwarding_device(source)
            # actually doing things
            event_reader = EventReader(
                self.context,
                source,
                forward_to,
                self._stop_event,
            )
            coroutines.append(event_reader.run())

        # set the numlock state to what it was before injecting, because
        # grabbing devices screws this up
        set_numlock(numlock_state)

        try:
            self._state = InjectorState.RUNNING
            setup_done.set()
            await asyncio.gather(*coroutines)  # returns when stop_injecting is called
        except RuntimeError as error:
            # the loop might have been stopped via a `CLOSE` message,
            # which causes the error message below. This is expected behavior
            if str(error) != "Event loop stopped before Future completed.":
                self._state = InjectorState.FAILED
                raise error
        except OSError as error:
            logger.error("Failed to run injector coroutines: %s", str(error))
            self._state = InjectorState.FAILED
            return

        logger.debug("Injector coroutines ended")
        for source in sources:
            # ungrab at the end to make the next injection process not fail
            # its grabs
            try:
                source.ungrab()
            except OSError as error:
                # it might have disappeared
                logger.debug("OSError for ungrab on %s: %s", source.path, str(error))

        self._state = InjectorState.STOPPED
