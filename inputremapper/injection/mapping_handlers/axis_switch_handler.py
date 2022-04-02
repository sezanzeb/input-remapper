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
from typing import Dict, Tuple

import evdev

from inputremapper.logger import logger
from inputremapper.configs.mapping import Mapping
from inputremapper.event_combination import EventCombination
from inputremapper.injection.mapping_handlers.mapping_handler import (
    MappingHandler,
    ContextProtocol,
    HandlerEnums,
    InputEventHandler,
)
from inputremapper.input_event import InputEvent, EventActions


class AxisSwitchHandler(MappingHandler):
    """enables or disables an axis"""

    _map_axis: Tuple[int, int]  # the axis we switch on or off (type and code)
    _trigger_key: Tuple[Tuple[int, int]]  # all events that can switch the axis
    _active: bool  # whether the axis is on or off
    _last_value: int  # the value of the last axis event that arrived
    _axis_source: evdev.InputDevice  # the cashed source of the axis
    _forward_device: evdev.UInput  # the cashed forward uinput
    _sub_handler: InputEventHandler

    def __init__(
        self,
        combination: EventCombination,
        mapping: Mapping,
        context: ContextProtocol,
    ):
        super().__init__(combination, mapping, context)
        map_axis = [
            event.type_and_code for event in combination if not event.is_key_event
        ]
        trigger_keys = [
            event.type_and_code for event in combination if event.is_key_event
        ]
        assert len(map_axis) != 0
        assert len(trigger_keys) >= 1
        self._map_axis = map_axis[0]
        self._trigger_keys = tuple(trigger_keys)
        self._active = False

        self._last_value = 0
        self._axis_source = None
        self._forward_device = None

    def __str__(self):
        return f"AxisSwitchHandler for {self._map_axis} <{id(self)}>"

    def __repr__(self):
        return self.__str__()

    @property
    def child(self):
        return self._sub_handler

    def notify(
        self,
        event: InputEvent,
        source: evdev.InputDevice,
        forward: evdev.UInput,
        supress: bool = False,
    ) -> bool:

        if (
            event.type_and_code not in self._trigger_keys
            and event.type_and_code != self._map_axis
        ):
            return False

        if event.is_key_event:
            if self._active == bool(event.value):
                # nothing changed
                return False

            self._active = bool(event.value)
            if not self._active:
                # recenter the axis
                logger.debug_key(self.mapping.event_combination, "stopping axis")
                event = InputEvent(
                    0, 0, *self._map_axis, 0, action=EventActions.recenter
                )
                self._sub_handler.notify(event, self._axis_source, self._forward_device)
            elif self._map_axis[0] == evdev.ecodes.EV_ABS:
                # send the last cached value so that the abs axis
                # is at the correct position
                logger.debug_key(self.mapping.event_combination, "starting axis")
                event = InputEvent(0, 0, *self._map_axis, self._last_value)
                self._sub_handler.notify(event, self._axis_source, self._forward_device)
            else:
                logger.debug_key(self.mapping.event_combination, "starting axis")
            return True

        # do some caching so that we can generate the
        # recenter event and an initial abs event
        if not self._forward_device:
            self._forward_device = forward
            self._axis_source = source

        # always cache the value
        self._last_value = event.value

        if self._active:
            return self._sub_handler.notify(event, source, forward, supress)

        return False

    def needs_wrapping(self) -> bool:
        return True

    def wrap_with(self) -> Dict[EventCombination, HandlerEnums]:
        combination = [event for event in self.input_events if event.is_key_event]
        return {EventCombination(combination): HandlerEnums.combination}
