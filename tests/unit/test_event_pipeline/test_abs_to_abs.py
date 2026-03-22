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
from tests.lib.fixtures import Fixture, fixtures
from tests.lib.pipes import uinput_write_history
from tests.lib.test_setup import test_setup
from tests.unit.test_event_pipeline.event_pipeline_test_base import (
    EventPipelineTestBase,
)


@test_setup
class TestAbsToAbs(EventPipelineTestBase):
    async def test_abs_to_abs(self):
        gain = 0.5
        # left x to mouse x
        input_config = InputConfig(type=EV_ABS, code=ABS_X)
        mapping_config = {
            "input_combination": InputCombination([input_config]).to_config(),
            "target_uinput": "gamepad",
            "output_type": EV_ABS,
            "output_code": ABS_X,
            "gain": gain,
            "deadzone": 0,
        }
        mapping_1 = Mapping(**mapping_config)
        preset = Preset()
        preset.add(mapping_1)
        input_config = InputConfig(type=EV_ABS, code=ABS_Y)
        mapping_config["input_combination"] = InputCombination(
            [input_config]
        ).to_config()
        mapping_config["output_code"] = ABS_Y
        mapping_2 = Mapping(**mapping_config)
        preset.add(mapping_2)

        x = fixtures.gamepad.max_abs
        y = fixtures.gamepad.max_abs

        event_reader = self.create_event_reader(preset, fixtures.gamepad)

        await self.send_events(
            [
                InputEvent.abs(ABS_X, -x),
                InputEvent.abs(ABS_Y, y),
            ],
            event_reader,
        )

        await asyncio.sleep(0.2)

        history = self.global_uinputs.get_uinput("gamepad").write_history
        self.assertEqual(
            history,
            [
                InputEvent.from_tuple((3, 0, fixtures.gamepad.min_abs / 2)),
                InputEvent.from_tuple((3, 1, fixtures.gamepad.max_abs / 2)),
            ],
        )

    async def test_abs_to_abs_with_input_switch(self):
        gain = 0.5
        input_combination = InputCombination(
            (
                InputConfig(type=EV_ABS, code=0),
                InputConfig(type=EV_ABS, code=1, analog_threshold=10),
            )
        )
        # left x to mouse x
        mapping_config = {
            "input_combination": input_combination.to_config(),
            "target_uinput": "gamepad",
            "output_type": EV_ABS,
            "output_code": ABS_X,
            "gain": gain,
            "deadzone": 0,
        }
        mapping_1 = Mapping(**mapping_config)
        preset = Preset()
        preset.add(mapping_1)

        x = fixtures.gamepad.max_abs
        y = fixtures.gamepad.max_abs

        event_reader = self.create_event_reader(preset, fixtures.gamepad)

        await self.send_events(
            [
                InputEvent.abs(ABS_X, -x // 5),  # will not map
                InputEvent.abs(ABS_X, -x),  # will map later
                # switch axis on sends initial position (previous event)
                InputEvent.abs(ABS_Y, y),
                InputEvent.abs(ABS_X, x),  # normally mapped
                InputEvent.abs(ABS_Y, y // 15),  # off, re-centers axis
                InputEvent.abs(ABS_X, -x // 5),  # will not map
            ],
            event_reader,
        )

        await asyncio.sleep(0.2)

        history = self.global_uinputs.get_uinput("gamepad").write_history
        self.assertEqual(
            history,
            [
                InputEvent.from_tuple((3, 0, fixtures.gamepad.min_abs / 2)),
                InputEvent.from_tuple((3, 0, fixtures.gamepad.max_abs / 2)),
                InputEvent.from_tuple((3, 0, 0)),
            ],
        )


if __name__ == "__main__":
    unittest.main()
