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
import dataclasses
import functools
import unittest
import itertools
from typing import Iterable, List

from inputremapper.injection.mapping_handlers.axis_transform import Transformation


class TestAxisTransformation(unittest.TestCase):
    @dataclasses.dataclass
    class InitArgs:
        max_: int
        min_: int
        deadzone: float
        gain: float
        expo: float

        def values(self):
            return self.__dict__.values()

    def get_init_args(
        self,
        max_=(255, 1000, 2**15),
        min_=(50, 0, -255),
        deadzone=(0, 0.5),
        gain=(0.5, 1, 2),
        expo=(-0.9, 0, 0.3),
    ) -> Iterable[InitArgs]:
        for args in itertools.product(max_, min_, deadzone, gain, expo):
            yield self.InitArgs(*args)

    @staticmethod
    def scale_to_range(min_, max_, x=(-1, -0.2, 0, 0.6, 1)) -> List[float]:
        """Scale values between -1 and 1 up, such that they are between min and max."""
        half_range = (max_ - min_) / 2
        return [float_x * half_range + min_ + half_range for float_x in x]

    def test_scale_to_range(self):
        """Make sure scale_to_range will actually return the min and max values
        (avoid "off by one" errors)"""
        max_ = (255, 1000, 2**15)
        min_ = (50, 0, -255)

        for x1, x2 in itertools.product(min_, max_):
            scaled = self.scale_to_range(x1, x2, (-1, 1))
            self.assertEqual(scaled, [x1, x2])

    def test_expo_symmetry(self):
        """Test that the transformation is symmetric for expo parameter
        x = f(g(x)), if  f._expo == - g._expo

        with the following constraints:
        min = -1, max = 1
        gain = 1
        deadzone = 0

        we can remove the constraints for min, max and gain,
        by scaling the values appropriately after each transformation
        """

        for init_args in self.get_init_args(deadzone=(0,)):
            f = Transformation(*init_args.values())
            init_args.expo = -init_args.expo
            g = Transformation(*init_args.values())

            scale = functools.partial(
                self.scale_to_range,
                init_args.min_,
                init_args.max_,
            )
            for x in scale():
                y1 = g(x)
                y1 = y1 / init_args.gain  # remove the gain
                y1 = scale((y1,))[0]  # remove the min/max constraint

                y2 = f(y1)
                y2 = y2 / init_args.gain  # remove the gain
                y2 = scale((y2,))[0]  # remove the min/max constraint
                self.assertAlmostEqual(x, y2, msg=f"test expo symmetry for {init_args}")

    def test_origin_symmetry(self):
        """Test that the transformation is symmetric to the origin
        f(x) = - f(-x)
        within the constraints: min = -max
        """

        for init_args in self.get_init_args():
            init_args.min_ = -init_args.max_
            f = Transformation(*init_args.values())
            for x in self.scale_to_range(init_args.min_, init_args.max_):
                self.assertAlmostEqual(
                    f(x),
                    -f(-x),
                    msg=f"test origin symmetry at {x=} for {init_args}",
                )

    def test_gain(self):
        """Test that f(max) = gain and f(min) = -gain."""
        for init_args in self.get_init_args():
            f = Transformation(*init_args.values())
            self.assertAlmostEqual(
                f(init_args.max_),
                init_args.gain,
                msg=f"test gain for {init_args}",
            )
            self.assertAlmostEqual(
                f(init_args.min_),
                -init_args.gain,
                msg=f"test gain for {init_args}",
            )

    def test_deadzone(self):
        """Test the Transfomation returns exactly 0 in the range of the deadzone."""

        for init_args in self.get_init_args(deadzone=(0.1, 0.2, 0.9)):
            f = Transformation(*init_args.values())
            for x in self.scale_to_range(
                init_args.min_,
                init_args.max_,
                x=(
                    init_args.deadzone * 0.999,
                    -init_args.deadzone * 0.999,
                    0.3 * init_args.deadzone,
                    0,
                ),
            ):
                self.assertEqual(f(x), 0, msg=f"test deadzone at {x=} for {init_args}")

    def test_continuity_near_deadzone(self):
        """Test that the Transfomation is continues (no sudden jump) next to the
        deadzone"""

        for init_args in self.get_init_args(deadzone=(0.1, 0.2, 0.9)):
            f = Transformation(*init_args.values())
            scale = functools.partial(
                self.scale_to_range,
                init_args.min_,
                init_args.max_,
            )
            x = (
                init_args.deadzone * 1.00001,
                init_args.deadzone * 1.001,
                -init_args.deadzone * 1.00001,
                -init_args.deadzone * 1.001,
            )
            scaled_x = scale(x=x)

            p1 = (x[0], f(scaled_x[0]))  # first point right of deadzone
            p2 = (x[1], f(scaled_x[1]))  # second point right of deadzone

            # calculate a linear function y = m * x + b from p1 and p2
            m = (p1[1] - p2[1]) / (p1[0] - p2[0])
            b = p1[1] - m * p1[0]

            # the zero intersection of that function must be close to the
            # edge of the deadzone
            self.assertAlmostEqual(
                -b / m,
                init_args.deadzone,
                places=5,
                msg=f"test continuity at {init_args.deadzone} for {init_args}",
            )

            # same thing on the other side
            p1 = (x[2], f(scaled_x[2]))
            p2 = (x[3], f(scaled_x[3]))
            m = (p1[1] - p2[1]) / (p1[0] - p2[0])
            b = p1[1] - m * p1[0]
            self.assertAlmostEqual(
                -b / m,
                -init_args.deadzone,
                places=5,
                msg=f"test continuity at {- init_args.deadzone} for {init_args}",
            )
