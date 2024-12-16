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


import unittest
from unittest.mock import patch

from evdev.ecodes import (
    EV_KEY,
    KEY_1,
    KEY_2,
    LED_CAPSL,
    LED_NUML,
)

from inputremapper.injection.macros.parse import Parser
from tests.lib.test_setup import test_setup
from tests.unit.test_macros.macro_test_base import DummyMapping, MacroTestBase


@test_setup
class TestLeds(MacroTestBase):
    async def test_if_capslock(self):
        macro = Parser.parse(
            "if_capslock(key(KEY_1), key(KEY_2))",
            self.context,
            DummyMapping,
            True,
        )
        self.assertEqual(self.count_child_macros(macro), 2)

        with patch.object(self.source_device, "leds", side_effect=lambda: [LED_NUML]):
            await macro.run(self.handler)
            self.assertListEqual(self.result, [(EV_KEY, KEY_2, 1), (EV_KEY, KEY_2, 0)])

        with patch.object(self.source_device, "leds", side_effect=lambda: [LED_CAPSL]):
            self.result = []
            await macro.run(self.handler)
            self.assertListEqual(self.result, [(EV_KEY, KEY_1, 1), (EV_KEY, KEY_1, 0)])

    async def test_if_numlock(self):
        macro = Parser.parse(
            "if_numlock(key(KEY_1), key(KEY_2))",
            self.context,
            DummyMapping,
            True,
        )
        self.assertEqual(self.count_child_macros(macro), 2)

        with patch.object(self.source_device, "leds", side_effect=lambda: [LED_NUML]):
            await macro.run(self.handler)
            self.assertListEqual(self.result, [(EV_KEY, KEY_1, 1), (EV_KEY, KEY_1, 0)])

        with patch.object(self.source_device, "leds", side_effect=lambda: [LED_CAPSL]):
            self.result = []
            await macro.run(self.handler)
            self.assertListEqual(self.result, [(EV_KEY, KEY_2, 1), (EV_KEY, KEY_2, 0)])

    async def test_if_numlock_no_else(self):
        macro = Parser.parse(
            "if_numlock(key(KEY_1))",
            self.context,
            DummyMapping,
            True,
        )
        self.assertEqual(self.count_child_macros(macro), 1)

        with patch.object(self.source_device, "leds", side_effect=lambda: [LED_CAPSL]):
            await macro.run(self.handler)
            self.assertListEqual(self.result, [])

        with patch.object(self.source_device, "leds", side_effect=lambda: [LED_NUML]):
            self.result = []
            await macro.run(self.handler)
            self.assertListEqual(self.result, [(EV_KEY, KEY_1, 1), (EV_KEY, KEY_1, 0)])

    async def test_if_capslock_no_then(self):
        macro = Parser.parse(
            "if_capslock(None, key(KEY_1))",
            self.context,
            DummyMapping,
            True,
        )
        self.assertEqual(self.count_child_macros(macro), 1)

        with patch.object(self.source_device, "leds", side_effect=lambda: [LED_CAPSL]):
            await macro.run(self.handler)
            self.assertListEqual(self.result, [])

        with patch.object(self.source_device, "leds", side_effect=lambda: [LED_NUML]):
            self.result = []
            await macro.run(self.handler)
            self.assertListEqual(self.result, [(EV_KEY, KEY_1, 1), (EV_KEY, KEY_1, 0)])


if __name__ == "__main__":
    unittest.main()
