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
import time
from functools import partial
from typing import Dict, Tuple, Optional

import evdev
from evdev.ecodes import (
    EV_REL,
    EV_ABS,
    REL_WHEEL,
    REL_HWHEEL,
    REL_WHEEL_HI_RES,
    REL_HWHEEL_HI_RES,
)

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
from inputremapper.utils import get_evdev_constant_name


async def _run_normal_output(self) -> None:
    """Start injecting events."""
    weight = self.mapping.rel_speed

    self._running = True
    self._stop = False
    # logger.debug("starting AbsToRel loop")
    remainder = 0.0
    start = time.time()
    while not self._stop:
        # self._value is between 0 and 1, scale up with weight
        scaled = self._value * weight + remainder
        # float_value % 1 will result in wrong calculations for negative values
        remainder = math.fmod(scaled, 1)
        value = int(scaled)
        remainder = scaled - value
        self._write(EV_REL, self.mapping.output_code, value)

        time_taken = time.time() - start
        await asyncio.sleep(max(0.0, (1 / self.mapping.rel_rate) - time_taken))
        start = time.time()

    # logger.debug("stopping AbsToRel loop")
    self._running = False


async def _run_wheel_output(self, codes: Tuple[int, int]) -> None:
    """Start injecting wheel events.

    made to inject both REL_WHEEL and REL_WHEEL_HI_RES events, because otherwise
    wheel output doesn't work for some people. See issue #354
    """
    weights = (
        self.mapping.rel_wheel_speed,
        self.mapping.rel_wheel_hi_res_speed,
    )

    self._running = True
    self._stop = False
    # logger.debug("starting AbsToRel loop")
    remainder = [0.0, 0.0]
    start = time.time()
    while not self._stop:
        for i in range(len(codes)):
            # self._value is between 0 and 1, scale up with weights
            scaled = self._value * weights[i] + remainder[i]
            # float_value % 1 will result in wrong calculations for negative values
            remainder[i] = math.fmod(scaled, 1)
            value = int(scaled)
            self._write(EV_REL, codes[i], value)

        time_taken = time.time() - start
        await asyncio.sleep(max(0.0, (1 / self.mapping.rel_rate) - time_taken))
        start = time.time()

    # logger.debug("stopping AbsToRel loop")
    self._running = False


class AbsToRelHandler(MappingHandler):
    """Handler which transforms an EV_ABS to EV_REL events."""

    _map_axis: Tuple[int, int]  # the input (type, code) of the axis we map
    _value: float  # the current output value
    _running: bool  # if the run method is active
    _stop: bool  # if the run loop should return
    _transform: Optional[Transformation]

    def __init__(
        self,
        combination: EventCombination,
        mapping: Mapping,
        **_,
    ) -> None:
        super().__init__(combination, mapping)

        # find the input event we are supposed to map
        for event in combination:
            if event.value == 0:
                assert event.type == EV_ABS
                self._map_axis = event.type_and_code
                break

        self._value = 0
        self._running = False
        self._stop = True
        self._transform = None

        # bind the correct run method
        if self.mapping.output_code in (
            REL_WHEEL,
            REL_HWHEEL,
            REL_WHEEL_HI_RES,
            REL_HWHEEL_HI_RES,
        ):
            if self.mapping.output_code in (REL_WHEEL, REL_WHEEL_HI_RES):
                codes = (REL_WHEEL, REL_WHEEL_HI_RES)
            else:
                codes = (REL_HWHEEL, REL_HWHEEL_HI_RES)

            self._run = partial(_run_wheel_output, self, codes=codes)

        else:
            self._run = partial(_run_normal_output, self)

    def __str__(self):
        name = get_evdev_constant_name(*self._map_axis)
        return f'AbsToRelHandler for "{name}" {self._map_axis} <{id(self)}>:'

    def __repr__(self):
        return self.__str__()

    @property
    def child(self):  # used for logging
        return (
            f"maps to: {self.mapping.get_output_name_constant()} "
            f"{self.mapping.get_output_type_code()} at "
            f"{self.mapping.target_uinput}"
        )

    def notify(
        self,
        event: InputEvent,
        source: evdev.InputDevice,
        forward: evdev.UInput = None,
        suppress: bool = False,
    ) -> bool:

        if event.type_and_code != self._map_axis:
            return False

        if EventActions.recenter in event.actions:
            self._stop = True
            return True

        if not self._transform:
            absinfo = {
                entry[0]: entry[1]
                for entry in source.capabilities(absinfo=True)[EV_ABS]
            }
            self._transform = Transformation(
                max_=absinfo[event.code].max,
                min_=absinfo[event.code].min,
                deadzone=self.mapping.deadzone,
                gain=self.mapping.gain,
                expo=self.mapping.expo,
            )

        transformed = self._transform(event.value)

        self._value = transformed

        if self._value == 0:
            self._stop = True
            return True

        if not self._running:
            asyncio.ensure_future(self._run())
        return True

    def reset(self) -> None:
        self._stop = True

    def _write(self, ev_type, keycode, value):
        """Inject."""
        # if the mouse won't move even though correct stuff is written here,
        # the capabilities are probably wrong
        if value == 0:
            return  # rel 0 does not make sense

        try:
            global_uinputs.write((ev_type, keycode, value), self.mapping.target_uinput)
        except OverflowError:
            # screwed up the calculation of mouse movements
            logger.error("OverflowError (%s, %s, %s)", ev_type, keycode, value)

    def needs_wrapping(self) -> bool:
        return len(self.input_events) > 1

    def set_sub_handler(self, handler: InputEventHandler) -> None:
        assert False  # cannot have a sub-handler

    def wrap_with(self) -> Dict[EventCombination, HandlerEnums]:
        if self.needs_wrapping():
            return {EventCombination(self.input_events): HandlerEnums.axisswitch}
        return {}
