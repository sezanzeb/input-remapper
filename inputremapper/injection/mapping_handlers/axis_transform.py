# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2024 sezanzeb <b8x45ygc9@mozmail.com>
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

import math
from typing import Dict, Union


class Transformation:
    """Callable that returns the axis transformation at x."""

    def __init__(
        self,
        # if input values are > max_, the return value will be > 1
        max_: Union[int, float],
        min_: Union[int, float],
        deadzone: float,
        gain: float = 1,
        expo: float = 0,
    ) -> None:
        self._max = max_
        self._min = min_
        self._deadzone = deadzone
        self._gain = gain
        self._expo = expo
        self._cache: Dict[float, float] = {}

    def __call__(self, /, x: Union[int, float]) -> float:
        if x not in self._cache:
            y = (
                self._calc_qubic(self._flatten_deadzone(self._normalize(x)))
                * self._gain
            )
            self._cache[x] = y

        return self._cache[x]

    def set_range(self, min_, max_):
        # TODO docstring
        if min_ != self._min or max_ != self._max:
            self._cache = {}

        self._min = min_
        self._max = max_

    def _normalize(self, x: Union[int, float]) -> float:
        """Move and scale x to be between -1 and 1
        return: x
        """
        if self._min == -1 and self._max == 1:
            return x

        half_range = (self._max - self._min) / 2
        middle = half_range + self._min
        return (x - middle) / half_range

    def _flatten_deadzone(self, x: float) -> float:
        """
         y ^                     y ^
           |                       |
         1 |         /           1 |         /
           |       /               |        /
           |     /         ==>     |    ---
           |   /                   |  /
        -1 | /                  -1 | /
           |------------>          |------------>
            -1       1  x           -1       1  x
        """
        if abs(x) <= self._deadzone:
            return 0

        return (x - self._deadzone * x / abs(x)) / (1 - self._deadzone)

    def _calc_qubic(self, x: float) -> float:
        """Transforms an x value by applying a qubic function

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
        k = self._expo

        if k == 0 or x == 0:
            return x

        if 0 < k <= 1:
            d = 1 - k
            return d * x + (1 - d) * x**3

        if -1 <= k < 0:
            # calculate return value with the real inverse solution
            # of y = b * x + a * x ** 3
            # LaTeX  for better readability:
            #
            #  y=\frac{{{\left( \sqrt{27 {{x}^{2}}+\frac{4 {{b}^{3}}}{a}}
            #         +{{3}^{\frac{3}{2}}} x\right) }^{\frac{1}{3}}}}
            #     {{{2}^{\frac{1}{3}}} \sqrt{3} {{a}^{\frac{1}{3}}}}
            #   -\frac{{{2}^{\frac{1}{3}}} b}
            #     {\sqrt{3} {{a}^{\frac{2}{3}}}
            #         {{\left( \sqrt{27 {{x}^{2}}+\frac{4 {{b}^{3}}}{a}}
            #         +{{3}^{\frac{3}{2}}} x\right) }^{\frac{1}{3}}}}
            sign = x / abs(x)
            x = math.fabs(x)
            d = 1 + k
            a = 1 - d
            b = d
            c = (math.sqrt(27 * x**2 + (4 * b**3) / a) + 3 ** (3 / 2) * x) ** (1 / 3)
            y = c / (2 ** (1 / 3) * math.sqrt(3) * a ** (1 / 3)) - (
                2 ** (1 / 3) * b
            ) / (math.sqrt(3) * a ** (2 / 3) * c)
            return y * sign

        raise ValueError("k must be between -1 and 1")
