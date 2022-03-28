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
from functools import partial

import evdev
import time
import asyncio
import math

from typing import Dict, Tuple, Optional, List, Union
from evdev.ecodes import (
    EV_REL,
    EV_ABS,
    REL_WHEEL,
    REL_HWHEEL,
    REL_WHEEL_HI_RES,
    REL_HWHEEL_HI_RES,
)

from inputremapper.configs.mapping import Mapping
from inputremapper.injection.mapping_handlers.mapping_handler import (
    MappingHandler,
    ContextProtocol,
    HandlerEnums,
    InputEventHandler,
)
from inputremapper.logger import logger
from inputremapper.event_combination import EventCombination
from inputremapper.input_event import InputEvent, EventActions
from inputremapper.injection.global_uinputs import global_uinputs


async def _run_normal(self) -> None:
    """start injecting events"""
    self._running = True
    self._stop = False
    # logger.debug("starting AbsToRel loop")
    remainder = 0.0
    start = time.time()
    while not self._stop:
        float_value = self._value + remainder
        # float_value % 1 will result in wrong calculations for negative values
        remainder = math.fmod(float_value, 1)
        value = int(float_value)
        self._write(EV_REL, self.mapping.output_code, value)

        time_taken = time.time() - start
        await asyncio.sleep(max(0.0, (1 / self.mapping.rate) - time_taken))
        start = time.time()

    # logger.debug("stopping AbsToRel loop")
    self._running = False


async def _run_wheel(self, codes: Tuple[int, int], weights: Tuple[int, int]) -> None:
    """start injecting events"""
    self._running = True
    self._stop = False
    # logger.debug("starting AbsToRel loop")
    remainder = [0.0, 0.0]
    start = time.time()
    while not self._stop:
        for i in range(0, 2):
            float_value = self._value * weights[i] + remainder[i]
            # float_value % 1 will result in wrong calculations for negative values
            remainder[i] = math.fmod(float_value, 1)
            value = int(float_value)
            self._write(EV_REL, codes[i], value)

        time_taken = time.time() - start
        await asyncio.sleep(max(0.0, (1 / self.mapping.rate) - time_taken))
        start = time.time()

    # logger.debug("stopping AbsToRel loop")
    self._running = False


class AbsToRelHandler(MappingHandler):
    """Handler which transforms an EV_ABS to EV_REL events"""

    _map_axis: Tuple[int, int]  # the (type, code) of the axis we map
    _value: float  # the current output value
    _running: bool  # if the run method is active
    _stop: bool  # if the run loop should return

    def __init__(
        self,
        combination: EventCombination,
        mapping: Mapping,
        context: ContextProtocol,
    ) -> None:
        super().__init__(combination, mapping, context)

        # find the input event we are supposed to map
        for event in combination:
            if event.value == 0:
                assert event.type == EV_ABS
                self._map_axis = event.type_and_code
                break

        self._value = 0
        self._running = False
        self._stop = True

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

            if self.mapping.output_code in (REL_WHEEL, REL_HWHEEL):
                weights = (1, 120)
            else:
                weights = (1 / 120, 1)

            self._run = partial(_run_wheel, self, codes=codes, weights=weights)

        else:
            self._run = _run_normal.__get__(self, AbsToRelHandler)

    def __str__(self):
        return f"AbsToRelHandler for {self._map_axis} <{id(self)}>:"

    def __repr__(self):
        return self.__str__()

    @property
    def child(self):  # used for logging
        return f"maps to: {self.mapping.output_code} at {self.mapping.target_uinput}"

    def notify(
        self,
        event: InputEvent,
        source: evdev.InputDevice = None,
        forward: evdev.UInput = None,
        supress: bool = False,
    ) -> bool:

        if event.type_and_code != self._map_axis:
            return False

        if event.action == EventActions.recenter:
            self._stop = True
            return True

        absinfo = {
            entry[0]: entry[1] for entry in source.capabilities(absinfo=True)[EV_ABS]
        }
        input_value, _ = self._normalize(
            event.value,
            absinfo[event.code].min,
            absinfo[event.code].max,
        )

        if abs(input_value) < self.mapping.deadzone:
            self._stop = True
            return True

        value = self._calc_qubic(input_value, self.mapping.expo)
        self._value = value * self.mapping.rel_speed * self.mapping.gain

        if not self._running:
            asyncio.ensure_future(self._run())
        return True

    @staticmethod
    def _calc_qubic(x: float, k: float) -> float:
        """
        transforms an x value by applying a qubic function

        k = 0 : will yield no transformation f(x) = x
        1 > k > 0 : will yield low sensitivity for low x values
            and high sensitivity for high x values
        -1 < k < 0 : will yield high sensitivity for low x values
            and low sensitivity for high x values

        see also: https://www.geogebra.org/calculator/mkdqueky

        Mathematical definition:
        f(x,d) = d * x + (1 - d) * x ** 3 | d = 1 - k | k ∈ [0,1]
        the function is designed such that if follows these constraints:
        f'(0, d) = d and f(1, d) = 1 and f(-x,d) = -f(x,d)

        for k ∈ [-1,0) the above function is mirrored at y = x
        and d = 1 + k
        """
        # TODO: since k is constant for each mapping we can sample this function in
        #  the constructor and provide a lookup table to interpolate at runtime
        if k == 0:
            return x

        if 0 < k <= 1:
            d = 1 - k
            return d * x + (1 - d) * x**3

        if -1 <= k < 0:
            # calculate return value with the real inverse solution of y = b * x + a * x ** 3
            # LaTeX  for better readability:
            #
            #  y=\frac{{{\left( \sqrt{27 {{x}^{2}}+\frac{4 {{b}^{3}}}{a}}
            #         +{{3}^{\frac{3}{2}}} x\right) }^{\frac{1}{3}}}}
            #     {{{2}^{\frac{1}{3}}} \sqrt{3} {{a}^{\frac{1}{3}}}}
            #   -\frac{{{2}^{\frac{1}{3}}} b}
            #     {\sqrt{3} {{a}^{\frac{2}{3}}}
            #         {{\left( \sqrt{27 {{x}^{2}}+\frac{4 {{b}^{3}}}{a}}
            #         +{{3}^{\frac{3}{2}}} x\right) }^{\frac{1}{3}}}}
            sign = 1 if x >= 0 else -1
            x = math.fabs(x)
            d = 1 + k
            a = 1 - d
            b = d
            c = (math.sqrt(27 * x**2 + (4 * b**3) / a) + 3 ** (3 / 2) * x) ** (
                1 / 3
            )
            y = c / (2 ** (1 / 3) * math.sqrt(3) * a ** (1 / 3)) - (
                2 ** (1 / 3) * b
            ) / (math.sqrt(3) * a ** (2 / 3) * c)
            return y * sign

        raise ValueError("k must be between -1 and 1")

    @staticmethod
    def _normalize(x: int, abs_min: int, abs_max: int) -> Tuple[float, float]:
        """
        move and scale x to be between -1 and 1
        return: x, scale_factor
        """
        if abs_min == -1 and abs_max == 1:
            return x, 1

        half_range = (abs_max - abs_min) / 2
        middle = half_range + abs_min
        x_norm = (x - middle) / half_range
        return x_norm, half_range

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
            return {self.input_events: HandlerEnums.axisswitch}
        return {}
