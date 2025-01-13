# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2024 sezanzeb <b8x45ygc9@mozmail.com>
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

from typing import Dict, Union, Tuple, Optional, List, Type

import evdev

import inputremapper.exceptions
import inputremapper.utils
from inputremapper.logging.logger import logger

MIN_ABS = -(2**15)  # -32768
MAX_ABS = 2**15  # 32768
DEV_NAME = "input-remapper"
DEFAULT_UINPUTS = {
    # for event codes see linux/input-event-codes.h
    "keyboard": {
        evdev.ecodes.EV_KEY: list(evdev.ecodes.KEY.keys() & evdev.ecodes.keys.keys())
    },
    "gamepad": {
        evdev.ecodes.EV_KEY: [*range(0x130, 0x13F)],  # BTN_SOUTH - BTN_THUMBR
        evdev.ecodes.EV_ABS: [
            *(
                (i, evdev.AbsInfo(0, MIN_ABS, MAX_ABS, 0, 0, 0))
                for i in range(0x00, 0x06)
            ),
            *((i, evdev.AbsInfo(0, -1, 1, 0, 0, 0)) for i in range(0x10, 0x12)),
        ],  # 6-axis and 1 hat switch
    },
     "gamepad-2": {
        evdev.ecodes.EV_KEY: [*range(0x130, 0x13F)],  # BTN_SOUTH - BTN_THUMBR
        evdev.ecodes.EV_ABS: [
            *(
                (i, evdev.AbsInfo(0, MIN_ABS, MAX_ABS, 0, 0, 0))
                for i in range(0x00, 0x06)
            ),
            *((i, evdev.AbsInfo(0, -1, 1, 0, 0, 0)) for i in range(0x10, 0x12)),
        ],  # 6-axis and 1 hat switch
    },
    "mouse": {
        evdev.ecodes.EV_KEY: [*range(0x110, 0x118)],  # BTN_LEFT - BTN_TASK
        evdev.ecodes.EV_REL: [*range(0x00, 0x0D)],  # all REL axis
    },
}
DEFAULT_UINPUTS["keyboard + mouse"] = {
    evdev.ecodes.EV_KEY: [
        *DEFAULT_UINPUTS["keyboard"][evdev.ecodes.EV_KEY],
        *DEFAULT_UINPUTS["mouse"][evdev.ecodes.EV_KEY],
    ],
    evdev.ecodes.EV_REL: [
        *DEFAULT_UINPUTS["mouse"][evdev.ecodes.EV_REL],
    ],
}


class UInput(evdev.UInput):
    _capabilities_cache: Optional[Dict] = None

    def __init__(self, *args, **kwargs):
        name = kwargs["name"]
        logger.debug('creating UInput device: "%s"', name)
        super().__init__(*args, **kwargs)

    def can_emit(self, event: Tuple[int, int, int]):
        """Check if an event can be emitted by the UIinput.

        Wrong events might be injected if the group mappings are wrong,
        """
        # this will never change, so we cache it since evdev runs an expensive loop to
        # gather the capabilities. (can_emit is called regularly)
        if self._capabilities_cache is None:
            self._capabilities_cache = self.capabilities(absinfo=False)

        return event[1] in self._capabilities_cache.get(event[0], [])


class FrontendUInput:
    """Uinput which can not actually send events, for use in the frontend."""

    def __init__(self, *_, events=None, name="py-evdev-uinput", **__):
        # see https://python-evdev.readthedocs.io/en/latest/apidoc.html#module-evdev.uinput  # noqa pylint: disable=line-too-long
        self.events = events
        self.name = name

        logger.debug('creating fake UInput device: "%s"', self.name)

    def capabilities(self):
        return self.events


class GlobalUInputs:
    """Manages all UInputs that are shared between all injection processes."""

    def __init__(
        self,
        uinput_factory: Union[Type[UInput], Type[FrontendUInput]],
    ):
        self.devices: Dict[str, Union[UInput, FrontendUInput]] = {}
        self._uinput_factory = uinput_factory

    def __iter__(self):
        return iter(uinput for _, uinput in self.devices.items())

    @staticmethod
    def can_default_uinput_emit(target: str, type_: int, code: int) -> bool:
        """Check if the uinput with the target name is capable of the event."""
        capabilities = DEFAULT_UINPUTS.get(target, {}).get(type_)
        return capabilities is not None and code in capabilities

    @staticmethod
    def find_fitting_default_uinputs(type_: int, code: int) -> List[str]:
        """Find the names of default uinputs that are able to emit this event."""
        return [
            uinput
            for uinput in DEFAULT_UINPUTS
            if code in DEFAULT_UINPUTS[uinput].get(type_, [])
        ]

    def reset(self):
        self.devices = {}
        self.prepare_all()

    def prepare_all(self):
        """Generate UInputs."""
        for name, events in DEFAULT_UINPUTS.items():
            if name in self.devices.keys():
                continue

            self.devices[name] = self._uinput_factory(
                name=f"{DEV_NAME} {name}",
                phys=DEV_NAME,
                events=events,
            )

    def prepare_single(self, name: str):
        """Generate a single uinput.

        This has to be done in the main process before injections that use it start.
        """
        if name not in DEFAULT_UINPUTS:
            raise KeyError("Could not find a matching uinput to generate.")

        if name in self.devices:
            logger.debug('Target "%s" already exists', name)
            return

        self.devices[name] = self._uinput_factory(
            name=f"{DEV_NAME} {name}",
            phys=DEV_NAME,
            events=DEFAULT_UINPUTS[name],
        )

    def write(self, event: Tuple[int, int, int], target_uinput):
        """Write event to target uinput."""
        uinput = self.get_uinput(target_uinput)
        if not uinput:
            raise inputremapper.exceptions.UinputNotAvailable(target_uinput)

        if not uinput.can_emit(event):
            raise inputremapper.exceptions.EventNotHandled(event)

        logger.write(event, uinput)
        uinput.write(*event)
        uinput.syn()

    def get_uinput(self, name: str) -> Optional[evdev.UInput]:
        """UInput with name

        Or None if there is no uinput with this name.

        Parameters
        ----------
        name
            uniqe name of the uinput device
        """
        if name not in self.devices:
            logger.error(
                f'UInput "{name}" is unknown. '
                + f"Available: {list(self.devices.keys())}"
            )
            return None

        return self.devices.get(name)
