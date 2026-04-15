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

import unittest

from evdev.ecodes import (
    EV_KEY,
    EV_ABS,
    ABS_X,
    ABS_Z
)

from inputremapper.configs.mapping import (
    Mapping,
)
from inputremapper.configs.preset import Preset
from inputremapper.configs.keyboard_layout import keyboard_layout
from inputremapper.configs.input_config import InputCombination, InputConfig
from inputremapper.input_event import InputEvent
from tests.lib.logger import logger
from tests.lib.fixtures import fixtures
from tests.lib.test_setup import test_setup
from tests.unit.test_event_pipeline.event_pipeline_test_base import (
    EventPipelineTestBase,
)


@test_setup
class TestAbsToBtn(EventPipelineTestBase):
    async def test_abs_trigger_threshold_simple(self):
        # at 30% map to a
        mapping_1 = Mapping.from_combination(
            InputCombination(
                [InputConfig(type=EV_ABS, code=ABS_X, analog_threshold=30)]
            ),
            output_symbol="a",
        )
        preset = Preset()
        preset.add(mapping_1)
        a_code = keyboard_layout.get("a")
        event_reader = self.create_event_reader(preset, fixtures.gamepad)

        # 50%, trigger a
        await self.send_events(
            [InputEvent.abs(ABS_X, fixtures.gamepad.max_abs // 2)],
            event_reader,
        )

        keyboard_history = self.global_uinputs.get_uinput("keyboard").write_history
        self.assertEqual(len(keyboard_history), 1)
        self.assertEqual(keyboard_history[0], (EV_KEY, a_code, 1))
        self.assertNotIn((EV_KEY, a_code, 0), keyboard_history)

    async def test_abs_z(self):
        # Shoulder triggers (ABS_Z, ABS_RZ, ABS_GAS, ABS_BRAKE). Their center point
        # is equal to the fully released point. They only have one direction.
        fixture = fixtures.gamepad_abs_0_to_256

        # at 30% map to a
        mapping_1 = Mapping.from_combination(
            InputCombination(
                [InputConfig(type=EV_ABS, code=ABS_Z, analog_threshold=30)]
            ),
            output_symbol="a",
        )

        # This mapping is impossible. There is no negative direction.
        mapping_2 = Mapping.from_combination(
            InputCombination(
                [InputConfig(type=EV_ABS, code=ABS_Z, analog_threshold=-30)]
            ),
            output_symbol="b",
        )

        preset = Preset()
        preset.add(mapping_1)
        preset.add(mapping_2)
        a_code = keyboard_layout.get("a")
        b_code = keyboard_layout.get("b")
        event_reader = self.create_event_reader(preset, fixture)
        max_abs = fixture.max_abs

        # 50%, trigger a
        await self.send_events(
            [InputEvent.abs(ABS_Z, max_abs // 2)],
            event_reader,
        )

        keyboard_history = self.global_uinputs.get_uinput("keyboard").write_history
        self.assertEqual(keyboard_history, [(EV_KEY, a_code, 1)])

        # Lets slowly move it all the way into the other direction
        assert fixture.min_abs == 0  # just for clarification here
        await self.send_events(
            [
                InputEvent.abs(ABS_Z, max_abs // 3),
                InputEvent.abs(ABS_Z, max_abs // 5),
                InputEvent.abs(ABS_Z, max_abs // 10),
                InputEvent.abs(ABS_Z, 0),
            ],
            event_reader,
        )

        # The negative mapping (mapping_2, to b) was not triggered. It just released
        # the a.
        self.assertEqual(keyboard_history, [
            (EV_KEY, a_code, 1),
            (EV_KEY, a_code, 0)
        ])


    async def test_abs_trigger_threshold(self):
        """Test that different activation points for abs_to_btn work correctly."""
        forwarded_history = self.forward_uinput.write_history

        # at 30% map to a
        mapping_1 = Mapping.from_combination(
            InputCombination(
                [InputConfig(type=EV_ABS, code=ABS_X, analog_threshold=30)]
            ),
            output_symbol="a",
        )
        # at 70% map to b
        mapping_2 = Mapping.from_combination(
            InputCombination(
                [InputConfig(type=EV_ABS, code=ABS_X, analog_threshold=70)]
            ),
            output_symbol="b",
        )
        preset = Preset()
        preset.add(mapping_1)
        preset.add(mapping_2)

        a = keyboard_layout.get("a")
        b = keyboard_layout.get("b")

        event_reader = self.create_event_reader(preset, fixtures.gamepad)

        logger.info("do nothing, then trigger a")
        await self.send_events(
            [
                # -10%, do nothing
                InputEvent.abs(ABS_X, fixtures.gamepad.min_abs // 10),
                # 0%, do noting
                InputEvent.abs(ABS_X, 0),
                # 10%, do nothing
                InputEvent.abs(ABS_X, fixtures.gamepad.max_abs // 10),
                # 50%, trigger a
                InputEvent.abs(ABS_X, fixtures.gamepad.max_abs // 2),
            ],
            event_reader,
        )
        keyboard_history = self.global_uinputs.get_uinput("keyboard").write_history

        self.assertEqual(keyboard_history.count((EV_KEY, a, 1)), 1)
        self.assertNotIn((EV_KEY, a, 0), keyboard_history)
        self.assertNotIn((EV_KEY, b, 1), keyboard_history)
        # the negative movements are not mapped, so the one event at -10% and its
        # release should be forwarded instead
        self.assertEqual(
            forwarded_history,
            [
                (EV_ABS, ABS_X, fixtures.gamepad.min_abs // 10),
                (EV_ABS, ABS_X, 0),
            ],
        )

        logger.info("trigger b, then release b")
        await self.send_events(
            [
                # 80%, trigger b
                InputEvent.abs(ABS_X, int(fixtures.gamepad.max_abs * 0.8)),
                # 50%, release b
                InputEvent.abs(ABS_X, fixtures.gamepad.max_abs // 2),
            ],
            event_reader,
        )
        keyboard_history = self.global_uinputs.get_uinput("keyboard").write_history
        self.assertEqual(
            keyboard_history,
            [
                (EV_KEY, a, 1),
                (EV_KEY, b, 1),
                (EV_KEY, b, 0),
            ],
        )

        # 0% release a
        await event_reader.handle(InputEvent.abs(ABS_X, 0))
        keyboard_history = self.global_uinputs.get_uinput("keyboard").write_history
        self.assertEqual(
            keyboard_history,
            [
                (EV_KEY, a, 1),
                (EV_KEY, b, 1),
                (EV_KEY, b, 0),
                (EV_KEY, a, 0),
            ],
        )

        # This didn't change. ABS_X of 0 should not be forwarded, because the joystick
        # came from the mapped direction to 0. Instead, it maps to release a.
        self.assertEqual(len(forwarded_history), 2)


if __name__ == "__main__":
    unittest.main()
