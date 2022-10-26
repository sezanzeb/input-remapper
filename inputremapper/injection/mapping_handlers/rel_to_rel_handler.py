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
from typing import Dict, Tuple, Optional

import evdev
from evdev.ecodes import (
    EV_REL,
    REL_X,
    REL_Y,
    REL_WHEEL,
    REL_HWHEEL,
    REL_WHEEL_HI_RES,
    REL_HWHEEL_HI_RES,
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
    _transform: Transformation

    # infinite loop which centers the output when input stops
    _recenter_loop: Optional[asyncio.Task]
    _moving: asyncio.Event  # event to notify the _recenter_loop

    _wheel_remainder: Remainder
    _wheel_hi_res_remainder: Remainder
    _default_remainder: Remainder

    def __init__(
        self,
        combination: EventCombination,
        mapping: Mapping,
        **_,
    ) -> None:
        super().__init__(combination, mapping)

        self._remainder = 0

        # find the input event we are supposed to map. If the input combination is
        # BTN_A + REL_X + BTN_B, then use the value of REL_X for the transformation
        input_event = mapping.find_analog_input_event(type_=EV_REL)
        assert input_event is not None
        self._input_event = input_event

        # - If rel_x is mapped to rel_y, it will transform it to between 0 and 1,
        # and then scale it back to exactly its original value.
        # - If rel_x is mapped to rel_wheel, and the mouse is moved in a normal
        # tempo, then the wheel should move in a normal tempo as well.
        # -> So the same speed is used as max_ and for scaling.
        if self._input_event.is_wheel_event:
            max_ = self.mapping.rel_wheel_speed
        elif self._input_event.is_wheel_hi_res_event:
            max_ = self.mapping.rel_wheel_hi_res_speed
        else:
            max_ = self.mapping.rel_xy_speed

        self._wheel_remainder = Remainder(self.mapping.rel_wheel_speed)
        self._wheel_hi_res_remainder = Remainder(self.mapping.rel_wheel_hi_res_speed)
        self._xy_remainder = Remainder(self.mapping.rel_xy_speed)

        self._transform = Transformation(
            max_=max_,
            min_=-max_,
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

        try:
            transformed = self._transform(event.value)

            # value is between 0 and 1, scale up
            wheel_output = self.mapping.is_wheel_output()
            hi_res_wheel_output = self.mapping.is_high_res_wheel_output()

            horizontal = self.mapping.output_code in (
                REL_HWHEEL_HI_RES,
                REL_HWHEEL,
            )

            if wheel_output or hi_res_wheel_output:
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
                    self._xy_remainder.input(transformed),
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
