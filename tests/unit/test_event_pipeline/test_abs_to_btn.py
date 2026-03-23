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
)

from inputremapper.configs.mapping import (
    Mapping,
)
from inputremapper.configs.preset import Preset
from inputremapper.configs.keyboard_layout import keyboard_layout
from inputremapper.configs.input_config import InputCombination, InputConfig
from inputremapper.input_event import InputEvent
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

    async def test_abs_trigger_threshold(self):
        """Test that different activation points for abs_to_btn work correctly."""

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

        await self.send_events(
            [
                # 80%, trigger b
                InputEvent.abs(ABS_X, int(fixtures.gamepad.max_abs * 0.8)),
                InputEvent.abs(ABS_X, fixtures.gamepad.max_abs // 2),  # 50%, release b
            ],
            event_reader,
        )
        keyboard_history = self.global_uinputs.get_uinput("keyboard").write_history
        self.assertEqual(keyboard_history.count((EV_KEY, a, 1)), 1)
        self.assertEqual(keyboard_history.count((EV_KEY, b, 1)), 1)
        self.assertEqual(keyboard_history.count((EV_KEY, b, 0)), 1)
        self.assertNotIn((EV_KEY, a, 0), keyboard_history)

        # 0% release a
        await event_reader.handle(InputEvent.abs(ABS_X, 0))
        keyboard_history = self.global_uinputs.get_uinput("keyboard").write_history
        forwarded_history = self.forward_uinput.write_history
        self.assertEqual(keyboard_history.count((EV_KEY, a, 0)), 1)
        self.assertEqual(len(forwarded_history), 0)


if __name__ == "__main__":
    unittest.main()
