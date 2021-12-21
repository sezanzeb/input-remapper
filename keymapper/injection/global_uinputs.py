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
from evdev.ecodes import EV_KEY

from keymapper.logger import logger

DEV_NAME = "key-mapper"


class UInput(evdev.UInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def can_emit(self, event):
        """ceck it a event can be emitted by the uinput

        Wrong events might be injected if the group mappings are wrong
        """
        # TODO check for event value especially for EV_ABS
        return event[1] in self.capabilities().get(event[0], [])


class FrontendUInput:
    """Uinput which can not actually send events, for use in the frontend"""
    def __init__(self, *args, **kwargs):
        defaults = { # see https://python-evdev.readthedocs.io/en/latest/apidoc.html#module-evdev.uinput
            "events": None,
            "name": 'py-evdev-uinput',
            #"vendor": 1,
            #"product": 1,
            #"version": 1,
            #"bustype": 3,
            #"devnode": '/dev/uinput',
            #"phys": 'py-evdev-uinput',
            }
        for key, value in defaults.items():
            try:
                setattr(self, key, kwargs[key])
            except KeyError:
                setattr(self, key, value)
    
    def capabilities(self):
        return self.events
        

class GlobalUInputs:
    """Manages all uinputs that are shared between all injection processes."""

    def __init__(self, backend = True):
        self.devices = {}
        if backend:
            self._uinput_factory = UInput
        else:
            self._uinput_factory = FrontendUInput
        
    def prepare(self):
        """Generate uinputs.

        This has to be done in the main process before injections start.
        """
        # Using all EV_KEY codes broke it in one installation, the use case for
        # keyboard_output (see docstring of Context) only requires KEY_* codes here
        # anyway and no BTN_* code.
        # Furthermore, python-evdev modifies the ecodes.keys list to make it usable,
        # only use KEY_* codes that are in ecodes.keys therefore.
        keys = list(evdev.ecodes.KEY.keys() & evdev.ecodes.keys.keys())
        self.devices["keyboard"] = self._uinput_factory(
            name="key-mapper keyboard",
            phys=DEV_NAME,
            events={evdev.ecodes.EV_KEY: keys},
        )

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
