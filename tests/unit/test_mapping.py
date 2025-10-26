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
from functools import partial

from evdev.ecodes import (
    EV_REL,
    REL_X,
    EV_KEY,
    REL_Y,
    REL_WHEEL,
    REL_WHEEL_HI_RES,
    KEY_1,
    KEY_ESC,
)
from pydantic import ValidationError

from inputremapper.configs.mapping import Mapping, UIMapping, MappingType
from inputremapper.configs.keyboard_layout import keyboard_layout, DISABLE_NAME
from inputremapper.configs.input_config import InputCombination, InputConfig
from inputremapper.gui.messages.message_broker import MessageType

from tests.lib.test_setup import test_setup


@test_setup
class TestMapping(unittest.IsolatedAsyncioTestCase):
    def test_init(self):
        """Test init and that defaults are set."""
        cfg = {
            "input_combination": [{"type": 1, "code": 2}],
            "target_uinput": "keyboard",
            "output_symbol": "a",
        }
        m = Mapping(**cfg)
        self.assertEqual(
            m.input_combination, InputCombination([InputConfig(type=1, code=2)])
        )
        self.assertEqual(m.target_uinput, "keyboard")
        self.assertEqual(m.output_symbol, "a")

        self.assertIsNone(m.output_code)
        self.assertIsNone(m.output_type)

        self.assertEqual(m.macro_key_sleep_ms, 0)
        self.assertEqual(m.deadzone, 0.1)
        self.assertEqual(m.gain, 1)
        self.assertEqual(m.expo, 0)
        self.assertEqual(m.rel_rate, 60)
        self.assertEqual(m.rel_to_abs_input_cutoff, 2)
        self.assertEqual(m.release_timeout, 0.05)

    def test_is_wheel_output(self):
        mapping = Mapping(
            input_combination=InputCombination([InputConfig(type=EV_REL, code=REL_X)]),
            target_uinput="keyboard",
            output_type=EV_REL,
            output_code=REL_Y,
        )
        self.assertFalse(mapping.is_wheel_output())
        self.assertFalse(mapping.is_high_res_wheel_output())

        mapping = Mapping(
            input_combination=InputCombination([InputConfig(type=EV_REL, code=REL_X)]),
            target_uinput="keyboard",
            output_type=EV_REL,
            output_code=REL_WHEEL,
        )
        self.assertTrue(mapping.is_wheel_output())
        self.assertFalse(mapping.is_high_res_wheel_output())

        mapping = Mapping(
            input_combination=InputCombination([InputConfig(type=EV_REL, code=REL_X)]),
            target_uinput="keyboard",
            output_type=EV_REL,
            output_code=REL_WHEEL_HI_RES,
        )
        self.assertFalse(mapping.is_wheel_output())
        self.assertTrue(mapping.is_high_res_wheel_output())

    def test_get_output_type_code(self):
        cfg = {
            "input_combination": [{"type": 1, "code": 2}],
            "target_uinput": "keyboard",
            "output_symbol": "a",
        }
        m = Mapping(**cfg)
        a = keyboard_layout.get("a")
        self.assertEqual(m.get_output_type_code(), (EV_KEY, a))

        m.output_symbol = "key(a)"
        self.assertIsNone(m.get_output_type_code())

        cfg = {
            "input_combination": [{"type": 1, "code": 2}, {"type": 3, "code": 1}],
            "target_uinput": "keyboard",
            "output_type": 2,
            "output_code": 3,
        }
        m = Mapping(**cfg)
        self.assertEqual(m.get_output_type_code(), (2, 3))

    def test_strips_output_symbol(self):
        cfg = {
            "input_combination": [{"type": 1, "code": 2}],
            "target_uinput": "keyboard",
            "output_symbol": "\t a \n",
        }
        m = Mapping(**cfg)
        a = keyboard_layout.get("a")
        self.assertEqual(m.get_output_type_code(), (EV_KEY, a))

    def test_combination_changed_callback(self):
        cfg = {
            "input_combination": [{"type": 1, "code": 1}],
            "target_uinput": "keyboard",
            "output_symbol": "a",
        }
        m = Mapping(**cfg)
        arguments = []

        def callback(*args):
            arguments.append(tuple(args))

        m.set_combination_changed_callback(callback)
        m.input_combination = [{"type": 1, "code": 2}]
        m.input_combination = [{"type": 1, "code": 3}]

        # make sure a copy works as expected and keeps the callback
        m2 = m.copy()
        m2.input_combination = [{"type": 1, "code": 4}]
        m2.remove_combination_changed_callback()
        m.remove_combination_changed_callback()
        m.input_combination = [{"type": 1, "code": 5}]
        m2.input_combination = [{"type": 1, "code": 6}]
        self.assertEqual(
            arguments,
            [
                (
                    InputCombination([{"type": 1, "code": 2}]),
                    InputCombination([{"type": 1, "code": 1}]),
                ),
                (
                    InputCombination([{"type": 1, "code": 3}]),
                    InputCombination([{"type": 1, "code": 2}]),
                ),
                (
                    InputCombination([{"type": 1, "code": 4}]),
                    InputCombination([{"type": 1, "code": 3}]),
                ),
            ],
        )
        m.remove_combination_changed_callback()

    def test_init_fails(self):
        """Test that the init fails with invalid data."""
        test = partial(self.assertRaises, ValidationError, Mapping)
        cfg = {
            "input_combination": [{"type": 1, "code": 2}],
            "target_uinput": "keyboard",
            "output_symbol": "a",
        }
        Mapping(**cfg)

        # missing output symbol
        del cfg["output_symbol"]
        test(**cfg)
        cfg["output_code"] = KEY_ESC
        test(**cfg)
        cfg["output_type"] = EV_KEY
        Mapping(**cfg)

        # matching type, code and symbol. This cannot be done via the ui, and requires
        # manual editing of the preset file.
        a = keyboard_layout.get("a")
        cfg["output_code"] = a
        cfg["output_symbol"] = "a"
        cfg["output_type"] = EV_KEY
        Mapping(**cfg)

        # macro
        cfg["output_symbol"] = "key(a)"
        test(**cfg)
        cfg["output_symbol"] = "a"
        Mapping(**cfg)

        # mismatching type, code and symbol
        cfg["output_symbol"] = "b"
        test(**cfg)
        del cfg["output_type"]
        del cfg["output_code"]
        Mapping(**cfg)  # no error

        # empty symbol string without type and code
        cfg["output_symbol"] = ""
        test(**cfg)
        cfg["output_symbol"] = "a"

        # missing target
        del cfg["target_uinput"]
        test(**cfg)

        # unknown target
        cfg["target_uinput"] = "foo"
        test(**cfg)
        cfg["target_uinput"] = "keyboard"
        Mapping(**cfg)

        # missing input_combination
        del cfg["input_combination"]
        test(**cfg)
        cfg["input_combination"] = [{"type": 1, "code": 2}]
        Mapping(**cfg)

        # no macro and not a known symbol
        cfg["output_symbol"] = "qux"
        test(**cfg)
        cfg["output_symbol"] = "key(a)"
        Mapping(**cfg)

        # invalid macro
        cfg["output_symbol"] = "key('a')"
        test(**cfg)
        cfg["output_symbol"] = "a"
        Mapping(**cfg)

        # map axis but no output type and code given
        cfg["input_combination"] = [{"type": 3, "code": 0}]
        test(**cfg)
        # output symbol=disable is allowed
        cfg["output_symbol"] = DISABLE_NAME
        Mapping(**cfg)
        del cfg["output_symbol"]
        cfg["output_code"] = 1
        cfg["output_type"] = 3
        Mapping(**cfg)

        # empty symbol string is allowed when type and code is set
        cfg["output_symbol"] = ""
        Mapping(**cfg)
        del cfg["output_symbol"]

        # multiple axis as axis in event combination
        cfg["input_combination"] = [{"type": 3, "code": 0}, {"type": 3, "code": 1}]
        test(**cfg)
        cfg["input_combination"] = [{"type": 3, "code": 0}]
        Mapping(**cfg)

        del cfg["output_type"]
        del cfg["output_code"]
        cfg["input_combination"] = [{"type": 1, "code": 2}]
        cfg["output_symbol"] = "a"
        Mapping(**cfg)

        # map EV_ABS as key with trigger point out of range
        cfg["input_combination"] = [{"type": 3, "code": 0, "analog_threshold": 100}]
        test(**cfg)
        cfg["input_combination"] = [{"type": 3, "code": 0, "analog_threshold": 99}]
        Mapping(**cfg)
        cfg["input_combination"] = [{"type": 3, "code": 0, "analog_threshold": -100}]
        test(**cfg)
        cfg["input_combination"] = [{"type": 3, "code": 0, "analog_threshold": -99}]
        Mapping(**cfg)

        cfg["input_combination"] = [{"type": 1, "code": 2}]
        Mapping(**cfg)

        # deadzone out of range
        test(**cfg, deadzone=1.01)
        test(**cfg, deadzone=-0.01)
        Mapping(**cfg, deadzone=1)
        Mapping(**cfg, deadzone=0)

        # expo out of range
        test(**cfg, expo=1.01)
        test(**cfg, expo=-1.01)
        Mapping(**cfg, expo=1)
        Mapping(**cfg, expo=-1)

        # negative rate
        test(**cfg, rel_rate=-1)
        test(**cfg, rel_rate=0)

        Mapping(**cfg, rel_rate=1)
        Mapping(**cfg, rel_rate=200)

        # negative rel_to_abs_input_cutoff
        test(**cfg, rel_to_abs_input_cutoff=-1)
        test(**cfg, rel_to_abs_input_cutoff=0)
        Mapping(**cfg, rel_to_abs_input_cutoff=1)
        Mapping(**cfg, rel_to_abs_input_cutoff=3)

        # negative release timeout
        test(**cfg, release_timeout=-0.1)
        test(**cfg, release_timeout=0)
        Mapping(**cfg, release_timeout=0.05)
        Mapping(**cfg, release_timeout=0.3)

        # analog output but no analog input
        cfg = {
            "input_combination": [{"type": 3, "code": 1, "analog_threshold": -1}],
            "target_uinput": "gamepad",
            "output_type": 3,
            "output_code": 1,
        }
        test(**cfg)
        cfg["input_combination"] = [{"type": 2, "code": 1, "analog_threshold": -1}]
        test(**cfg)
        cfg["output_type"] = 2
        test(**cfg)
        cfg["input_combination"] = [{"type": 3, "code": 1, "analog_threshold": -1}]
        test(**cfg)

    def test_automatically_detects_mapping_type(self):
        cfg = {
            "input_combination": [{"type": 1, "code": 2}],
            "target_uinput": "keyboard",
            "output_symbol": "a",
        }
        self.assertEqual(Mapping(**cfg).mapping_type, MappingType.KEY_MACRO.value)

        cfg = {
            "input_combination": [{"type": 1, "code": 2}],
            "target_uinput": "keyboard",
            "output_type": EV_KEY,
            "output_code": KEY_ESC,
        }
        self.assertEqual(Mapping(**cfg).mapping_type, MappingType.KEY_MACRO.value)

        cfg = {
            "input_combination": [{"type": EV_REL, "code": REL_X}],
            "target_uinput": "keyboard",
            "output_type": EV_REL,
            "output_code": REL_X,
        }
        self.assertEqual(Mapping(**cfg).mapping_type, MappingType.ANALOG.value)

    def test_revalidate_at_assignment(self):
        cfg = {
            "input_combination": [{"type": 1, "code": 1}],
            "target_uinput": "keyboard",
            "output_symbol": "a",
        }
        m = Mapping(**cfg)
        test = partial(self.assertRaises, ValidationError, m.__setattr__)

        # invalid input event
        test("input_combination", "1,2,3,4")

        # unknown target
        test("target_uinput", "foo")

        # invalid macro
        test("output_symbol", "key()")

        # we could do a lot more tests here but since pydantic uses the same validation
        # code as for the initialization we only need to make sure that the
        # assignment validation is active

    def test_set_invalid_combination_with_callback(self):
        cfg = {
            "input_combination": [{"type": 1, "code": 1}],
            "target_uinput": "keyboard",
            "output_symbol": "a",
        }
        m = Mapping(**cfg)
        m.set_combination_changed_callback(lambda *args: None)
        self.assertRaises(ValidationError, m.__setattr__, "input_combination", "1,2")
        m.input_combination = [{"type": 1, "code": 2}]
        m.input_combination = [{"type": 1, "code": 2}]

    def test_is_valid(self):
        cfg = {
            "input_combination": [{"type": 1, "code": 1}],
            "target_uinput": "keyboard",
            "output_symbol": "a",
        }
        m = Mapping(**cfg)
        self.assertTrue(m.is_valid())

    def test_wrong_target(self):
        mapping = Mapping(
            input_combination=[{"type": EV_KEY, "code": KEY_1}],
            target_uinput="keyboard",
            output_symbol="a",
        )
        mapping.set_combination_changed_callback(lambda *args: None)
        self.assertRaisesRegex(
            ValidationError,
            # the error should mention
            # - the symbol
            # - the current incorrect target
            # - the target that works for this symbol
            ".*BTN_A.*keyboard.*gamepad",
            mapping.__setattr__,
            "output_symbol",
            "BTN_A",
        )

    def test_wrong_target_for_macro(self):
        mapping = Mapping(
            input_combination=[{"type": EV_KEY, "code": KEY_1}],
            target_uinput="keyboard",
            output_symbol="key(a)",
        )
        mapping.set_combination_changed_callback(lambda *args: None)
        self.assertRaisesRegex(
            ValidationError,
            # the error should mention
            # - the symbol
            # - the current incorrect target
            # - the target that works for this symbol
            ".*BTN_A.*keyboard.*gamepad",
            mapping.__setattr__,
            "output_symbol",
            "key(BTN_A)",
        )


@test_setup
class TestUIMapping(unittest.IsolatedAsyncioTestCase):
    def test_init(self):
        """Should be able to initialize without throwing errors."""
        UIMapping()

    def test_is_valid(self):
        """Should be invalid at first and become valid once all data is provided."""
        mapping = UIMapping()
        self.assertFalse(mapping.is_valid())

        mapping.input_combination = [{"type": EV_KEY, "code": KEY_1}]
        mapping.output_symbol = "a"
        self.assertFalse(mapping.is_valid())
        mapping.target_uinput = "keyboard"
        self.assertTrue(mapping.is_valid())

    def test_updates_validation_error(self):
        mapping = UIMapping()
        errors = mapping.get_error().errors()
        # target_uinput: none is not an allowed value
        # __root__: Missing Argument: Mapping must either contain `output_symbol` or
        #   `output_type` and `output_code`
        self.assertGreaterEqual(len(errors), 2)
        mapping.input_combination = [{"type": EV_KEY, "code": KEY_1}]
        mapping.output_symbol = "a"
        self.assertIn(
            "1 validation error for Mapping\ntarget_uinput",
            str(mapping.get_error()),
        )
        mapping.target_uinput = "keyboard"
        self.assertTrue(mapping.is_valid())
        self.assertIsNone(mapping.get_error())

    def test_copy_returns_ui_mapping(self):
        """Copy should also be a UIMapping with all the invalid data."""
        mapping = UIMapping()
        mapping_2 = mapping.copy()
        self.assertIsInstance(mapping_2, UIMapping)
        self.assertEqual(
            mapping_2.input_combination, InputCombination.empty_combination()
        )
        self.assertIsNone(mapping_2.output_symbol)

    def test_get_bus_massage(self):
        mapping = UIMapping()
        mapping_2 = mapping.get_bus_message()
        self.assertEqual(mapping_2.message_type, MessageType.mapping)

        with self.assertRaises(TypeError):
            # the massage should be immutable
            mapping_2.output_symbol = "a"
        self.assertIsNone(mapping_2.output_symbol)

        # the original should be not immutable
        mapping.output_symbol = "a"
        self.assertEqual(mapping.output_symbol, "a")

    def test_has_input_defined(self):
        mapping = UIMapping()
        self.assertFalse(mapping.has_input_defined())
        mapping.input_combination = InputCombination([InputConfig(type=EV_KEY, code=1)])
        self.assertTrue(mapping.has_input_defined())


if __name__ == "__main__":
    unittest.main()
