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

from inputremapper.configs.input_config import InputCombination, InputConfig
from inputremapper.configs.mapping import (
    Mapping,
    REL_XY_SCALING,
    WHEEL_SCALING,
    WHEEL_HI_RES_SCALING,
    DEFAULT_REL_RATE,
)
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


def calculate_output(value, weight, remainder):
    # self._value is between 0 and 1, scale up with weight
    scaled = value * weight + remainder
    # float_value % 1 will result in wrong calculations for negative values
    remainder = math.fmod(scaled, 1)
    return int(scaled), remainder


# TODO move into class?
async def _run_normal_output(self) -> None:
    """Start injecting events."""
    self._running = True
    self._stop = False
    remainder = 0.0
    start = time.time()

    # if the rate is configured to be slower than the default, increase the value, so
    # that the overall speed stays the same.
    rate_compensation = DEFAULT_REL_RATE / self.mapping.rel_rate
    weight = REL_XY_SCALING * rate_compensation

    while not self._stop:
        value, remainder = calculate_output(
            self._value,
            weight,
            remainder,
        )

        self._write(EV_REL, self.mapping.output_code, value)

        time_taken = time.time() - start
        sleep = max(0.0, (1 / self.mapping.rel_rate) - time_taken)
        await asyncio.sleep(sleep)
        start = time.time()

    self._running = False


# TODO move into class?
async def _run_wheel_output(self, codes: Tuple[int, int]) -> None:
    """Start injecting wheel events.

    made to inject both REL_WHEEL and REL_WHEEL_HI_RES events, because otherwise
    wheel output doesn't work for some people. See issue #354
    """
    weights = (WHEEL_SCALING, WHEEL_HI_RES_SCALING)

    self._running = True
    self._stop = False
    remainder = [0.0, 0.0]
    start = time.time()
    while not self._stop:
        for i in range(len(codes)):
            value, remainder[i] = calculate_output(
                self._value,
                weights[i],
                remainder[i],
            )

            self._write(EV_REL, codes[i], value)

        time_taken = time.time() - start
        await asyncio.sleep(max(0.0, (1 / self.mapping.rel_rate) - time_taken))
        start = time.time()

    self._running = False


class AbsToRelHandler(MappingHandler):
    """Handler which transforms an EV_ABS to EV_REL events."""

    _map_axis: InputConfig  # the InputConfig for the axis we map
    _value: float  # the current output value
    _running: bool  # if the run method is active
    _stop: bool  # if the run loop should return
    _transform: Optional[Transformation]

    def __init__(
        self,
        combination: InputCombination,
        mapping: Mapping,
        **_,
    ) -> None:
        super().__init__(combination, mapping)

        # find the input event we are supposed to map
        assert (map_axis := combination.find_analog_input_config(type_=EV_ABS))
        self._map_axis = map_axis

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
        name = get_evdev_constant_name(*self._map_axis.type_and_code)
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
        if event.input_match_hash != self._map_axis.input_match_hash:
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

        if transformed == 0:
            self._stop = True
            return True

        if not self._running:
            asyncio.ensure_future(self._run())
        return True

    def reset(self) -> None:
        self._stop = True

    def _write(self, type_, keycode, value):
        """Inject."""
        # if the mouse won't move even though correct stuff is written here,
        # the capabilities are probably wrong
        if value == 0:
            return  # rel 0 does not make sense

        try:
            global_uinputs.write((type_, keycode, value), self.mapping.target_uinput)
        except OverflowError:
            # screwed up the calculation of mouse movements
            logger.error("OverflowError (%s, %s, %s)", type_, keycode, value)

    def needs_wrapping(self) -> bool:
        return len(self.input_configs) > 1

    def set_sub_handler(self, handler: InputEventHandler) -> None:
        assert False  # cannot have a sub-handler

    def wrap_with(self) -> Dict[InputCombination, HandlerEnums]:
        if self.needs_wrapping():
            return {InputCombination(self.input_configs): HandlerEnums.axisswitch}
        return {}
