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
from inputremapper.injection.mapping_handlers.hierarchy_handler import HierarchyHandler
from tests.test import quick_cleanup, get_key_mapping
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
from inputremapper.event_combination import EventCombination
from inputremapper.configs.mapping import Mapping


class TestContext(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        quick_cleanup()

    def test_callbacks(self):
        preset = Preset()
        cfg = {
            "event_combination": ",".join((str(EV_ABS), str(ABS_X), "0")),
            "target_uinput": "mouse",
            "output_type": EV_REL,
            "output_code": REL_HWHEEL_HI_RES,
        }
        preset.add(Mapping(**cfg))  # abs x -> wheel
        cfg["event_combination"] = ",".join((str(EV_ABS), str(ABS_Y), "0"))
        cfg["output_code"] = REL_WHEEL_HI_RES
        preset.add(Mapping(**cfg))  # abs y -> wheel

        preset.add(get_key_mapping(EventCombination((1, 31, 1)), "keyboard", "k(a)"))
        preset.add(get_key_mapping(EventCombination((1, 32, 1)), "keyboard", "b"))

        # overlapping combination for (1, 32, 1)
        preset.add(
            get_key_mapping(
                EventCombination(((1, 32, 1), (1, 33, 1), (1, 34, 1))),
                "keyboard",
                "c",
            )
        )

        # map abs x to key "b"
        preset.add(
            get_key_mapping(EventCombination([EV_ABS, ABS_X, 20]), "keyboard", "d"),
        )
        context = Context(preset)

        # expected callbacks and their lengths:
        callbacks = {
            (
                EV_ABS,
                ABS_X,
            ): 2,  # ABS_X -> "d" and ABS_X -> wheel have the same type and code
            (EV_ABS, ABS_Y): 1,
            (1, 31): 1,
            # even though we have 2 mappings with this type and code, we only expect one callback
            # because they both map to keys. We don't want to trigger two mappings with the same key press
            (1, 32): 1,
            (1, 33): 1,
            (1, 34): 1,
        }
        self.assertEqual(set(callbacks.keys()), set(context.notify_callbacks.keys()))
        for key, val in callbacks.items():
            self.assertEqual(val, len(context.notify_callbacks[key]))

        # 7 unique input events in the preset
        self.assertEqual(7, len(context._handlers))


if __name__ == "__main__":
    unittest.main()
