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
from typing import Iterable

import evdev
from evdev.ecodes import (
    EV_KEY,
    EV_ABS,
    EV_REL,
    ABS_X,
    ABS_Y,
    REL_X,
    REL_Y,
    BTN_A,
    REL_HWHEEL,
    REL_WHEEL,
    REL_WHEEL_HI_RES,
    REL_HWHEEL_HI_RES,
    ABS_HAT0X,
    BTN_LEFT,
    BTN_B,
    KEY_A,
    ABS_HAT0Y,
    KEY_B,
    KEY_C,
    KEY_D,
    BTN_TL,
    KEY_1,
)

from inputremapper.configs.mapping import (
    Mapping,
    REL_XY_SCALING,
    WHEEL_SCALING,
    WHEEL_HI_RES_SCALING,
    DEFAULT_REL_RATE,
)
from inputremapper.configs.preset import Preset
from inputremapper.configs.keyboard_layout import keyboard_layout
from inputremapper.configs.input_config import InputCombination, InputConfig
from inputremapper.injection.context import Context
from inputremapper.injection.event_reader import EventReader
from inputremapper.injection.global_uinputs import GlobalUInputs, UInput
from inputremapper.injection.mapping_handlers.mapping_parser import MappingParser
from inputremapper.input_event import InputEvent
from tests.lib.cleanup import cleanup
from tests.lib.logger import logger
from tests.lib.constants import MAX_ABS, MIN_ABS
from tests.lib.fixtures import Fixture, fixtures
from tests.lib.pipes import uinput_write_history
from tests.lib.test_setup import test_setup
from tests.unit.test_event_pipeline.event_pipeline_test_base import (
    EventPipelineTestBase,
)


@test_setup
class TestRelToRel(EventPipelineTestBase):
    async def _test(self, input_code, input_value, output_code, output_value, gain=1):
        preset = Preset()

        input_config = InputConfig(type=EV_REL, code=input_code)
        mapping = Mapping(
            input_combination=InputCombination([input_config]).to_config(),
            target_uinput="mouse",
            output_type=EV_REL,
            output_code=output_code,
            deadzone=0,
            gain=gain,
        )
        preset.add(mapping)

        event_reader = self.create_event_reader(preset, fixtures.gamepad)

        await self.send_events(
            [InputEvent(0, 0, EV_REL, input_code, input_value)],
            event_reader,
        )

        history = self.global_uinputs.get_uinput("mouse").write_history

        self.assertEqual(len(history), 1)
        self.assertEqual(
            history[0],
            InputEvent(0, 0, EV_REL, output_code, output_value),
        )

    async def test_wheel_to_y(self):
        await self._test(
            input_code=REL_WHEEL,
            input_value=2 * WHEEL_SCALING,
            output_code=REL_Y,
            output_value=2 * REL_XY_SCALING,
        )

    async def test_hi_res_wheel_to_y(self):
        await self._test(
            input_code=REL_WHEEL_HI_RES,
            input_value=3 * WHEEL_HI_RES_SCALING,
            output_code=REL_Y,
            output_value=3 * REL_XY_SCALING,
        )

    async def test_x_to_hwheel(self):
        # injects both hi_res and regular wheel events at the same time

        input_code = REL_X
        input_value = 100
        output_code = REL_HWHEEL
        gain = 2

        output_value = int(input_value / REL_XY_SCALING * WHEEL_SCALING * gain)
        output_value_hi_res = int(
            input_value / REL_XY_SCALING * WHEEL_HI_RES_SCALING * gain
        )

        preset = Preset()

        input_config = InputConfig(type=EV_REL, code=input_code)
        mapping = Mapping(
            input_combination=InputCombination([input_config]).to_config(),
            target_uinput="mouse",
            output_type=EV_REL,
            output_code=output_code,
            deadzone=0,
            gain=gain,
        )
        preset.add(mapping)

        event_reader = self.create_event_reader(preset, fixtures.gamepad)

        await self.send_events(
            [InputEvent(0, 0, EV_REL, input_code, input_value)],
            event_reader,
        )

        history = self.global_uinputs.get_uinput("mouse").write_history
        # injects both REL_WHEEL and REL_WHEEL_HI_RES events
        self.assertEqual(len(history), 2)
        self.assertEqual(
            history[0],
            InputEvent(
                0,
                0,
                EV_REL,
                REL_HWHEEL,
                output_value,
            ),
        )

        self.assertEqual(
            history[1],
            InputEvent(
                0,
                0,
                EV_REL,
                REL_HWHEEL_HI_RES,
                output_value_hi_res,
            ),
        )

    async def test_remainder(self):
        preset = Preset()
        history = self.global_uinputs.get_uinput("mouse").write_history

        # REL_WHEEL_HI_RES to REL_Y
        input_config = InputConfig(type=EV_REL, code=REL_WHEEL_HI_RES)
        gain = 0.01
        mapping = Mapping(
            input_combination=InputCombination([input_config]).to_config(),
            target_uinput="mouse",
            output_type=EV_REL,
            output_code=REL_Y,
            deadzone=0,
            gain=gain,
        )
        preset.add(mapping)

        event_reader = self.create_event_reader(preset, fixtures.gamepad)

        events_until_one_rel_y_written = int(
            WHEEL_HI_RES_SCALING / REL_XY_SCALING / gain
        )
        # due to the low gain and low input value, it needs to be sent many times
        # until one REL_Y event is written
        await self.send_events(
            [InputEvent(0, 0, EV_REL, REL_WHEEL_HI_RES, 1)]
            * (events_until_one_rel_y_written - 1),
            event_reader,
        )
        self.assertEqual(len(history), 0)

        # write the final event that causes the input to accumulate to 1
        # plus one extra event because of floating-point math
        await self.send_events(
            [InputEvent(0, 0, EV_REL, REL_WHEEL_HI_RES, 1)],
            event_reader,
        )
        self.assertEqual(len(history), 1)
        self.assertEqual(
            history[0],
            InputEvent(0, 0, EV_REL, REL_Y, 1),
        )

        # repeat it one more time to see if the remainder is reset correctly
        await self.send_events(
            [InputEvent(0, 0, EV_REL, REL_WHEEL_HI_RES, 1)]
            * (events_until_one_rel_y_written - 1),
            event_reader,
        )
        self.assertEqual(len(history), 1)

        # the event that causes the second REL_Y to be written
        # this should never need the one extra if the remainder is reset correctly
        await self.send_events(
            [InputEvent(0, 0, EV_REL, REL_WHEEL_HI_RES, 1)],
            event_reader,
        )
        self.assertEqual(len(history), 2)
        self.assertEqual(
            history[1],
            InputEvent(0, 0, EV_REL, REL_Y, 1),
        )


if __name__ == "__main__":
    unittest.main()
