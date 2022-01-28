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


import unittest

from inputremapper.injection.context import Context
from inputremapper.configs.preset import Preset
from inputremapper.event_combination import EventCombination
from inputremapper.configs.global_config import NONE, MOUSE, WHEEL, BUTTONS
from inputremapper.configs.system_mapping import system_mapping
from tests.test import quick_cleanup


class TestContext(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        quick_cleanup()

    def setUp(self):
        self.mapping = Preset()
        self.mapping.set("gamepad.joystick.left_purpose", WHEEL)
        self.mapping.set("gamepad.joystick.right_purpose", WHEEL)
        self.mapping.change(EventCombination([1, 31, 1]), "keyboard", "k(a)")
        self.mapping.change(EventCombination([1, 32, 1]), "keyboard", "b")
        self.mapping.change(EventCombination((1, 33, 1), (1, 34, 1), (1, 35, 1)), "keyboard", "c")
        self.context = Context(self.mapping)

    def test_update_purposes(self):
        self.mapping.set("gamepad.joystick.left_purpose", BUTTONS)
        self.mapping.set("gamepad.joystick.right_purpose", MOUSE)
        self.context.update_purposes()
        self.assertEqual(self.context.left_purpose, BUTTONS)
        self.assertEqual(self.context.right_purpose, MOUSE)

    def test_parse_macros(self):
        self.assertEqual(len(self.context.macros), 1)
        self.assertEqual(self.context.macros[((1, 31, 1),)][1], "keyboard")
        self.assertEqual(self.context.macros[((1, 31, 1),)][0].code, "k(a)")

    def test_map_keys_to_codes(self):
        b = system_mapping.get("b")
        c = system_mapping.get("c")
        self.assertEqual(len(self.context.key_to_code), 3)
        self.assertEqual(self.context.key_to_code[((1, 32, 1),)], (b, "keyboard"))
        self.assertEqual(
            self.context.key_to_code[(1, 33, 1), (1, 34, 1), (1, 35, 1)],
            (c, "keyboard"),
        )
        self.assertEqual(
            self.context.key_to_code[(1, 34, 1), (1, 33, 1), (1, 35, 1)],
            (c, "keyboard"),
        )

    def test_is_mapped(self):
        self.assertTrue(self.context.is_mapped(((1, 32, 1),)))
        self.assertTrue(self.context.is_mapped(((1, 33, 1), (1, 34, 1), (1, 35, 1))))
        self.assertTrue(self.context.is_mapped(((1, 34, 1), (1, 33, 1), (1, 35, 1))))

        self.assertFalse(self.context.is_mapped(((1, 34, 1), (1, 35, 1), (1, 33, 1))))
        self.assertFalse(self.context.is_mapped(((1, 36, 1),)))

    def test_maps_joystick(self):
        self.assertTrue(self.context.maps_joystick())
        self.mapping.set("gamepad.joystick.left_purpose", NONE)
        self.mapping.set("gamepad.joystick.right_purpose", NONE)
        self.context.update_purposes()
        self.assertFalse(self.context.maps_joystick())

    def test_joystick_as_dpad(self):
        self.assertTrue(self.context.maps_joystick())

        self.mapping.set("gamepad.joystick.left_purpose", WHEEL)
        self.mapping.set("gamepad.joystick.right_purpose", MOUSE)
        self.context.update_purposes()
        self.assertFalse(self.context.joystick_as_dpad())

        self.mapping.set("gamepad.joystick.left_purpose", BUTTONS)
        self.mapping.set("gamepad.joystick.right_purpose", NONE)
        self.context.update_purposes()
        self.assertTrue(self.context.joystick_as_dpad())

        self.mapping.set("gamepad.joystick.left_purpose", MOUSE)
        self.mapping.set("gamepad.joystick.right_purpose", BUTTONS)
        self.context.update_purposes()
        self.assertTrue(self.context.joystick_as_dpad())

    def test_joystick_as_mouse(self):
        self.assertTrue(self.context.maps_joystick())

        self.mapping.set("gamepad.joystick.right_purpose", MOUSE)
        self.context.update_purposes()
        self.assertTrue(self.context.joystick_as_mouse())

        self.mapping.set("gamepad.joystick.left_purpose", NONE)
        self.mapping.set("gamepad.joystick.right_purpose", NONE)
        self.context.update_purposes()
        self.assertFalse(self.context.joystick_as_mouse())

        self.mapping.set("gamepad.joystick.right_purpose", BUTTONS)
        self.context.update_purposes()
        self.assertFalse(self.context.joystick_as_mouse())

    def test_writes_keys(self):
        self.assertTrue(self.context.writes_keys())
        self.assertFalse(Context(Preset()).writes_keys())


if __name__ == "__main__":
    unittest.main()
