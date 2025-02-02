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

from evdev._ecodes import KEY_B, KEY_C
from evdev.ecodes import (
    EV_KEY,
    EV_ABS,
    EV_REL,
    ABS_X,
    ABS_Y,
    REL_X,
    REL_Y,
    KEY_A,
)

from inputremapper.configs.input_config import InputCombination, InputConfig
from inputremapper.configs.mapping import (
    Mapping,
    REL_XY_SCALING,
    DEFAULT_REL_RATE,
)
from inputremapper.configs.preset import Preset
from inputremapper.input_event import InputEvent
from tests.lib.constants import MAX_ABS, MIN_ABS
from tests.lib.fixtures import fixtures
from tests.lib.test_setup import test_setup
from tests.unit.test_event_pipeline.test_event_pipeline import EventPipelineTestBase


@test_setup
class TestRelToAbs(EventPipelineTestBase):
    def setUp(self):
        self.timestamp = 0
        super().setUp()

    def next_usec_time(self):
        self.timestamp += 1000000 / DEFAULT_REL_RATE
        return self.timestamp

    async def test_rel_to_abs(self):
        # first mapping
        # left mouse x to abs x
        gain = 0.5
        cutoff = 2
        input_combination = InputCombination([InputConfig(type=EV_REL, code=REL_X)])
        mapping_config = {
            "input_combination": input_combination.to_config(),
            "target_uinput": "gamepad",
            "output_type": EV_ABS,
            "output_code": ABS_X,
            "gain": gain,
            "rel_to_abs_input_cutoff": cutoff,
            "release_timeout": 0.5,
            "deadzone": 0,
        }
        mapping_1 = Mapping(**mapping_config)
        preset = Preset()
        preset.add(mapping_1)

        # second mapping
        input_combination = InputCombination([InputConfig(type=EV_REL, code=REL_Y)])
        mapping_config["input_combination"] = input_combination.to_config()
        mapping_config["output_code"] = ABS_Y
        mapping_2 = Mapping(**mapping_config)
        preset.add(mapping_2)

        event_reader = self.create_event_reader(preset, fixtures.gamepad)

        next_time = self.next_usec_time()
        await self.send_events(
            [
                InputEvent(0, next_time, EV_REL, REL_X, -int(REL_XY_SCALING * cutoff)),
                InputEvent(0, next_time, EV_REL, REL_Y, int(REL_XY_SCALING * cutoff)),
            ],
            event_reader,
        )

        await asyncio.sleep(0.1)

        history = self.global_uinputs.get_uinput("gamepad").write_history
        self.assertEqual(
            history,
            [
                InputEvent.from_tuple((3, 0, MIN_ABS / 2)),
                InputEvent.from_tuple((3, 1, MAX_ABS / 2)),
            ],
        )

        # send more events, then wait until the release timeout
        next_time = self.next_usec_time()
        await self.send_events(
            [
                InputEvent(0, next_time, EV_REL, REL_X, -int(REL_XY_SCALING)),
                InputEvent(0, next_time, EV_REL, REL_Y, int(REL_XY_SCALING)),
            ],
            event_reader,
        )
        await asyncio.sleep(0.7)
        history = self.global_uinputs.get_uinput("gamepad").write_history
        self.assertEqual(
            history,
            [
                InputEvent.from_tuple((3, 0, MIN_ABS / 2)),
                InputEvent.from_tuple((3, 1, MAX_ABS / 2)),
                InputEvent.from_tuple((3, 0, MIN_ABS / 4)),
                InputEvent.from_tuple((3, 1, MAX_ABS / 4)),
                InputEvent.from_tuple((3, 0, 0)),
                InputEvent.from_tuple((3, 1, 0)),
            ],
        )

    async def test_rel_to_abs_reset_multiple(self):
        # Recenters correctly when triggering the mapping a second time.
        # Could only be reproduced if a key input is part of the combination, that is
        # released and pressed again.

        # left mouse x to abs x
        gain = 0.5
        cutoff = 2
        input_combination = InputCombination(
            [
                InputConfig(type=EV_KEY, code=KEY_A),
                InputConfig(type=EV_REL, code=REL_X),
            ]
        )
        mapping_1 = Mapping(
            input_combination=input_combination.to_config(),
            target_uinput="gamepad",
            output_type=EV_ABS,
            output_code=ABS_X,
            gain=gain,
            rel_to_abs_input_cutoff=cutoff,
            release_timeout=0.1,
            deadzone=0,
        )
        preset = Preset()
        preset.add(mapping_1)

        event_reader = self.create_event_reader(preset, fixtures.gamepad)

        for _ in range(3):
            next_time = self.next_usec_time()
            value = int(REL_XY_SCALING * cutoff)
            await event_reader.handle(InputEvent(0, next_time, EV_KEY, KEY_A, 1))
            await event_reader.handle(InputEvent(0, next_time, EV_REL, REL_X, value))
            await asyncio.sleep(0.2)

            history = self.global_uinputs.get_uinput("gamepad").write_history
            self.assertIn(
                InputEvent.from_tuple((3, 0, 0)),
                history,
            )

            await event_reader.handle(InputEvent(0, next_time, EV_KEY, KEY_A, 0))
            await asyncio.sleep(0.05)

            self.global_uinputs.get_uinput("gamepad").write_history = []

    async def test_rel_to_abs_with_input_switch(self):
        # use 0 everywhere, because that will cause the handler to not update the rate,
        # and we are able to test things without worrying about that at all
        timestamp = 0

        gain = 0.5
        cutoff = 1
        input_combination = InputCombination(
            (
                InputConfig(type=EV_REL, code=REL_X),
                InputConfig(type=EV_REL, code=REL_Y, analog_threshold=10),
            )
        )
        # left mouse x to x
        mapping_1 = Mapping(
            input_combination=input_combination.to_config(),
            target_uinput="gamepad",
            output_type=EV_ABS,
            output_code=ABS_X,
            gain=gain,
            rel_to_abs_input_cutoff=cutoff,
            deadzone=0,
        )
        preset = Preset()
        preset.add(mapping_1)

        event_reader = self.create_event_reader(preset, fixtures.gamepad)

        # if the cutoff is higher, the test sends higher values to overcome the cutoff
        await self.send_events(
            [
                # will not map
                InputEvent(0, timestamp, EV_REL, REL_X, -REL_XY_SCALING / 4 * cutoff),
                # switch axis on
                InputEvent(0, timestamp, EV_REL, REL_Y, REL_XY_SCALING / 5 * cutoff),
                # normally mapped
                InputEvent(0, timestamp, EV_REL, REL_X, REL_XY_SCALING * cutoff),
                # off, re-centers axis
                InputEvent(0, timestamp, EV_REL, REL_Y, REL_XY_SCALING / 20 * cutoff),
                # will not map
                InputEvent(0, timestamp, EV_REL, REL_X, REL_XY_SCALING / 2 * cutoff),
            ],
            event_reader,
        )

        await asyncio.sleep(0.2)

        history = self.global_uinputs.get_uinput("gamepad").write_history
        self.assertEqual(
            history,
            [
                InputEvent.from_tuple((3, 0, MAX_ABS / 2)),
                InputEvent.from_tuple((3, 0, 0)),
            ],
        )
