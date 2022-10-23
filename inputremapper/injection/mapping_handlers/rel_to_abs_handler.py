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
from typing import Tuple, Dict, Optional

import evdev
from evdev.ecodes import (
    EV_ABS,
    EV_REL,
    REL_WHEEL,
    REL_HWHEEL,
    REL_HWHEEL_HI_RES,
    REL_WHEEL_HI_RES,
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
from inputremapper.input_event import InputEvent, EventActions
from inputremapper.logger import logger


class RelToAbsHandler(MappingHandler):
    """Handler which transforms EV_REL to EV_ABS events"""

    _input_movement: Tuple[int, int]  # (type, code) of the relative movement we map
    _output_axis: Tuple[int, int]  # the (type, code) of the output axis
    _transform: Transformation
    _target_absinfo: evdev.AbsInfo

    # infinite loop which centers the output when input stops
    _recenter_loop: Optional[asyncio.Task]
    _moving: asyncio.Event  # event to notify the _recenter_loop

    def __init__(
        self,
        combination: EventCombination,
        mapping: Mapping,
        **_,
    ) -> None:
        super().__init__(combination, mapping)

        # find the input event we are supposed to map. If the input combination is
        # BTN_A + REL_X + BTN_B, then use the value of REL_X for the transformation
        analog_input = mapping.find_analog_input_event(type_=EV_REL)
        assert analog_input is not None
        self._input_movement = analog_input.type_and_code

        assert mapping.output_code is not None
        assert mapping.output_type == EV_ABS
        self._output_axis = (mapping.output_type, mapping.output_code)

        self._target_absinfo = {
            code: absinfo
            for code, absinfo in global_uinputs.get_uinput(
                mapping.target_uinput
            ).capabilities(absinfo=True)[EV_ABS]
        }[mapping.output_code]

        # TODO test?
        if self._input_movement[1] in [REL_WHEEL, REL_HWHEEL]:
            max_ = mapping.rel_wheel_max_input
        elif self._input_movement[1] in [REL_WHEEL_HI_RES, REL_HWHEEL_HI_RES]:
            max_ = mapping.rel_wheel_hi_res_max_input
        else:
            max_ = mapping.rel_xy_max_input

        self._transform = Transformation(
            max_=max_,
            min_=-max_,
            deadzone=mapping.deadzone,
            gain=mapping.gain,
            expo=mapping.expo,
        )
        self._moving = asyncio.Event()
        self._recenter_loop = None

    def __str__(self):
        return f"RelToAbsHandler for {self._input_movement} <{id(self)}>:"

    def __repr__(self):
        return self.__str__()

    @property
    def child(self):  # used for logging
        return f"maps to: {self.mapping.output_code} at {self.mapping.target_uinput}"

    def notify(
        self,
        event: InputEvent,
        source: evdev.InputDevice,
        forward: evdev.UInput = None,
        suppress: bool = False,
    ) -> bool:
        if event.type_and_code != self._input_movement:
            return False

        if EventActions.recenter in event.actions:
            if self._recenter_loop:
                self._recenter_loop.cancel()
            self._recenter()
            return True

        if not self._recenter_loop:
            self._recenter_loop = asyncio.create_task(self._create_recenter_loop())

        self._moving.set()  # notify the _recenter_loop
        try:
            self._write(self._scale_to_target(self._transform(event.value)))
            return True
        except (exceptions.UinputNotAvailable, exceptions.EventNotHandled):
            return False

    def reset(self) -> None:
        if self._recenter_loop:
            self._recenter_loop.cancel()
        self._recenter()

    def _recenter(self) -> None:
        """recenter the output"""
        self._write(self._scale_to_target(0))

    async def _create_recenter_loop(self) -> None:
        """coroutine which waits for the input to start moving,
        then waits until the input stops moving, centers the output and repeat.

        runs forever"""
        while True:
            await self._moving.wait()  # input moving started
            while (
                await asyncio.wait(
                    (self._moving.wait(),), timeout=self.mapping.release_timeout
                )
            )[0]:
                self._moving.clear()  # still moving
            self._recenter()  # input moving stopped

    def _scale_to_target(self, x: float) -> int:
        """scales a x value between -1 and 1 to an integer between
        target_absinfo.min and target_absinfo.max

        input values above 1 or below -1 are clamped to the extreme values
        """
        factor = (self._target_absinfo.max - self._target_absinfo.min) / 2
        offset = self._target_absinfo.min + factor
        y = factor * x + offset
        if y > offset:
            return int(min(self._target_absinfo.max, y))
        else:
            return int(max(self._target_absinfo.min, y))

    def _write(self, value: int) -> None:
        """Inject."""
        try:
            global_uinputs.write(
                (*self._output_axis, value), self.mapping.target_uinput
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
