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

import evdev
import time
import asyncio
import math

from typing import Dict, Tuple
from evdev.ecodes import EV_REL

from inputremapper.logger import logger
from inputremapper.key import Key
from inputremapper.input_event import InputEvent
from inputremapper.injection.global_uinputs import global_uinputs


class AbsToRelHandler:
    """
    Handler which transforms an EV_ABS to EV_REL events
    and sends that to a UInput

    adheres to the MappingHandler protocol
    """

    _key: Key  # key of len 1 for the event to
    _target: str  # name of target UInput
    _deadzone: float  # deadzone
    _output: int  # target event code

    # the ratio between abs value as float between -1 and +1
    # and the output speed as units per tick
    _gain: float
    _expo: float
    _rate: int  # the tick rate in Hz

    _last_value: float  # value of last abs event between -1 and 1
    _running: bool  # if the run method is active
    _stop: bool  # if the run loop should return

    def __init__(self, config: Dict[str, any], _) -> None:
        """initialize the handler

        Parameters
        ----------
        config : Dict = {
            "key": str
            "target": str
            "deadzone" : float
            "output" : int
            "gain" : float
            "expo" : float
            "rate" : int
        }
        """
        self._key = Key(config["key"])
        self._target = config["target"]
        self._deadzone = config["deadzone"]
        self._output = config["output"]
        self._gain = config["gain"]
        self._expo = config["expo"]
        self._rate = config["rate"]

        self._last_value = 0
        self._running = False
        self._stop = True

    def __str__(self):
        return f"AbsToRelHandler for {self._key[0]} <{id(self)}>:"

    def __repr__(self):
        return self.__str__()

    @property
    def child(self):  # used for logging
        return f"maps to: {self._output} at {self._target}"

    async def notify(
        self,
        event: InputEvent,
        source: evdev.InputDevice = None,
        forward: evdev.UInput = None,
        supress: bool = False,
    ) -> bool:

        if event.type_and_code != self._key[0][:2]:
            return False

        input_value, scale_factor = self._normalize(
            event.value,
            source.absinfo(event.code).min,
            source.absinfo(event.code).max,
        )

        if abs(input_value) < self._deadzone:
            self._stop = True
            return True

        output_value = self._calc_qubic(input_value, self._expo)
        self._last_value = output_value * scale_factor * self._gain

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
            return d * x + (1 - d) * x ** 3

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
            c = (math.sqrt(27 * x ** 2 + (4 * b ** 3) / a) + 3 ** (3 / 2) * x) ** (
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

    async def _run(self) -> None:
        """start injecting events"""
        self._running = True
        self._stop = False
        # logger.debug("starting AbsToRel loop")
        remainder = 0.0
        start = time.time()
        while not self._stop:
            float_value = self._last_value * self._gain + remainder
            remainder = float_value % 1
            value = int(float_value)
            self._write(EV_REL, self._output, value)

            time_taken = time.time() - start
            await asyncio.sleep(max(0.0, (1 / self._rate) - time_taken))
            start = time.time()

        # logger.debug("stopping AbsToRel loop")
        self._running = False

    def _write(self, ev_type, keycode, value):
        """Inject."""
        # if the mouse won't move even though correct stuff is written here,
        # the capabilities are probably wrong
        try:
            global_uinputs.write((ev_type, keycode, value), self._target)
        except OverflowError:
            # screwed up the calculation of mouse movements
            logger.error("OverflowError (%s, %s, %s)", ev_type, keycode, value)
