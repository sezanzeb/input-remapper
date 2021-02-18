#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@hip70890b.de>
#
# This file is part of key-mapper.
#
# key-mapper is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# key-mapper is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with key-mapper.  If not, see <https://www.gnu.org/licenses/>.


import unittest

from keymapper.injection.context import Context
from keymapper.mapping import Mapping
from keymapper.key import Key
from keymapper.config import NONE, MOUSE, WHEEL, BUTTONS
from keymapper.state import system_mapping


class TestContext(unittest.TestCase):
    def setUp(self):
        self.mapping = Mapping()
        self.mapping.set('gamepad.joystick.left_purpose', WHEEL)
        self.mapping.set('gamepad.joystick.right_purpose', WHEEL)
        self.mapping.change(Key(1, 31, 1), 'k(a)')
        self.mapping.change(Key(1, 32, 1), 'b')
        self.mapping.change(Key((1, 33, 1), (1, 34, 1), (1, 35, 1)), 'c')
        self.context = Context(self.mapping)

    def test_update_purposes(self):
        self.mapping.set('gamepad.joystick.left_purpose', BUTTONS)
        self.mapping.set('gamepad.joystick.right_purpose', MOUSE)
        self.context.update_purposes()
        self.assertEqual(self.context.left_purpose, BUTTONS)
        self.assertEqual(self.context.right_purpose, MOUSE)

    def test_parse_macros(self):
        self.assertEqual(len(self.context.macros), 1)
        self.assertEqual(self.context.macros[((1, 31, 1),)].code, 'k(a)')

    def test_map_keys_to_codes(self):
        b = system_mapping.get('b')
        c = system_mapping.get('c')
        self.assertEqual(len(self.context.key_to_code), 3)
        self.assertEqual(self.context.key_to_code[((1, 32, 1),)], b)
        self.assertEqual(self.context.key_to_code[(1, 33, 1), (1, 34, 1), (1, 35, 1)], c)
        self.assertEqual(self.context.key_to_code[(1, 34, 1), (1, 33, 1), (1, 35, 1)], c)

    def test_is_mapped(self):
        self.assertTrue(self.context.is_mapped(
            ((1, 32, 1),)
        ))
        self.assertTrue(self.context.is_mapped(
            ((1, 33, 1), (1, 34, 1), (1, 35, 1))
        ))
        self.assertTrue(self.context.is_mapped(
            ((1, 34, 1), (1, 33, 1), (1, 35, 1))
        ))

        self.assertFalse(self.context.is_mapped(
            ((1, 34, 1), (1, 35, 1), (1, 33, 1))
        ))
        self.assertFalse(self.context.is_mapped(
            ((1, 36, 1),)
        ))

    def test_forwards_joystick(self):
        self.assertFalse(self.context.forwards_joystick())
        self.mapping.set('gamepad.joystick.left_purpose', NONE)
        self.mapping.set('gamepad.joystick.right_purpose', BUTTONS)
        self.assertFalse(self.context.forwards_joystick())

        # I guess the whole purpose of update_purposes is that the config
        # doesn't need to get resolved many times during operation
        self.context.update_purposes()
        self.assertTrue(self.context.forwards_joystick())

    def test_maps_joystick(self):
        self.assertTrue(self.context.maps_joystick())
        self.mapping.set('gamepad.joystick.left_purpose', NONE)
        self.mapping.set('gamepad.joystick.right_purpose', NONE)
        self.context.update_purposes()
        self.assertFalse(self.context.maps_joystick())

    def test_joystick_as_mouse(self):
        self.assertTrue(self.context.maps_joystick())

        self.mapping.set('gamepad.joystick.right_purpose', MOUSE)
        self.context.update_purposes()
        self.assertTrue(self.context.joystick_as_mouse())

        self.mapping.set('gamepad.joystick.left_purpose', NONE)
        self.mapping.set('gamepad.joystick.right_purpose', NONE)
        self.context.update_purposes()
        self.assertFalse(self.context.joystick_as_mouse())

        self.mapping.set('gamepad.joystick.right_purpose', BUTTONS)
        self.context.update_purposes()
        self.assertFalse(self.context.joystick_as_mouse())

    def test_writes_keys(self):
        self.assertTrue(self.context.writes_keys())
        self.assertFalse(Context(Mapping()).writes_keys())


if __name__ == "__main__":
    unittest.main()
