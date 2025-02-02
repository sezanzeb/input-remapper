#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2025 sezanzeb <b8x45ygc9@mozmail.com>
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
import unittest

from evdev._ecodes import (
    REL_Y,
    EV_REL,
    REL_HWHEEL,
    REL_HWHEEL_HI_RES,
    REL_X,
    REL_WHEEL,
    REL_WHEEL_HI_RES,
    KEY_A,
    EV_KEY,
)

from inputremapper.configs.validation_errors import MacroError
from inputremapper.injection.macros.parse import Parser
from tests.lib.test_setup import test_setup
from tests.unit.test_macros.macro_test_base import DummyMapping, MacroTestBase


@test_setup
class TestMouse(MacroTestBase):
    async def test_mouse_acceleration(self):
        # There is a tiny float-rounding error that can break the test, therefore I use
        # 0.09001 to make it more robust.
        await self._run_macro("mouse(up, 10, 0.09001)", 0.1)
        self.assertEqual(
            [
                (EV_REL, REL_Y, -2),
                (EV_REL, REL_Y, -3),
                (EV_REL, REL_Y, -4),
                (EV_REL, REL_Y, -4),
                (EV_REL, REL_Y, -5),
            ],
            self.result,
        )

    async def test_rate(self):
        # It should move 200 times per second by 1px, for 0.2 seconds.
        rel_rate = 200
        time = 0.2
        speed = 1
        expected_movement = time * rel_rate * speed

        await self._run_macro(f"mouse(down, {speed})", time, rel_rate)
        total_movement = sum(event[2] for event in self.result)
        self.assertAlmostEqual(float(total_movement), expected_movement, delta=1)

    async def test_slow_movement(self):
        await self._run_macro(f"mouse(down, 0.1)", 0.2, 200)
        total_movement = sum(event[2] for event in self.result)
        self.assertAlmostEqual(total_movement, 4, delta=1)

    async def test_mouse_xy_acceleration_1(self):
        await self._run_macro("mouse_xy(2, -10, 0.09001)", 0.1)
        self.assertEqual(
            [
                (EV_REL, REL_Y, -2),
                (EV_REL, REL_Y, -3),
                (EV_REL, REL_Y, -4),
                (EV_REL, REL_Y, -4),
                (EV_REL, REL_Y, -5),
            ],
            self._get_y_movement(),
        )
        self.assertEqual(
            [
                (EV_REL, REL_X, 1),
                (EV_REL, REL_X, 1),
                (EV_REL, REL_X, 1),
            ],
            self._get_x_movement(),
        )

    async def test_mouse_xy_acceleration_2(self):
        await self._run_macro("mouse_xy(10, -2, 0.09001)", 0.1)
        self.assertEqual(
            [
                (EV_REL, REL_Y, -1),
                (EV_REL, REL_Y, -1),
                (EV_REL, REL_Y, -1),
            ],
            self._get_y_movement(),
        )
        self.assertEqual(
            [
                (EV_REL, REL_X, 2),
                (EV_REL, REL_X, 3),
                (EV_REL, REL_X, 4),
                (EV_REL, REL_X, 4),
                (EV_REL, REL_X, 5),
            ],
            self._get_x_movement(),
        )

    async def test_mouse_xy_only_x(self):
        await self._run_macro("mouse_xy(x=10, acceleration=1)", 0.1)
        self.assertEqual([], self._get_y_movement())
        self.assertEqual(
            [
                (EV_REL, REL_X, 10),
                (EV_REL, REL_X, 10),
                (EV_REL, REL_X, 10),
                (EV_REL, REL_X, 10),
                (EV_REL, REL_X, 10),
                (EV_REL, REL_X, 10),
            ],
            self._get_x_movement(),
        )

    async def test_mouse_xy_only_y(self):
        await self._run_macro("mouse_xy(y=10)", 0.1)
        self.assertEqual([], self._get_x_movement())
        self.assertEqual(
            [
                (EV_REL, REL_Y, 10),
                (EV_REL, REL_Y, 10),
                (EV_REL, REL_Y, 10),
                (EV_REL, REL_Y, 10),
                (EV_REL, REL_Y, 10),
                (EV_REL, REL_Y, 10),
            ],
            self._get_y_movement(),
        )

    async def test_wheel_left(self):
        wheel_speed = 60
        sleep = 0.1
        await self._run_macro(f"wheel(left, {wheel_speed})", sleep)

        self.assertIn((EV_REL, REL_HWHEEL, 1), self.result)
        self.assertIn((EV_REL, REL_HWHEEL_HI_RES, 60), self.result)

        expected_num_hires_events = sleep * DummyMapping.rel_rate
        expected_num_wheel_events = int(expected_num_hires_events / 120 * wheel_speed)
        actual_num_wheel_events = self.result.count((EV_REL, REL_HWHEEL, 1))
        actual_num_hires_events = self.result.count(
            (
                EV_REL,
                REL_HWHEEL_HI_RES,
                wheel_speed,
            )
        )

        self.assertGreater(
            actual_num_wheel_events,
            expected_num_wheel_events * 0.9,
        )
        self.assertLess(
            actual_num_wheel_events,
            expected_num_wheel_events * 1.1,
        )
        self.assertGreater(
            actual_num_hires_events,
            expected_num_hires_events * 0.9,
        )
        self.assertLess(
            actual_num_hires_events,
            expected_num_hires_events * 1.1,
        )

    async def test_wheel_up(self):
        await self._run_macro(f"wheel(up, 60)", 0.1)
        self.assertIn((EV_REL, REL_WHEEL, 1), self.result)
        self.assertIn((EV_REL, REL_WHEEL_HI_RES, 60), self.result)

    async def test_wheel_down(self):
        await self._run_macro(f"wheel(down, 60)", 0.1)
        self.assertIn((EV_REL, REL_WHEEL, -1), self.result)
        self.assertIn((EV_REL, REL_WHEEL_HI_RES, -60), self.result)

    async def test_wheel_right(self):
        await self._run_macro(f"wheel(right, 60)", 0.1)
        self.assertIn((EV_REL, REL_HWHEEL, -1), self.result)
        self.assertIn((EV_REL, REL_HWHEEL_HI_RES, -60), self.result)

    async def test_mouse_releases(self):
        await self._run_macro(f"mouse(down, 1).key(a)", 0.1)
        self.assertEqual(self.result[-2:], [(EV_KEY, KEY_A, 1), (EV_KEY, KEY_A, 0)])

    async def test_mouse_xy_releases(self):
        await self._run_macro(f"mouse_xy(1, 1, 1).key(a)", 0.1)
        self.assertEqual(self.result[-2:], [(EV_KEY, KEY_A, 1), (EV_KEY, KEY_A, 0)])

    async def test_wheel_releases(self):
        await self._run_macro(f"wheel(down, 1).key(a)", 0.1)
        self.assertEqual(self.result[-2:], [(EV_KEY, KEY_A, 1), (EV_KEY, KEY_A, 0)])

    async def test_raises_error(self):
        Parser.parse("mouse(up, 3)", self.context)  # no error
        Parser.parse("mouse(up, speed=$a)", self.context)  # no error
        self.assertRaises(MacroError, Parser.parse, "mouse(3, up)", self.context)
        Parser.parse("wheel(left, 3)", self.context)  # no error
        self.assertRaises(MacroError, Parser.parse, "wheel(3, left)", self.context)

    def _get_x_movement(self):
        return [event for event in self.result if event[1] == REL_X]

    def _get_y_movement(self):
        return [event for event in self.result if event[1] == REL_Y]

    async def _run_macro(
        self,
        code: str,
        time: float,
        rel_rate: int = DummyMapping.rel_rate,
    ):
        dummy_mapping = DummyMapping()
        dummy_mapping.rel_rate = rel_rate
        macro = Parser.parse(
            code,
            self.context,
            dummy_mapping,
        )
        macro.press_trigger()
        asyncio.ensure_future(macro.run(self.handler))

        await asyncio.sleep(time)
        self.assertTrue(macro.tasks[0].is_holding())
        macro.release_trigger()
        await asyncio.sleep(0.05)


if __name__ == "__main__":
    unittest.main()
