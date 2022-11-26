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

from evdev.ecodes import (
    EV_KEY,
    EV_ABS,
    EV_REL,
    BTN_C,
    BTN_B,
    BTN_A,
    BTN_MIDDLE,
    REL_X,
    REL_Y,
    REL_WHEEL,
    REL_HWHEEL,
    ABS_RY,
    ABS_X,
    ABS_HAT0Y,
    ABS_HAT0X,
    KEY_A,
    KEY_LEFTSHIFT,
    KEY_RIGHTALT,
    KEY_LEFTCTRL,
)

from inputremapper.input_configuration import InputCombination, InputConfig
from tests.lib.fixtures import get_combination_config


class TestInputCombination(unittest.TestCase):
    def test_get_permutations(self):
        key_1 = InputCombination(get_combination_config((1, 3, 1)))
        self.assertEqual(len(key_1.get_permutations()), 1)
        self.assertEqual(key_1.get_permutations()[0], key_1)

        key_2 = InputCombination(get_combination_config((1, 3, 1), (1, 5, 1)))
        self.assertEqual(len(key_2.get_permutations()), 1)
        self.assertEqual(key_2.get_permutations()[0], key_2)

        key_3 = InputCombination(
            get_combination_config((1, 3, 1), (1, 5, 1), (1, 7, 1))
        )
        self.assertEqual(len(key_3.get_permutations()), 2)
        self.assertEqual(
            key_3.get_permutations()[0],
            InputCombination(get_combination_config((1, 3, 1), (1, 5, 1), (1, 7, 1))),
        )
        self.assertEqual(
            key_3.get_permutations()[1],
            InputCombination(get_combination_config((1, 5, 1), (1, 3, 1), (1, 7, 1))),
        )

    def test_is_problematic(self):
        key_1 = InputCombination(
            get_combination_config((1, KEY_LEFTSHIFT, 1), (1, 5, 1))
        )
        self.assertTrue(key_1.is_problematic())

        key_2 = InputCombination(
            get_combination_config((1, KEY_RIGHTALT, 1), (1, 5, 1))
        )
        self.assertTrue(key_2.is_problematic())

        key_3 = InputCombination(
            get_combination_config((1, 3, 1), (1, KEY_LEFTCTRL, 1))
        )
        self.assertTrue(key_3.is_problematic())

        key_4 = InputCombination(get_combination_config((1, 3, 1)))
        self.assertFalse(key_4.is_problematic())

        key_5 = InputCombination(get_combination_config((1, 3, 1), (1, 5, 1)))
        self.assertFalse(key_5.is_problematic())

    def test_init(self):
        self.assertRaises(TypeError, lambda: InputCombination(1))
        self.assertRaises(TypeError, lambda: InputCombination(None))
        self.assertRaises(TypeError, lambda: InputCombination([1]))
        self.assertRaises(TypeError, lambda: InputCombination((1,)))
        self.assertRaises(TypeError, lambda: InputCombination((1, 2)))
        self.assertRaises(TypeError, lambda: InputCombination("1"))
        self.assertRaises(TypeError, lambda: InputCombination("(1,2,3)"))
        self.assertRaises(
            TypeError,
            lambda: InputCombination(((1, 2, 3), (1, 2, 3), None)),
        )

        # those don't raise errors
        InputCombination(({"type": 1, "code": 2}, {"type": 1, "code": 1}))
        InputCombination(({"type": 1, "code": 2},))
        InputCombination(({"type": "1", "code": "2"},))
        InputCombination(InputConfig(type=1, code=2, analog_threshold=3))
        InputCombination(
            (
                {"type": 1, "code": 2},
                {"type": "1", "code": "2"},
                InputConfig(type=1, code=2),
            )
        )

    def test_to_config(self):
        c1 = InputCombination(InputConfig(type=1, code=2, analog_threshold=3))
        c2 = InputCombination(
            (
                InputConfig(type=1, code=2, analog_threshold=3),
                InputConfig(type=4, code=5, analog_threshold=6),
            )
        )
        # analog_threshold is removed for key events
        self.assertEqual(c1.to_config(), ({"type": 1, "code": 2},))
        self.assertEqual(
            c2.to_config(),
            ({"type": 1, "code": 2}, {"type": 4, "code": 5, "analog_threshold": 6}),
        )

    def test_beautify(self):
        # not an integration test, but I have all the selection_label tests here already
        self.assertEqual(
            InputCombination(get_combination_config((EV_KEY, KEY_A, 1))).beautify(),
            "a",
        )
        self.assertEqual(
            InputCombination(get_combination_config((EV_KEY, KEY_A, 1))).beautify(),
            "a",
        )
        self.assertEqual(
            InputCombination(
                get_combination_config((EV_ABS, ABS_HAT0Y, -1))
            ).beautify(),
            "DPad-Y Up",
        )
        self.assertEqual(
            InputCombination(get_combination_config((EV_KEY, BTN_A, 1))).beautify(),
            "Button A",
        )
        self.assertEqual(
            InputCombination(get_combination_config((EV_KEY, 1234, 1))).beautify(),
            "unknown (1, 1234)",
        )
        self.assertEqual(
            InputCombination(
                get_combination_config((EV_ABS, ABS_HAT0X, -1))
            ).beautify(),
            "DPad-X Left",
        )
        self.assertEqual(
            InputCombination(
                get_combination_config((EV_ABS, ABS_HAT0Y, -1))
            ).beautify(),
            "DPad-Y Up",
        )
        self.assertEqual(
            InputCombination(get_combination_config((EV_KEY, BTN_A, 1))).beautify(),
            "Button A",
        )
        self.assertEqual(
            InputCombination(get_combination_config((EV_ABS, ABS_X, 1))).beautify(),
            "Joystick-X Right",
        )
        self.assertEqual(
            InputCombination(get_combination_config((EV_ABS, ABS_RY, 1))).beautify(),
            "Joystick-RY Down",
        )
        self.assertEqual(
            InputCombination(
                get_combination_config((EV_REL, REL_HWHEEL, 1))
            ).beautify(),
            "Wheel Right",
        )
        self.assertEqual(
            InputCombination(
                get_combination_config((EV_REL, REL_WHEEL, -1))
            ).beautify(),
            "Wheel Down",
        )

        # combinations
        self.assertEqual(
            InputCombination(
                get_combination_config(
                    (EV_KEY, BTN_A, 1),
                    (EV_KEY, BTN_B, 1),
                    (EV_KEY, BTN_C, 1),
                ),
            ).beautify(),
            "Button A + Button B + Button C",
        )

    def test_find_analog_input_config(self):
        analog_input = InputConfig(type=EV_REL, code=REL_X)

        combination = InputCombination(
            (
                InputConfig(type=EV_KEY, code=BTN_MIDDLE),
                InputConfig(type=EV_REL, code=REL_Y, analog_threshold=1),
                analog_input,
            )
        )
        self.assertIsNone(combination.find_analog_input_config(type_=EV_ABS))
        self.assertEqual(
            combination.find_analog_input_config(type_=EV_REL), analog_input
        )
        self.assertEqual(combination.find_analog_input_config(), analog_input)

        combination = InputCombination(
            (
                InputConfig(type=EV_REL, code=REL_X, analog_threshold=1),
                InputConfig(type=EV_KEY, code=BTN_MIDDLE),
            )
        )
        self.assertIsNone(combination.find_analog_input_config(type_=EV_ABS))
        self.assertIsNone(combination.find_analog_input_config(type_=EV_REL))
        self.assertIsNone(combination.find_analog_input_config())


if __name__ == "__main__":
    unittest.main()
