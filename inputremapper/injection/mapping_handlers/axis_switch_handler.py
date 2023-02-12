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

from typing import Dict, Tuple, Hashable, TYPE_CHECKING

import evdev
from inputremapper.configs.input_config import InputConfig

from inputremapper.configs.input_config import InputCombination
from inputremapper.configs.mapping import Mapping
from inputremapper.injection.mapping_handlers.mapping_handler import (
    MappingHandler,
    HandlerEnums,
    InputEventHandler,
    ContextProtocol,
)
from inputremapper.input_event import InputEvent, EventActions
from inputremapper.logger import logger
from inputremapper.utils import get_device_hash


class AxisSwitchHandler(MappingHandler):
    """Enables or disables an axis.

    Generally, if multiple events are mapped to something in a combination, all of
    them need to be triggered in order to map to the output.

    If an analog input is combined with a key input, then the same thing should happen.
    The key needs to be pressed and the joystick needs to be moved in order to generate
    output.
    """

    _map_axis: InputConfig  # the InputConfig for the axis we switch on or off
    _trigger_keys: Tuple[Hashable, ...]  # all events that can switch the axis
    _active: bool  # whether the axis is on or off
    _last_value: int  # the value of the last axis event that arrived
    _axis_source: evdev.InputDevice  # the cached source of the axis input events
    _forward_device: evdev.UInput  # the cached forward uinput
    _sub_handler: InputEventHandler

    def __init__(
        self,
        combination: InputCombination,
        mapping: Mapping,
        context: ContextProtocol,
        **_,
    ):
        super().__init__(combination, mapping)
        trigger_keys = tuple(
            event.input_match_hash
            for event in combination
            if not event.defines_analog_input
        )
        assert len(trigger_keys) >= 1
        assert (map_axis := combination.find_analog_input_config())
        self._map_axis = map_axis
        self._trigger_keys = trigger_keys
        self._active = False

        self._last_value = 0
        self._axis_source = None
        self._forward_device = None

        self.context = context

    def __str__(self):
        return f"AxisSwitchHandler for {self._map_axis.type_and_code}"

    def __repr__(self):
        return f"<{str(self)} at {hex(id(self))}>"

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
            logger.debug("Stopping axis for %s", self.mapping.input_combination)
            event = InputEvent(
                0,
                0,
                *self._map_axis.type_and_code,
                0,
                actions=(EventActions.recenter,),
                origin_hash=self._map_axis.origin_hash,
            )
            self._sub_handler.notify(event, self._axis_source)
            return True

        if self._map_axis.type == evdev.ecodes.EV_ABS:
            # send the last cached value so that the abs axis
            # is at the correct position
            logger.debug("Starting axis for %s", self.mapping.input_combination)
            event = InputEvent(
                0,
                0,
                *self._map_axis.type_and_code,
                self._last_value,
                origin_hash=self._map_axis.origin_hash,
            )
            self._sub_handler.notify(event, self._axis_source)
            return True

        return True

    def _should_map(self, event: InputEvent):
        return (
            event.input_match_hash in self._trigger_keys
            or event.input_match_hash == self._map_axis.input_match_hash
        )

    def notify(
        self,
        event: InputEvent,
        source: evdev.InputDevice,
        suppress: bool = False,
    ) -> bool:
        if not self._should_map(event):
            return False

        if event.is_key_event:
            return self._handle_key_input(event)

        # do some caching so that we can generate the
        # recenter event and an initial abs event
        if self._axis_source is None:
            self._axis_source = source

        if self._forward_device is None:
            device_hash = get_device_hash(source)
            self._forward_device = self.context.get_forward_uinput(device_hash)

        # always cache the value
        self._last_value = event.value

        if self._active:
            return self._sub_handler.notify(event, source, suppress)

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
