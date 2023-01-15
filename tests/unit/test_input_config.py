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

from inputremapper.configs.input_config import InputCombination, InputConfig
from tests.lib.fixtures import get_combination_config


class TestInputConfig(unittest.TestCase):
    def test_input_config(self):
        test_cases = [
            # basic test, nothing fancy here
            {
                "input": {
                    "type": EV_KEY,
                    "code": KEY_A,
                    "origin_hash": "foo",
                },
                "properties": {
                    "type": EV_KEY,
                    "code": KEY_A,
                    "origin_hash": "foo",
                    "input_match_hash": (EV_KEY, KEY_A, "foo"),
                    "defines_analog_input": False,
                    "type_and_code": (EV_KEY, KEY_A),
                },
                "methods": [
                    {
                        "name": "description",
                        "args": (),
                        "kwargs": {},
                        "return": "a",
                    },
                    {
                        "name": "__hash__",
                        "args": (),
                        "kwargs": {},
                        "return": hash((EV_KEY, KEY_A, "foo", None)),
                    },
                ],
            },
            # removes analog_threshold
            {
                "input": {
                    "type": EV_KEY,
                    "code": KEY_A,
                    "origin_hash": "foo",
                    "analog_threshold": 10,
                },
                "properties": {
                    "type": EV_KEY,
                    "code": KEY_A,
                    "origin_hash": "foo",
                    "analog_threshold": None,
                    "input_match_hash": (EV_KEY, KEY_A, "foo"),
                    "defines_analog_input": False,
                    "type_and_code": (EV_KEY, KEY_A),
                },
                "methods": [
                    {
                        "name": "description",
                        "args": (),
                        "kwargs": {},
                        "return": "a",
                    },
                    {
                        "name": "__hash__",
                        "args": (),
                        "kwargs": {},
                        "return": hash((EV_KEY, KEY_A, "foo", None)),
                    },
                ],
            },
            # abs to btn
            {
                "input": {
                    "type": EV_ABS,
                    "code": ABS_X,
                    "origin_hash": "foo",
                    "analog_threshold": 10,
                },
                "properties": {
                    "type": EV_ABS,
                    "code": ABS_X,
                    "origin_hash": "foo",
                    "analog_threshold": 10,
                    "input_match_hash": (EV_ABS, ABS_X, "foo"),
                    "defines_analog_input": False,
                    "type_and_code": (EV_ABS, ABS_X),
                },
                "methods": [
                    {
                        "name": "description",
                        "args": (),
                        "kwargs": {},
                        "return": "Joystick-X Right 10%",
                    },
                    {
                        "name": "description",
                        "args": (),
                        "kwargs": {"exclude_threshold": True},
                        "return": "Joystick-X Right",
                    },
                    {
                        "name": "description",
                        "args": (),
                        "kwargs": {
                            "exclude_threshold": True,
                            "exclude_direction": True,
                        },
                        "return": "Joystick-X",
                    },
                    {
                        "name": "__hash__",
                        "args": (),
                        "kwargs": {},
                        "return": hash((EV_ABS, ABS_X, "foo", 10)),
                    },
                ],
            },
            # abs to btn with d-pad
            {
                "input": {
                    "type": EV_ABS,
                    "code": ABS_HAT0Y,
                    "origin_hash": "foo",
                    "analog_threshold": 10,
                },
                "properties": {
                    "type": EV_ABS,
                    "code": ABS_HAT0Y,
                    "origin_hash": "foo",
                    "analog_threshold": 10,
                    "input_match_hash": (EV_ABS, ABS_HAT0Y, "foo"),
                    "defines_analog_input": False,
                    "type_and_code": (EV_ABS, ABS_HAT0Y),
                },
                "methods": [
                    {
                        "name": "description",
                        "args": (),
                        "kwargs": {},
                        "return": "DPad-Y Down 10%",
                    },
                    {
                        "name": "__hash__",
                        "args": (),
                        "kwargs": {},
                        "return": hash((EV_ABS, ABS_HAT0Y, "foo", 10)),
                    },
                ],
            },
            # rel to btn
            {
                "input": {
                    "type": EV_REL,
                    "code": REL_Y,
                    "origin_hash": "foo",
                    "analog_threshold": 10,
                },
                "properties": {
                    "type": EV_REL,
                    "code": REL_Y,
                    "origin_hash": "foo",
                    "analog_threshold": 10,
                    "input_match_hash": (EV_REL, REL_Y, "foo"),
                    "defines_analog_input": False,
                    "type_and_code": (EV_REL, REL_Y),
                },
                "methods": [
                    {
                        "name": "description",
                        "args": (),
                        "kwargs": {},
                        "return": "Y Down 10",
                    },
                    {
                        "name": "__hash__",
                        "args": (),
                        "kwargs": {},
                        "return": hash((EV_REL, REL_Y, "foo", 10)),
                    },
                ],
            },
            # abs as axis
            {
                "input": {
                    "type": EV_ABS,
                    "code": ABS_X,
                    "origin_hash": "foo",
                    "analog_threshold": 0,
                },
                "properties": {
                    "type": EV_ABS,
                    "code": ABS_X,
                    "origin_hash": "foo",
                    "analog_threshold": None,
                    "input_match_hash": (EV_ABS, ABS_X, "foo"),
                    "defines_analog_input": True,
                    "type_and_code": (EV_ABS, ABS_X),
                },
                "methods": [
                    {
                        "name": "description",
                        "args": (),
                        "kwargs": {},
                        "return": "Joystick-X",
                    },
                    {
                        "name": "description",
                        "args": (),
                        "kwargs": {
                            "exclude_threshold": True,
                            "exclude_direction": True,
                        },
                        "return": "Joystick-X",
                    },
                    {
                        "name": "__hash__",
                        "args": (),
                        "kwargs": {},
                        "return": hash((EV_ABS, ABS_X, "foo", None)),
                    },
                ],
            },
            # rel as axis
            {
                "input": {
                    "type": EV_REL,
                    "code": REL_WHEEL,
                    "origin_hash": "foo",
                },
                "properties": {
                    "type": EV_REL,
                    "code": REL_WHEEL,
                    "origin_hash": "foo",
                    "analog_threshold": None,
                    "input_match_hash": (EV_REL, REL_WHEEL, "foo"),
                    "defines_analog_input": True,
                    "type_and_code": (EV_REL, REL_WHEEL),
                },
                "methods": [
                    {
                        "name": "description",
                        "args": (),
                        "kwargs": {},
                        "return": "Wheel",
                    },
                    {
                        "name": "__hash__",
                        "args": (),
                        "kwargs": {},
                        "return": hash((EV_REL, REL_WHEEL, "foo", None)),
                    },
                ],
            },
        ]
        for test_case in test_cases:
            input_config = InputConfig(**test_case["input"])
            for property_, value in test_case["properties"].items():
                self.assertEqual(
                    value,
                    getattr(input_config, property_),
                    f"property mismatch for input: {test_case['input']} "
                    f"property: {property_} expected value: {value}",
                )
            for method in test_case["methods"]:
                self.assertEqual(
                    method["return"],
                    getattr(input_config, method["name"])(
                        *method["args"], **method["kwargs"]
                    ),
                    f"wrong method return for input: {test_case['input']} "
                    f"method: {method}",
                )

    def test_is_immutable(self):
        input_config = InputConfig(type=1, code=2)
        with self.assertRaises(TypeError):
            input_config.origin_hash = "foo"


class TestInputCombination(unittest.TestCase):
    def test_eq(self):
        a = InputCombination(
            [
                InputConfig(type=EV_REL, code=REL_X, value=1, origin_hash="1234"),
                InputConfig(type=EV_KEY, code=KEY_A, value=1, origin_hash="abcd"),
            ]
        )
        b = InputCombination(
            [
                InputConfig(type=EV_REL, code=REL_X, value=1, origin_hash="1234"),
                InputConfig(type=EV_KEY, code=KEY_A, value=1, origin_hash="abcd"),
            ]
        )
        self.assertEqual(a, b)

    def test_not_eq(self):
        a = InputCombination(
            [
                InputConfig(type=EV_REL, code=REL_X, value=1, origin_hash="2345"),
                InputConfig(type=EV_KEY, code=KEY_A, value=1, origin_hash="bcde"),
            ]
        )
        b = InputCombination(
            [
                InputConfig(type=EV_REL, code=REL_X, value=1, origin_hash="1234"),
                InputConfig(type=EV_KEY, code=KEY_A, value=1, origin_hash="abcd"),
            ]
        )
        self.assertNotEqual(a, b)

    def test_can_be_used_as_dict_key(self):
        dict_ = {
            InputCombination(
                [
                    InputConfig(type=EV_REL, code=REL_X, value=1, origin_hash="1234"),
                    InputConfig(type=EV_KEY, code=KEY_A, value=1, origin_hash="abcd"),
                ]
            ): "foo"
        }
        key = InputCombination(
            [
                InputConfig(type=EV_REL, code=REL_X, value=1, origin_hash="1234"),
                InputConfig(type=EV_KEY, code=KEY_A, value=1, origin_hash="abcd"),
            ]
        )
        self.assertEqual(dict_.get(key), "foo")

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
        InputCombination([InputConfig(type=1, code=2, analog_threshold=3)])
        InputCombination(
            (
                {"type": 1, "code": 2},
                {"type": "1", "code": "2"},
                InputConfig(type=1, code=2),
            )
        )

    def test_to_config(self):
        c1 = InputCombination([InputConfig(type=1, code=2, analog_threshold=3)])
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
