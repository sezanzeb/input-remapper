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

import evdev

from typing import Tuple, Dict

from inputremapper import exceptions
from inputremapper.logger import logger
from inputremapper.injection.global_uinputs import global_uinputs
from inputremapper.configs.system_mapping import system_mapping


class KeyHandler:
    """injects the target key if notified

    adheres to the CombinationSubHandler protocol
    """

    _target: str
    _maps_to: Tuple[int, int]
    _active: bool

    def __init__(self, config: Dict[str, any]):
        """initialize the handler

        Parameters
        ----------
        config : Dict = {
            "target": str
            "symbol": str
        }
        """
        super().__init__()
        self._target = config["target"]
        self._maps_to = (evdev.ecodes.EV_KEY, system_mapping.get(config["symbol"]))
        self._active = False

    def __str__(self):
        return f"KeyHandler <{id(self)}>:"

    def __repr__(self):
        return self.__str__()

    @property
    def child(self):  # used for logging
        return f"maps to: {self._maps_to} on {self._target}"

    async def notify(self, event: evdev.InputEvent) -> bool:
        """inject event.value to the target key"""

        event_tuple = (*self._maps_to, event.value)
        try:
            global_uinputs.write(event_tuple, self._target)
            logger.debug_key(event_tuple, "sending to %s", self._target)
            self._active = event.value == 1
            return True
        except exceptions.Error:
            return False

    @property
    def active(self) -> bool:
        return self._active
