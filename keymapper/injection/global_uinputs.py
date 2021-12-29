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


import evdev
import keymapper.utils
import keymapper.exceptions
from keymapper.logger import logger

DEV_NAME = "key-mapper"
DEFAULT_UINPUTS = {
    # for event codes see linux/input-event-codes.h
    "keyboard": {
        evdev.ecodes.EV_KEY: list(evdev.ecodes.KEY.keys() & evdev.ecodes.keys.keys())
    },
    "gamepad": {
        evdev.ecodes.EV_KEY: [*range(0x130, 0x13f)],  # BTN_SOUTH - BTN_THUMBR
        evdev.ecodes.EV_ABS: [*range(0x00, 0x06), *range(0x10, 0x12)]  # 6-axis and 1 hat switch
    },
    "mouse": {
        evdev.ecodes.EV_KEY: [*range(0x110, 0x118)],  # BTN_LEFT - BTN_TASK
        evdev.ecodes.EV_REL: [*range(0x00, 0x0a)]  # all REL axis
    }
}


class UInput(evdev.UInput):
    def __init__(self, *args, **kwargs):
        logger.debug(f"creating UInput device: '{kwargs['name']}'")
        super().__init__(*args, **kwargs)

    def can_emit(self, event):
        """check if an event can be emitted by the uinput

        Wrong events might be injected if the group mappings are wrong
        """
        # TODO check for event value especially for EV_ABS
        return event[1] in self.capabilities().get(event[0], [])


class FrontendUInput:
    """Uinput which can not actually send events, for use in the frontend"""
    def __init__(self, *args, **kwargs):
        defaults = {  # see https://python-evdev.readthedocs.io/en/latest/apidoc.html#module-evdev.uinput
            "events": None,
            "name": 'py-evdev-uinput',
            #"vendor": 1,
            #"product": 1,
            #"version": 1,
            #"bustype": 3,
            #"devnode": '/dev/uinput',
            #"phys": 'py-evdev-uinput',
            }
        logger.debug(f"creating fake UInput device: '{kwargs['name']}'")
        for key, value in defaults.items():
            try:
                setattr(self, key, kwargs[key])
            except KeyError:
                setattr(self, key, value)
    
    def capabilities(self):
        return self.events


class GlobalUInputs:
    """Manages all uinputs that are shared between all injection processes."""

    def __init__(self):
        self.devices = {}

        if keymapper.utils.is_service():
            self._uinput_factory = UInput
        else:
            self._uinput_factory = FrontendUInput

    def prepare(self, force_service=False):
        """Generate uinputs.

        This has to be done in the main process before injections start.
        """

        # TODO: remove force_service we should find a way to patch keymapper.utils.is_service() in the tests
        if force_service:
            self._uinput_factory = UInput

        for name, events in DEFAULT_UINPUTS.items():
            if name in self.devices.keys():
                continue
            self.devices[name] = self._uinput_factory(
                name=f"{DEV_NAME} {name}",
                phys=DEV_NAME,
                events=events,
            )

    def write(self, event, target_uinput):
        """write event to target uinput"""
        uinput = self.get_uinput(target_uinput)
        if not uinput:
            raise keymapper.exceptions.UinputNotAvailable(target_uinput)

        if not uinput.can_emit(event):
            raise keymapper.exceptions.EventNotHandled(event)

        uinput.write(*event)
        uinput.syn()

    def get_uinput(self, name):
        """UInput with name

        Or None if there is no uinput with this name.

        Parameters
        ----------
        name : uniqe name of the uinput device
        """
        if name in self.devices.keys():
            return self.devices[name]

        return None


global_uinputs = GlobalUInputs()
