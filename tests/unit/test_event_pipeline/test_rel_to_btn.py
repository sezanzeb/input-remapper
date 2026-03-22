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
class TestRelToBtn(EventPipelineTestBase):
    async def test_rel_to_btn(self):
        """Rel axis mapped to buttons are automatically released if no new rel event arrives."""

        # map those two to stuff
        w_up = (EV_REL, REL_WHEEL, -1)
        hw_right = (EV_REL, REL_HWHEEL, 1)

        # should be forwarded and present in the capabilities
        hw_left = (EV_REL, REL_HWHEEL, -1)

        keyboard_layout.clear()
        code_b = 91
        code_c = 92
        keyboard_layout._set("b", code_b)
        keyboard_layout._set("c", code_c)

        # set a high release timeout to make sure the tests pass
        release_timeout = 0.2
        mapping_1 = Mapping.from_combination(
            InputCombination(InputCombination.from_tuples(hw_right)), "keyboard", "k(b)"
        )
        mapping_2 = Mapping.from_combination(
            InputCombination(InputCombination.from_tuples(w_up)), "keyboard", "c"
        )
        mapping_1.release_timeout = release_timeout
        mapping_2.release_timeout = release_timeout

        preset = Preset()
        preset.add(mapping_1)
        preset.add(mapping_2)

        event_reader = self.create_event_reader(preset, fixtures.foo_device_2_mouse)

        await self.send_events(
            [InputEvent.from_tuple(hw_right), InputEvent.from_tuple(w_up)] * 5,
            event_reader,
        )
        # wait less than the release timeout and send more events
        await asyncio.sleep(release_timeout / 5)
        await self.send_events(
            [InputEvent.from_tuple(hw_right), InputEvent.from_tuple(w_up)] * 5
            + [InputEvent.from_tuple(hw_left)]
            * 3,  # one event will release hw_right, the others are forwarded
            event_reader,
        )
        # wait more than the release_timeout to make sure all handlers finish
        await asyncio.sleep(release_timeout * 1.2)

        keyboard_history = self.global_uinputs.get_uinput("keyboard").write_history
        forwarded_history = self.forward_uinput.write_history
        self.assertEqual(keyboard_history.count((EV_KEY, code_b, 1)), 1)
        self.assertEqual(keyboard_history.count((EV_KEY, code_c, 1)), 1)
        self.assertEqual(keyboard_history.count((EV_KEY, code_b, 0)), 1)
        self.assertEqual(keyboard_history.count((EV_KEY, code_c, 0)), 1)
        # the unmapped wheel direction
        self.assertEqual(forwarded_history.count(hw_left), 2)

        # the unmapped wheel won't get a debounced release command, it's
        # forwarded as is
        self.assertNotIn((EV_REL, REL_HWHEEL, 0), forwarded_history)

    async def test_rel_trigger_threshold(self):
        """Test that different activation points for rel_to_btn work correctly."""

        # at 5 map to a
        mapping_1 = Mapping.from_combination(
            InputCombination(
                [InputConfig(type=EV_REL, code=REL_X, analog_threshold=5)]
            ),
            output_symbol="a",
        )
        # at 15 map to b
        mapping_2 = Mapping.from_combination(
            InputCombination(
                [InputConfig(type=EV_REL, code=REL_X, analog_threshold=15)]
            ),
            output_symbol="b",
        )
        release_timeout = 0.2  # give some time to do assertions before the release
        mapping_1.release_timeout = release_timeout
        mapping_2.release_timeout = release_timeout
        preset = Preset()
        preset.add(mapping_1)
        preset.add(mapping_2)

        a = keyboard_layout.get("a")
        b = keyboard_layout.get("b")

        event_reader = self.create_event_reader(preset, fixtures.foo_device_2_mouse)

        await self.send_events(
            [
                InputEvent.rel(REL_X, -5),  # forward
                InputEvent.rel(REL_X, 0),  # forward
                InputEvent.rel(REL_X, 3),  # forward
                InputEvent.rel(REL_X, 10),  # trigger a
            ],
            event_reader,
        )
        await asyncio.sleep(release_timeout * 1.5)  # release a
        keyboard_history = self.global_uinputs.get_uinput("keyboard").write_history

        self.assertEqual(keyboard_history, [(EV_KEY, a, 1), (EV_KEY, a, 0)])
        self.assertEqual(keyboard_history.count((EV_KEY, a, 1)), 1)
        self.assertEqual(keyboard_history.count((EV_KEY, a, 0)), 1)
        self.assertNotIn((EV_KEY, b, 1), keyboard_history)

        await self.send_events(
            [
                InputEvent.rel(REL_X, 10),  # trigger a
                InputEvent.rel(REL_X, 20),  # trigger b
                InputEvent.rel(REL_X, 10),  # release b
            ],
            event_reader,
        )
        keyboard_history = self.global_uinputs.get_uinput("keyboard").write_history
        self.assertEqual(keyboard_history.count((EV_KEY, a, 1)), 2)
        self.assertEqual(keyboard_history.count((EV_KEY, b, 1)), 1)
        self.assertEqual(keyboard_history.count((EV_KEY, b, 0)), 1)
        self.assertEqual(keyboard_history.count((EV_KEY, a, 0)), 1)

        await asyncio.sleep(release_timeout * 1.5)  # release a
        keyboard_history = self.global_uinputs.get_uinput("keyboard").write_history
        forwarded_history = self.forward_uinput.write_history
        self.assertEqual(keyboard_history.count((EV_KEY, a, 0)), 2)
        self.assertEqual(
            forwarded_history,
            [(EV_REL, REL_X, -5), (EV_REL, REL_X, 0), (EV_REL, REL_X, 3)],
        )


if __name__ == "__main__":
    unittest.main()
