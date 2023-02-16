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
from inputremapper.input_event import InputEvent
from tests.lib.cleanup import quick_cleanup
from evdev.ecodes import (
    EV_REL,
    EV_ABS,
    ABS_X,
    ABS_Y,
    REL_WHEEL_HI_RES,
    REL_HWHEEL_HI_RES,
)
import unittest

from inputremapper.injection.context import Context
from inputremapper.configs.preset import Preset
from inputremapper.configs.mapping import Mapping
from inputremapper.configs.input_config import InputConfig, InputCombination


class TestContext(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        quick_cleanup()

    def test_callbacks(self):
        preset = Preset()
        cfg = {
            "input_combination": InputCombination.from_tuples((EV_ABS, ABS_X)),
            "target_uinput": "mouse",
            "output_type": EV_REL,
            "output_code": REL_HWHEEL_HI_RES,
        }
        preset.add(Mapping(**cfg))  # abs x -> wheel
        cfg["input_combination"] = InputCombination.from_tuples((EV_ABS, ABS_Y))
        cfg["output_code"] = REL_WHEEL_HI_RES
        preset.add(Mapping(**cfg))  # abs y -> wheel

        preset.add(
            Mapping.from_combination(
                InputCombination.from_tuples((1, 31)), "keyboard", "k(a)"
            )
        )
        preset.add(
            Mapping.from_combination(
                InputCombination.from_tuples((1, 32)), "keyboard", "b"
            )
        )

        # overlapping combination for (1, 32, 1)
        preset.add(
            Mapping.from_combination(
                InputCombination.from_tuples((1, 32), (1, 33), (1, 34)),
                "keyboard",
                "c",
            )
        )

        # map abs x to key "b"
        preset.add(
            Mapping.from_combination(
                InputCombination.from_tuples((EV_ABS, ABS_X, 20)),
                "keyboard",
                "d",
            ),
        )

        context = Context(preset, {}, {})

        expected_num_callbacks = {
            # ABS_X -> "d" and ABS_X -> wheel have the same type and code
            InputEvent.abs(ABS_X, 1): 2,
            InputEvent.abs(ABS_Y, 1): 1,
            InputEvent.key(31, 1): 1,
            # even though we have 2 mappings with this type and code, we only expect
            # one callback because they both map to keys. We don't want to trigger two
            # mappings with the same key press
            InputEvent.key(32, 1): 1,
            InputEvent.key(33, 1): 1,
            InputEvent.key(34, 1): 1,
        }

        self.assertEqual(
            set([event.input_match_hash for event in expected_num_callbacks.keys()]),
            set(context._notify_callbacks.keys()),
        )
        for input_event, num_callbacks in expected_num_callbacks.items():
            self.assertEqual(
                num_callbacks,
                len(context.get_notify_callbacks(input_event)),
            )

        # 7 unique input events in the preset
        self.assertEqual(7, len(context._handlers))


if __name__ == "__main__":
    unittest.main()
