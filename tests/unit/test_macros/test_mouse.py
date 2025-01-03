#!/usr/bin/env python3
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

import asyncio
import unittest

from evdev._ecodes import REL_Y, EV_REL, REL_HWHEEL, REL_HWHEEL_HI_RES, REL_X

from inputremapper.injection.macros.parse import Parser
from tests.lib.test_setup import test_setup
from tests.unit.test_macros.macro_test_base import DummyMapping, MacroTestBase


@test_setup
class TestMouse(MacroTestBase):
    async def test_mouse_acceleration(self):
        # There is a tiny float-rounding error that can break the test, therefore I use
        # 0.09001 to make it more robust.
        await self._run_mouse_macro("mouse(up, 10, 0.09001)", 0.1)
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

        await self._run_mouse_macro(f"mouse(down, {speed})", time, rel_rate)
        total_movement = sum(event[2] for event in self.result)
        self.assertAlmostEqual(float(total_movement), expected_movement, delta=1)

    async def test_slow_movement(self):
        await self._run_mouse_macro(f"mouse(down, 0.1)", 0.2, 200)
        total_movement = sum(event[2] for event in self.result)
        self.assertAlmostEqual(total_movement, 4, delta=1)

    async def test_mouse_xy_acceleration_1(self):
        await self._run_mouse_macro("mouse_xy(2, -10, 0.09001)", 0.1)
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
        await self._run_mouse_macro("mouse_xy(10, -2, 0.09001)", 0.1)
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
        await self._run_mouse_macro("mouse_xy(x=10, acceleration=1)", 0.1)
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
        await self._run_mouse_macro("mouse_xy(y=10)", 0.1)
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

    async def test_mouse_and_wheel(self):
        wheel_speed = 60
        macro_1 = Parser.parse("mouse(up, 4)", self.context, DummyMapping)
        macro_2 = Parser.parse(
            f"wheel(left, {wheel_speed})", self.context, DummyMapping
        )
        macro_1.press_trigger()
        macro_2.press_trigger()
        asyncio.ensure_future(macro_1.run(self.handler))
        asyncio.ensure_future(macro_2.run(self.handler))

        sleep = 0.1
        await asyncio.sleep(sleep)
        self.assertTrue(macro_1.tasks[0].is_holding())
        self.assertTrue(macro_2.tasks[0].is_holding())
        macro_1.release_trigger()
        macro_2.release_trigger()

        self.assertIn((EV_REL, REL_Y, -4), self.result)
        expected_wheel_hi_res_event_count = sleep * DummyMapping.rel_rate
        expected_wheel_event_count = int(
            expected_wheel_hi_res_event_count / 120 * wheel_speed
        )
        actual_wheel_event_count = self.result.count((EV_REL, REL_HWHEEL, 1))
        actual_wheel_hi_res_event_count = self.result.count(
            (
                EV_REL,
                REL_HWHEEL_HI_RES,
                wheel_speed,
            )
        )
        # this seems to have a tendency of injecting less wheel events,
        # especially if the sleep is short
        self.assertGreater(actual_wheel_event_count, expected_wheel_event_count * 0.8)
        self.assertLess(actual_wheel_event_count, expected_wheel_event_count * 1.1)
        self.assertGreater(
            actual_wheel_hi_res_event_count, expected_wheel_hi_res_event_count * 0.8
        )
        self.assertLess(
            actual_wheel_hi_res_event_count, expected_wheel_hi_res_event_count * 1.1
        )

    def _get_x_movement(self):
        return [event for event in self.result if event[1] == REL_X]

    def _get_y_movement(self):
        return [event for event in self.result if event[1] == REL_Y]

    async def _run_mouse_macro(
        self,
        code: str,
        time: float,
        rel_rate: int = DummyMapping.rel_rate,
    ):
        dummy_mapping = DummyMapping()
        dummy_mapping.rel_rate = rel_rate
        macro_1 = Parser.parse(
            code,
            self.context,
            dummy_mapping,
        )
        macro_1.press_trigger()
        asyncio.ensure_future(macro_1.run(self.handler))

        await asyncio.sleep(time)
        macro_1.release_trigger()


if __name__ == "__main__":
    unittest.main()
