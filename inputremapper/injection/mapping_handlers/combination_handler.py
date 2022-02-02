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
import asyncio

import evdev

from typing import Dict, Tuple, Optional, List
from evdev.ecodes import EV_ABS, EV_REL, EV_KEY

from inputremapper.configs.mapping import Mapping
from inputremapper.input_event import InputEvent, EventActions
from inputremapper.event_combination import EventCombination
from inputremapper.logger import logger
from inputremapper.injection.mapping_handlers.mapping_handler import ContextProtocol, MappingHandler, InputEventHandler, \
    HandlerEnums


class CombinationHandler(MappingHandler):
    """keeps track of a combination and notifies a sub handler"""

    # map of (event.type, event.code) -> bool , keep track of the combination state
    _key_map: Dict[Tuple[int, int], bool]
    _last_active_state: bool  # overall state of the combination after last event

    # if we forward axis events contains the event.type and event.code
    _map_axis: Optional[Tuple[int, int]]

    def __init__(self, combination: EventCombination, mapping: Mapping, context: ContextProtocol) -> None:
        super().__init__(combination, mapping, context)
        self._key_map = {}
        self._map_axis = None
        self._last_active_state = False

        # prepare a key map for all events with non-zero value
        for event in combination:
            if event.value != 0:
                self._key_map[event.type_and_code] = False
            else:
                assert self._map_axis is None  # we can not map multiple axis
                self._map_axis = event.type_and_code

        assert len(self._key_map) > 0  # no combination handler without a key

    def __str__(self):
        return f"CombinationHandler for {self.mapping.event_combination} <{id(self)}>:"

    def __repr__(self):
        return self.__str__()

    @property
    def child(self):  # used for logging
        return self._sub_handler

    async def notify(
        self,
        event: InputEvent,
        source: evdev.InputDevice,
        forward: evdev.UInput,
        supress: bool = False,
    ) -> bool:
        type_code = event.type_and_code

        if type_code not in self._key_map.keys() and (
                not self._map_axis or type_code != self._map_axis):
            return False  # we are not responsible for the event

        # check if the event belongs to the axis we and is not interpreted as key
        if self._map_axis and type_code == self._map_axis and not event.action == EventActions.as_key:
            if self._last_active_state:
                # combination is active, and this is the axis we should pass though the event pipe
                return await self._sub_handler.notify(event, source, forward, supress)
            else:
                # combination is not active, send the event back
                return False

        self._key_map[type_code] = event.value == 1
        if self.get_active() == self._last_active_state:
            # nothing changed ignore this event
            return False

        if self.get_active() and event.value == 1:
            # send key up events to the forwarded uinput
            self.forward_release(forward)

        if supress:
            return False

        if self.get_active() and event.value == 1:
            event = event.modify(value=1)
            self._last_active_state = True
        else:
            event = event.modify(value=0)
            self._last_active_state = False

        if self._map_axis and event.value == 0:
            logger.debug_key(self.mapping.event_combination, "deactivated")
            event = InputEvent(0, 0, *self._map_axis, 0, action=EventActions.recenter)
            asyncio.ensure_future(self._sub_handler.notify(event, source, forward, supress))
            return True  # don't pass through if we map to an axis
        elif self._map_axis:
            logger.debug_key(self.mapping.event_combination, "activated")
            return True

        logger.debug_key(self.mapping.event_combination, "triggered: sending to sub-handler")
        return await self._sub_handler.notify(event, source, forward, supress)

    def get_active(self) -> bool:
        """return if all keys in the keymap are set to True"""
        return False not in self._key_map.values()

    def forward_release(self, forward: evdev.UInput) -> None:
        """forward a button release for all keys if this is a combination

        this might cause duplicate key-up events but those are ignored by evdev anyway
        """
        if len(self.mapping.event_combination) == 1:
            return
        for event in self.mapping.event_combination:
            forward.write(*event.type_and_code, 0)
        forward.syn()

    def needs_ranking(self) -> bool:
        return True

    def rank_by(self) -> Optional[EventCombination]:
        return EventCombination(event for event in self.input_events if event.value != 0)

    def wrap_with(self) -> Dict[EventCombination, HandlerEnums]:
        return_dict = {}
        for event in self.input_events:
            if event.type == EV_ABS and event.value != 0:
                return_dict[EventCombination(event)] = HandlerEnums.abs2btn

            if event.type == EV_REL and event.value != 0:
                return_dict[EventCombination(event)] = HandlerEnums.rel2btn

            if event.type == EV_KEY and event.value == 0:
                if self.mapping.output_type == EV_ABS:
                    return_dict[EventCombination(event)] = HandlerEnums.btn2abs
                elif self.mapping.output_type == EV_REL:
                    return_dict[EventCombination(event)] = HandlerEnums.btn2rel

        return return_dict
