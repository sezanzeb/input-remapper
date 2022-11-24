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
from evdev.ecodes import EV_KEY

from inputremapper.configs.mapping import Mapping
from inputremapper.input_configuration import InputCombination
from inputremapper.injection.mapping_handlers.mapping_handler import (
    MappingHandler,
    HandlerEnums,
    InputEventHandler,
)
from inputremapper.input_event import InputEvent, EventActions
from inputremapper.logger import logger


class AxisSwitchHandler(MappingHandler):
    """Enables or disables an axis.

    Generally, if multiple events are mapped to something in a combination, all of
    them need to be triggered in order to map to the output.

    If an analog input is combined with a key input, then the same thing should happen.
    The key needs to be pressed and the joystick needs to be moved in order to generate
    output.
    """

    _map_axis: Tuple[int, int]  # the axis we switch on or off (type and code)
    _trigger_key: Tuple[Tuple[int, int]]  # all events that can switch the axis
    _active: bool  # whether the axis is on or off
    _last_value: int  # the value of the last axis event that arrived
    _axis_source: evdev.InputDevice  # the cached source of the axis input events
    _forward_device: evdev.UInput  # the cached forward uinput
    _sub_handler: InputEventHandler

    def __init__(
        self,
        combination: InputCombination,
        mapping: Mapping,
        **_,
    ):
        super().__init__(combination, mapping)
        trigger_keys = [
            event.type_and_code
            for event in combination
            if not event.defines_analog_input
        ]
        assert len(trigger_keys) >= 1
        assert (map_axis := mapping.find_analog_input_event())
        self._map_axis = map_axis.type_and_code
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

    def _handle_key_input(self, event: InputEvent):
        """If a key is pressed, allow mapping analog events in subhandlers.

        Analog events (e.g. ABS_X, REL_Y) that have gone through Handlers that
        transform them to buttons also count as keys.
        """
        key_is_pressed = bool(event.value)
        if self._active == key_is_pressed:
            # nothing changed
            return False

        self._active = key_is_pressed

        if self._axis_source is None:
            return True

        if not key_is_pressed:
            # recenter the axis
            logger.debug_key(self.mapping.event_combination, "stopping axis")
            event = InputEvent(
                0,
                0,
                *self._map_axis,
                0,
                actions=(EventActions.recenter,),
            )
            self._sub_handler.notify(event, self._axis_source, self._forward_device)
            return True

        if self._map_axis[0] == evdev.ecodes.EV_ABS:
            # send the last cached value so that the abs axis
            # is at the correct position
            logger.debug_key(self.mapping.event_combination, "starting axis")
            event = InputEvent(
                0,
                0,
                *self._map_axis,
                self._last_value,
            )
            self._sub_handler.notify(event, self._axis_source, self._forward_device)
            return True

        return True

    def _should_map(self, event: InputEvent):
        return (
            event.type_and_code in self._trigger_keys
            or event.type_and_code == self._map_axis
        )

    def notify(
        self,
        event: InputEvent,
        source: evdev.InputDevice,
        forward: evdev.UInput,
        suppress: bool = False,
    ) -> bool:

        if not self._should_map(event):
            return False

        if event.is_key_event:
            return self._handle_key_input(event)

        # do some caching so that we can generate the
        # recenter event and an initial abs event
        if not self._forward_device:
            self._forward_device = forward
            self._axis_source = source

        # always cache the value
        self._last_value = event.value

        if self._active:
            return self._sub_handler.notify(event, source, forward, suppress)

        return False

    def reset(self) -> None:
        self._last_value = 0
        self._active = False
        self._sub_handler.reset()

    def needs_wrapping(self) -> bool:
        return True

    def wrap_with(self) -> Dict[InputCombination, HandlerEnums]:
        combination = [
            config for config in self.input_configs if not config.defines_analog_input
        ]
        return {InputCombination(combination): HandlerEnums.combination}
