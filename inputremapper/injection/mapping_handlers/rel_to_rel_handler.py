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
from typing import Dict, Tuple, Optional

import evdev
from evdev.ecodes import (
    EV_REL,
    REL_WHEEL,
    REL_HWHEEL,
)

from inputremapper import exceptions
from inputremapper.configs.mapping import Mapping
from inputremapper.event_combination import EventCombination
from inputremapper.injection.global_uinputs import global_uinputs
from inputremapper.injection.mapping_handlers.axis_transform import Transformation
from inputremapper.injection.mapping_handlers.mapping_handler import (
    MappingHandler,
    HandlerEnums,
    InputEventHandler,
)
from inputremapper.input_event import InputEvent
from inputremapper.logger import logger


def is_wheel(event) -> bool:
    return event.type == EV_REL and event.code in (REL_WHEEL, REL_HWHEEL)


# TODO
"""
00:16:22.695476 35088 Service ERROR preset.py:308: failed to Validate mapping for 2,0,1: 1 validation error for Mapping
__root__
  missing macro or key: the combination = <EventCombination (2, 0, 1)> specifies a key input, but no output macro or key is programmed (type=value_error)
  
  
00:18:34.576837 35275 Service ERROR preset.py:308: failed to Validate mapping for 2,0,1: 2 validation errors for Mapping
__root__
  missing Argument: Mapping must either contain `output_symbol` or `output_type` and `output_code` (type=value_error)
__root__
  missing macro or key: the combination = <EventCombination (2, 0, 1)> specifies a key input, but no output macro or key is programmed (type=value_error)
"""

# TODO after "The device was not grabbed" message, reset the "Stop" button


# TODO
"""
│   571 │   │   def show_result(msg: InjectorState):                                               │
│   572 │   │   │   self.message_broker.unsubscribe(show_result)                                   │
│ ❱ 573 │   │   │   assert msg.state == STOPPED
if this fails, then fix the inconsistency instead of crashing
"""

# TODO test


# TODO high-res wheel as input
# TODO high-res wheel as output


class RelToRelHandler(MappingHandler):
    """Handler which transforms EV_REL to EV_REL events"""

    _input_movement: Tuple[int, int]  # (type, code) of the relative movement we map
    _output_axis: Tuple[int, int]  # the (type, code) of the output axis
    _transform: Transformation
    _is_wheel_input: bool

    # infinite loop which centers the output when input stops
    _recenter_loop: Optional[asyncio.Task]
    _moving: asyncio.Event  # event to notify the _recenter_loop

    _remainder: float

    def __init__(
        self,
        combination: EventCombination,
        mapping: Mapping,
        **_,
    ) -> None:
        super().__init__(combination, mapping)

        self._remainder = 0

        self._transform = Transformation(
            max_=256,
            min_=-256,
            deadzone=self.mapping.deadzone,
            gain=self.mapping.gain,
            expo=self.mapping.expo,
        )

        self._is_wheel_input = False

        # TODO duplicate code
        # find the input event we are supposed to map. If the input combination is
        # BTN_A + REL_X + BTN_B, then use the value of REL_X for the transformation
        for event in combination:
            # TODO search for "Use as Analog"?
            if event.value == 0:
                assert event.type == EV_REL
                self._input_movement = event.type_and_code

                if is_wheel(event):
                    self._is_wheel_input = True

                break

    def __str__(self):
        return f"RelToRelHandler for {self._input_movement} <{id(self)}>:"

    def __repr__(self):
        return self.__str__()

    @property
    def child(self):  # used for logging
        return f"maps to: {self.mapping.output_code} at {self.mapping.target_uinput}"

    def _should_map(self, event):
        """Check if this input event is relevant for this handler."""
        if self._is_wheel_input and is_wheel(event):
            return True

        if event.type_and_code == self._input_movement:
            return True

        return False

    def notify(
        self,
        event: InputEvent,
        source: evdev.InputDevice,
        forward: evdev.UInput = None,
        supress: bool = False,
    ) -> bool:
        if not self._should_map(event):
            return False

        try:
            self._write(self._transform(event.value))
            return True
        except (exceptions.UinputNotAvailable, exceptions.EventNotHandled):
            return False

    def reset(self) -> None:
        pass

    def _write(self, value: float) -> None:
        """Inject."""
        is_wheel_output = self.mapping.output_code in (
            REL_WHEEL,
            REL_HWHEEL,
        )

        # value is between 0 and 1, scale up
        if is_wheel_output or self._is_wheel_input:
            scaled = value * self.mapping.rel_wheel_speed
        else:
            scaled = value * self.mapping.rel_xy_speed

        # if the mouse moves very slow, it might not move at all because of the
        # int-conversion (which is required when writing). store the remainder
        # (the decimal places) and add it up, until the mouse moves a little.
        floored = int(scaled)
        self._remainder += scaled - floored
        if abs(self._remainder) >= 1:
            output_value = int(scaled + self._remainder)
            self._remainder = scaled - output_value
        else:
            output_value = floored

        if output_value == 0:
            return

        try:
            global_uinputs.write(
                (EV_REL, self.mapping.output_code, output_value),
                self.mapping.target_uinput,
            )
        except OverflowError:
            # screwed up the calculation of the event value
            logger.error("OverflowError (%s, %s, %s)", *self._output_axis, value)

    def needs_wrapping(self) -> bool:
        return len(self.input_events) > 1

    def set_sub_handler(self, handler: InputEventHandler) -> None:
        assert False  # cannot have a sub-handler

    def wrap_with(self) -> Dict[EventCombination, HandlerEnums]:
        if self.needs_wrapping():
            return {EventCombination(self.input_events): HandlerEnums.axisswitch}
        return {}
