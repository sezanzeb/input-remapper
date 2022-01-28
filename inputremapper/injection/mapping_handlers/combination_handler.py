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

from typing import Protocol, Dict, Tuple

from inputremapper import utils
from inputremapper.event_combination import EventCombination
from inputremapper.logger import logger
from inputremapper.input_event import InputEvent
from inputremapper.injection.macros.parse import is_this_a_macro
from inputremapper.injection.mapping_handlers.mapping_handler import ContextProtocol
from inputremapper.injection.mapping_handlers.key_handler import KeyHandler
from inputremapper.injection.mapping_handlers.macro_handler import MacroHandler


class CombinationSubHandler(Protocol):
    """Protocol any handler which can be triggered by a combination must implement"""

    @property
    def active(self) -> bool:
        ...

    async def notify(self, event: evdev.InputEvent) -> bool:
        ...


class CombinationHandler:
    """keeps track of a combination and notifies a sub handler

    adheres to the MappingHandler protocol
    """

    _combination: EventCombination
    _key_map: Dict[Tuple[int, int], bool]
    _sub_handler: CombinationSubHandler

    def __init__(self, config: Dict[str, any], context: ContextProtocol) -> None:
        """initialize the handler

        Parameters
        ----------
        config : Dict = {
            "combination": str
            "target": str
            "symbol": str
        }
        context : Context
        """
        super().__init__()
        self._combination = EventCombination.from_string(config["combination"])
        self._key_map = {}
        for event in self._combination:  # prepare key_map
            self._key_map[event.type_and_code] = False

        if is_this_a_macro(config["symbol"]):
            self._sub_handler = MacroHandler(config, context)
        else:
            self._sub_handler = KeyHandler(config)

    def __str__(self):
        return f"CombinationHandler for {self._combination} <{id(self)}>:"

    def __repr__(self):
        return self.__str__()

    @property
    def child(self):  # used for logging
        return self._sub_handler

    async def notify(
        self,
        event: InputEvent,
        source: evdev.InputDevice = None,
        forward: evdev.UInput = None,
        supress: bool = False,
    ) -> bool:

        map_key = event.type_and_code
        if map_key not in self._key_map.keys():
            return False  # we are not responsible for the event

        self._key_map[map_key] = event.value == 1
        if self.get_active() == self._sub_handler.active:
            return False  # nothing changed ignore this event

        if self.get_active() and not utils.is_key_up(event.value) and forward:
            self.forward_release(forward)

        if supress:
            return False

        is_key_down = self.get_active() and not utils.is_key_up(event.value)
        if is_key_down:
            value = 1
        else:
            value = 0

        event = event.modify(value=value)
        logger.debug_key(self._combination, "triggered: sending to sub-handler")
        return await self._sub_handler.notify(event)

    def get_active(self) -> bool:
        """return if all keys in the keymap are set to True"""
        return False not in self._key_map.values()

    def forward_release(self, forward: evdev.UInput) -> None:
        """forward a button release for all keys if this is a combination

        this might cause duplicate key-up events but those are ignored by evdev anyway
        """
        if len(self._combination) == 1:
            return
        for event in self._combination:
            forward.write(*event.type_and_code, 0)
        forward.syn()
