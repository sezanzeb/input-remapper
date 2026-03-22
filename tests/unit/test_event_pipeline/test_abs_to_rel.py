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
class TestAbsToRel(EventPipelineTestBase):
    async def test_abs_to_rel(self):
        """Map gamepad EV_ABS events to EV_REL events."""

        rel_rate = 60  # rate [Hz] at which events are produced
        gain = 0.5  # halve the speed of the rel axis
        # left x to mouse x
        input_config = InputConfig(type=EV_ABS, code=ABS_X)
        mapping_config = {
            "input_combination": InputCombination([input_config]).to_config(),
            "target_uinput": "mouse",
            "output_type": EV_REL,
            "output_code": REL_X,
            "rel_rate": rel_rate,
            "gain": gain,
            "deadzone": 0,
        }
        mapping_1 = Mapping(**mapping_config)
        preset = Preset()
        preset.add(mapping_1)
        # left y to mouse y
        input_config = InputConfig(type=EV_ABS, code=ABS_Y)
        mapping_config["input_combination"] = InputCombination(
            [input_config]
        ).to_config()
        mapping_config["output_code"] = REL_Y
        mapping_2 = Mapping(**mapping_config)
        preset.add(mapping_2)

        # set input axis to 100% in order to move
        # (gain * REL_XY_SCALING) pixel per event
        x = MAX_ABS
        y = MAX_ABS

        event_reader = self.create_event_reader(preset, fixtures.gamepad)

        await self.send_events(
            [
                InputEvent.abs(ABS_X, -x),
                InputEvent.abs(ABS_Y, -y),
            ],
            event_reader,
        )
        # wait a bit more for it to sum up
        sleep = 0.5
        await asyncio.sleep(sleep)
        # stop it
        await self.send_events(
            [
                InputEvent.abs(ABS_X, 0),
                InputEvent.abs(ABS_Y, 0),
            ],
            event_reader,
        )

        mouse_history = self.global_uinputs.get_uinput("mouse").write_history

        if mouse_history[0].type == EV_ABS:
            raise AssertionError(
                "The injector probably just forwarded them unchanged"
                # possibly in addition to writing mouse events
            )

        # This varies quite a lot depending on the machines performance.
        # Face it, python is a bad choice for this.
        self.assertAlmostEqual(len(mouse_history), rel_rate * sleep * 2, delta=10)

        # those may be in arbitrary order
        expected_value = -gain * REL_XY_SCALING * (rel_rate / DEFAULT_REL_RATE)
        count_x = mouse_history.count((EV_REL, REL_X, expected_value))
        count_y = mouse_history.count((EV_REL, REL_Y, expected_value))
        self.assertGreater(count_x, 1)
        self.assertGreater(count_y, 1)
        # only those two types of events were written
        self.assertEqual(len(mouse_history), count_x + count_y)

    async def test_abs_to_wheel_hi_res_quirk(self):
        """When mapping to wheel events we always expect to see both,
        REL_WHEEL and REL_WHEEL_HI_RES events with an accumulative value ratio of 1/120
        """
        rel_rate = 60  # rate [Hz] at which events are produced
        gain = 1
        # left x to mouse x
        input_config = InputConfig(type=EV_ABS, code=ABS_X)
        mapping_config = {
            "input_combination": InputCombination([input_config]).to_config(),
            "target_uinput": "mouse",
            "output_type": EV_REL,
            "output_code": REL_WHEEL,
            "rel_rate": rel_rate,
            "gain": gain,
            "deadzone": 0,
        }
        mapping_1 = Mapping(**mapping_config)

        preset = Preset()
        preset.add(mapping_1)
        # left y to mouse y
        input_config = InputConfig(type=EV_ABS, code=ABS_Y)
        mapping_config["input_combination"] = InputCombination(
            [input_config]
        ).to_config()
        mapping_config["output_code"] = REL_HWHEEL_HI_RES
        mapping_2 = Mapping(**mapping_config)
        preset.add(mapping_2)

        # set input axis to 100% in order to move
        # speed*gain*rate=1*0.5*60 pixel per second
        x = MAX_ABS
        y = MAX_ABS

        event_reader = self.create_event_reader(preset, fixtures.gamepad)

        await self.send_events(
            [
                InputEvent.abs(ABS_X, x),
                InputEvent.abs(ABS_Y, -y),
            ],
            event_reader,
        )
        # wait a bit more for it to sum up
        sleep = 0.8
        await asyncio.sleep(sleep)
        # stop it
        await self.send_events(
            [
                InputEvent.abs(ABS_X, 0),
                InputEvent.abs(ABS_Y, 0),
            ],
            event_reader,
        )
        m_history = self.global_uinputs.get_uinput("mouse").write_history

        rel_wheel = sum([event.value for event in m_history if event.code == REL_WHEEL])
        rel_wheel_hi_res = sum(
            [event.value for event in m_history if event.code == REL_WHEEL_HI_RES]
        )
        rel_hwheel = sum(
            [event.value for event in m_history if event.code == REL_HWHEEL]
        )
        rel_hwheel_hi_res = sum(
            [event.value for event in m_history if event.code == REL_HWHEEL_HI_RES]
        )

        self.assertAlmostEqual(rel_wheel, rel_wheel_hi_res / 120, places=0)
        self.assertAlmostEqual(rel_hwheel, rel_hwheel_hi_res / 120, places=0)


if __name__ == "__main__":
    unittest.main()
