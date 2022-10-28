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
import math
from typing import Dict, Optional

import evdev
from evdev.ecodes import (
    EV_REL,
    REL_WHEEL,
    REL_HWHEEL,
    REL_WHEEL_HI_RES,
    REL_HWHEEL_HI_RES,
)

from inputremapper import exceptions
from inputremapper.configs.mapping import Mapping, WHEEL_SCALING, WHEEL_HI_RES_SCALING
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


def is_high_res_wheel(event) -> bool:
    return event.type == EV_REL and event.code in (REL_WHEEL_HI_RES, REL_HWHEEL_HI_RES)


class Remainder:
    _scale: int
    _remainder: float

    def __init__(self, scale):
        self._scale = scale
        self._remainder = 0

    def input(self, value):
        # if the mouse moves very slow, it might not move at all because of the
        # int-conversion (which is required when writing). store the remainder
        # (the decimal places) and add it up, until the mouse moves a little.
        scaled = value * self._scale + self._remainder
        self._remainder = math.fmod(scaled, 1)

        return int(scaled)


class RelToRelHandler(MappingHandler):
    """Handler which transforms EV_REL to EV_REL events."""

    _input_event: InputEvent  # the relative movement we map

    _max_observed_input: int

    _transform: Transformation

    # infinite loop which centers the output when input stops
    _recenter_loop: Optional[asyncio.Task]
    _moving: asyncio.Event  # event to notify the _recenter_loop

    _remainder: Remainder
    _wheel_remainder: Remainder
    _wheel_hi_res_remainder: Remainder

    def __init__(
        self,
        combination: EventCombination,
        mapping: Mapping,
        **_,
    ) -> None:
        super().__init__(combination, mapping)

        self._max_observed_input = 0

        # find the input event we are supposed to map. If the input combination is
        # BTN_A + REL_X + BTN_B, then use the value of REL_X for the transformation
        input_event = mapping.find_analog_input_event(type_=EV_REL)
        assert input_event is not None
        self._input_event = input_event

        self._remainder = Remainder(1)
        self._wheel_remainder = Remainder(1 / WHEEL_SCALING)
        self._wheel_hi_res_remainder = Remainder(1 / WHEEL_SCALING * WHEEL_HI_RES_SCALING)

        self._transform = Transformation(
            max_=1,
            min_=-1,
            deadzone=self.mapping.deadzone,
            gain=self.mapping.gain,
            expo=self.mapping.expo,
        )

    def __str__(self):
        return f"RelToRelHandler for {self._input_event} <{id(self)}>:"

    def __repr__(self):
        return self.__str__()

    @property
    def child(self):  # used for logging
        return f"maps to: {self.mapping.output_code} at {self.mapping.target_uinput}"

    def _should_map(self, event):
        """Check if this input event is relevant for this handler."""
        if event.type_and_code == (self._input_event.type, self._input_event.code):
            return True

        return False

    def notify(
        self,
        event: InputEvent,
        source: evdev.InputDevice,
        forward: evdev.UInput = None,
        suppress: bool = False,
    ) -> bool:
        if not self._should_map(event):
            return False
        """
        rel2rel example:
        - input every 0.1s (`input_rate` of 10 events/s), value of 200
        - input speed is 2000, because in 1 second a value of 2000 acumulates
        - `input_rel_speed` is a const defined as 4000 px/s, how fast mice usually move
        - `transformed = Transformation(input.value, max=input_rel_speed / input_rate)`
        - get 0.5 because the expo is 0
        - `abs_to_rel_speed` is 5000
        - inject 2500 therefore per second, making it a bit faster
        - divide 2500 by the rate of 10 to inject a value of 250 each time input occurs

        ```
        output_value = Transformation(
            input.value,
            max=input_rel_speed / input_rate
        ) * abs_to_rel_speed / input_rate
        ```

        The input_rel_speed could be used here instead of abs_to_rel_speed, because the gain
        already controls the speed. In that case it would be a 1:1 ratio of
        input-to-output value if the gain is 1.

        for wheel and wheel_hi_res, different input speed constants must be set.

        abs2rel needs a base value for the output, so `abs_to_rel_speed` is still required.
        `abs_to_rel_speed / rel_rate * transform(input.value, max=absinfo.max)` is the output
        value. Both abs_to_rel_speed and the transformation-gain control speed.

        if abs_to_rel_speed controls speed in the abs2rel output, it should also do so in other
        handlers that have EV_REL output.
        
        unfortunately input_rate needs to be determined during runtime, which screws
        the overall speed up when slowly moving the input device in the beginning,
        because slow input is thought to be the regular input.
        
        ---
        
        transforming from rate based to rate based speed values won't work well.
        
        better to use fractional speed values.
        REL_X of 40 = REL_WHEEL of 1 = REL_WHEE_HI_RES of 1/120
        
        this is why abs_to_rel_speed does not affect the rel_to_rel handler.
        
        The expo calculation will be wrong in the beginning, because it is based on
        the highest observed value. The overall gain will be fine though.
        """

        input_value = event.value
        if event.is_wheel_event:
            input_value /= WHEEL_SCALING
        elif event.is_wheel_hi_res_event:
            input_value /= WHEEL_SCALING * WHEEL_HI_RES_SCALING

        if abs(input_value) > self._max_observed_input:
            self._max_observed_input = abs(input_value)

        transformed = (
            self._transform(input_value / self._max_observed_input)
            * self._max_observed_input
        )

        is_wheel_output = self.mapping.is_wheel_output()
        is_hi_res_wheel_output = self.mapping.is_high_res_wheel_output()

        horizontal = self.mapping.output_code in (
            REL_HWHEEL_HI_RES,
            REL_HWHEEL,
        )

        try:
            if is_wheel_output or is_hi_res_wheel_output:
                # inject both kinds of wheels, otherwise wheels don't work for some
                # people. See issue #354
                self._write(
                    REL_HWHEEL if horizontal else REL_WHEEL,
                    self._wheel_remainder.input(transformed),
                )
                self._write(
                    REL_HWHEEL_HI_RES if horizontal else REL_WHEEL_HI_RES,
                    self._wheel_hi_res_remainder.input(transformed),
                )
            else:
                self._write(
                    self.mapping.output_code,
                    self._remainder.input(transformed),
                )

            return True
        except OverflowError:
            # screwed up the calculation of the event value
            logger.error("OverflowError while handling %s", event)
            return True
        except (exceptions.UinputNotAvailable, exceptions.EventNotHandled):
            return False

    def reset(self) -> None:
        pass

    def _write(self, code, value):
        if value == 0:
            return

        global_uinputs.write(
            (EV_REL, code, value),
            self.mapping.target_uinput,
        )

    def needs_wrapping(self) -> bool:
        return len(self.input_events) > 1

    def set_sub_handler(self, handler: InputEventHandler) -> None:
        assert False  # cannot have a sub-handler

    def wrap_with(self) -> Dict[EventCombination, HandlerEnums]:
        if self.needs_wrapping():
            return {EventCombination(self.input_events): HandlerEnums.axisswitch}
        return {}
