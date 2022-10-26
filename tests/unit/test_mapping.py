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
from functools import partial

from evdev.ecodes import (
    EV_ABS,
    EV_REL,
    REL_X,
    BTN_MIDDLE,
    EV_KEY,
    KEY_A,
    ABS_X,
    REL_Y,
    REL_WHEEL,
    REL_WHEEL_HI_RES,
)
from pydantic import ValidationError

from inputremapper.configs.mapping import Mapping, UIMapping
from inputremapper.configs.system_mapping import system_mapping, DISABLE_NAME
from inputremapper.event_combination import EventCombination
from inputremapper.gui.messages.message_broker import MessageType
from inputremapper.input_event import EventActions, InputEvent, USE_AS_ANALOG_VALUE


class TestMapping(unittest.IsolatedAsyncioTestCase):
    def test_init(self):
        """Test init and that defaults are set."""
        cfg = {
            "event_combination": "1,2,1",
            "target_uinput": "keyboard",
            "output_symbol": "a",
        }
        m = Mapping(**cfg)
        self.assertEqual(m.event_combination, EventCombination.validate("1,2,1"))
        self.assertEqual(m.target_uinput, "keyboard")
        self.assertEqual(m.output_symbol, "a")

        self.assertIsNone(m.output_code)
        self.assertIsNone(m.output_type)

        self.assertEqual(m.macro_key_sleep_ms, 0)
        self.assertEqual(m.deadzone, 0.1)
        self.assertEqual(m.gain, 1)
        self.assertEqual(m.expo, 0)
        self.assertEqual(m.rel_xy_rate, 125)
        self.assertEqual(m.rel_wheel_rate, 60)
        self.assertEqual(m.rel_xy_speed, 30)
        self.assertEqual(m.rel_wheel_speed, 1)
        self.assertEqual(m.rel_xy_max_input, 100)
        self.assertEqual(m.release_timeout, 0.05)

    def test_is_wheel_output(self):
        mapping = Mapping(
            event_combination=EventCombination(
                events=(InputEvent(0, 0, EV_REL, REL_X, USE_AS_ANALOG_VALUE),)
            ),
            target_uinput="keyboard",
            output_type=EV_REL,
            output_code=REL_Y,
        )
        self.assertFalse(mapping.is_wheel_output())
        self.assertFalse(mapping.is_high_res_wheel_output())

        mapping = Mapping(
            event_combination=EventCombination(
                events=(InputEvent(0, 0, EV_REL, REL_X, USE_AS_ANALOG_VALUE),)
            ),
            target_uinput="keyboard",
            output_type=EV_REL,
            output_code=REL_WHEEL,
        )
        self.assertTrue(mapping.is_wheel_output())
        self.assertFalse(mapping.is_high_res_wheel_output())

        mapping = Mapping(
            event_combination=EventCombination(
                events=(InputEvent(0, 0, EV_REL, REL_X, USE_AS_ANALOG_VALUE),)
            ),
            target_uinput="keyboard",
            output_type=EV_REL,
            output_code=REL_WHEEL_HI_RES,
        )
        self.assertFalse(mapping.is_wheel_output())
        self.assertTrue(mapping.is_high_res_wheel_output())

    def test_find_analog_input_event(self):
        analog_input = InputEvent(0, 0, EV_REL, REL_X, USE_AS_ANALOG_VALUE)

        mapping = Mapping(
            event_combination=EventCombination(
                events=(
                    InputEvent(0, 0, EV_KEY, BTN_MIDDLE, 1),
                    InputEvent(0, 0, EV_REL, REL_Y, 1),
                    analog_input,
                )
            ),
            target_uinput="keyboard",
            output_type=EV_ABS,
            output_code=ABS_X,
        )
        self.assertIsNone(mapping.find_analog_input_event(type_=EV_ABS))
        self.assertEqual(mapping.find_analog_input_event(type_=EV_REL), analog_input)
        self.assertEqual(mapping.find_analog_input_event(), analog_input)

        mapping = Mapping(
            event_combination=EventCombination(
                events=(
                    InputEvent(0, 0, EV_REL, REL_X, 1),
                    InputEvent(0, 0, EV_KEY, BTN_MIDDLE, 1),
                )
            ),
            target_uinput="keyboard",
            output_type=EV_KEY,
            output_code=KEY_A,
        )
        self.assertIsNone(mapping.find_analog_input_event(type_=EV_ABS))
        self.assertIsNone(mapping.find_analog_input_event(type_=EV_REL))
        self.assertIsNone(mapping.find_analog_input_event())

    def test_get_output_type_code(self):
        cfg = {
            "event_combination": "1,2,1",
            "target_uinput": "keyboard",
            "output_symbol": "a",
        }
        m = Mapping(**cfg)
        a = system_mapping.get("a")
        self.assertEqual(m.get_output_type_code(), (EV_KEY, a))
        m.output_symbol = "key(a)"
        self.assertIsNone(m.get_output_type_code())
        cfg = {
            "event_combination": "1,2,1+3,1,0",
            "target_uinput": "keyboard",
            "output_type": 2,
            "output_code": 3,
        }
        m = Mapping(**cfg)
        self.assertEqual(m.get_output_type_code(), (2, 3))

    def test_init_sets_event_actions(self):
        """Test that InputEvent.actions are set properly."""
        cfg = {
            "event_combination": "1,2,1+2,1,1+3,1,0",
            "target_uinput": "keyboard",
            "output_type": 2,
            "output_code": 3,
        }
        m = Mapping(**cfg)
        expected_actions = [(EventActions.as_key,), (EventActions.as_key,), ()]
        actions = [event.actions for event in m.event_combination]
        self.assertEqual(expected_actions, actions)

        # copy keeps the event actions
        m2 = m.copy()
        actions = [event.actions for event in m2.event_combination]
        self.assertEqual(expected_actions, actions)

        # changing the combination sets the actions
        m3 = m.copy()
        m3.event_combination = "1,2,1+2,1,0+3,1,10"
        expected_actions = [(EventActions.as_key,), (), (EventActions.as_key,)]
        actions = [event.actions for event in m3.event_combination]
        self.assertEqual(expected_actions, actions)

    def test_combination_changed_callback(self):
        cfg = {
            "event_combination": "1,1,1",
            "target_uinput": "keyboard",
            "output_symbol": "a",
        }
        m = Mapping(**cfg)
        arguments = []

        def callback(*args):
            arguments.append(tuple(args))

        m.set_combination_changed_callback(callback)
        m.event_combination = "1,1,2"
        m.event_combination = "1,1,3"

        # make sure a copy works as expected and keeps the callback
        m2 = m.copy()
        m2.event_combination = "1,1,4"
        m2.remove_combination_changed_callback()
        m.remove_combination_changed_callback()
        m.event_combination = "1,1,5"
        m2.event_combination = "1,1,6"
        self.assertEqual(
            arguments,
            [
                (
                    EventCombination.from_string("1,1,2"),
                    EventCombination.from_string("1,1,1"),
                ),
                (
                    EventCombination.from_string("1,1,3"),
                    EventCombination.from_string("1,1,2"),
                ),
                (
                    EventCombination.from_string("1,1,4"),
                    EventCombination.from_string("1,1,3"),
                ),
            ],
        )
        m.remove_combination_changed_callback()

    def test_init_fails(self):
        """Test that the init fails with invalid data."""
        test = partial(self.assertRaises, ValidationError, Mapping)
        cfg = {
            "event_combination": "1,2,3",
            "target_uinput": "keyboard",
            "output_symbol": "a",
        }
        Mapping(**cfg)

        # missing output symbol
        del cfg["output_symbol"]
        test(**cfg)
        cfg["output_code"] = 1
        test(**cfg)
        cfg["output_type"] = 1
        Mapping(**cfg)

        # matching type, code and symbol
        a = system_mapping.get("a")
        cfg["output_code"] = a
        cfg["output_symbol"] = "a"
        cfg["output_type"] = EV_KEY
        Mapping(**cfg)

        # macro + type and code
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

        # missing event_combination
        del cfg["event_combination"]
        test(**cfg)
        cfg["event_combination"] = "1,2,3"
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
        cfg["event_combination"] = "3,0,0"
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
        cfg["event_combination"] = "3,0,0+3,1,0"
        test(**cfg)
        cfg["event_combination"] = "3,0,0"
        Mapping(**cfg)

        del cfg["output_type"]
        del cfg["output_code"]
        cfg["event_combination"] = "1,2,3"
        cfg["output_symbol"] = "a"
        Mapping(**cfg)

        # map EV_ABS as key with trigger point out of range
        cfg["event_combination"] = "3,0,100"
        test(**cfg)
        cfg["event_combination"] = "3,0,99"
        Mapping(**cfg)
        cfg["event_combination"] = "3,0,-100"
        test(**cfg)
        cfg["event_combination"] = "3,0,-99"
        Mapping(**cfg)

        cfg["event_combination"] = "1,2,3"
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
        test(**cfg, rel_xy_rate=-1)
        test(**cfg, rel_wheel_rate=-1)

        test(**cfg, rel_xy_rate=0)
        test(**cfg, rel_wheel_rate=0)

        Mapping(**cfg, rel_xy_rate=1)
        Mapping(**cfg, rel_xy_rate=200)

        Mapping(**cfg, rel_wheel_rate=1)
        Mapping(**cfg, rel_wheel_rate=200)

        # negative rel_xy_speed
        test(**cfg, rel_xy_speed=-1)
        test(**cfg, rel_xy_speed=0)
        Mapping(**cfg, rel_xy_speed=1)
        Mapping(**cfg, rel_xy_speed=200)

        # negative rel_xy_max_input
        test(**cfg, rel_xy_max_input=-1)
        test(**cfg, rel_xy_max_input=0)
        Mapping(**cfg, rel_xy_max_input=1)
        Mapping(**cfg, rel_xy_max_input=200)

        # negative release timeout
        test(**cfg, release_timeout=-0.1)
        test(**cfg, release_timeout=0)
        Mapping(**cfg, release_timeout=0.05)
        Mapping(**cfg, release_timeout=0.3)

        # analog output but no analog input
        cfg = {
            "event_combination": "3,1,-1",
            "target_uinput": "gamepad",
            "output_type": 3,
            "output_code": 1,
        }
        test(**cfg)
        cfg["event_combination"] = "2,1,-1"
        test(**cfg)
        cfg["output_type"] = 2
        test(**cfg)
        cfg["event_combination"] = "3,1,-1"
        test(**cfg)

    def test_revalidate_at_assignment(self):
        cfg = {
            "event_combination": "1,1,1",
            "target_uinput": "keyboard",
            "output_symbol": "a",
        }
        m = Mapping(**cfg)
        test = partial(self.assertRaises, ValidationError, m.__setattr__)

        # invalid input event
        test("event_combination", "1,2,3,4")

        # unknown target
        test("target_uinput", "foo")

        # invalid macro
        test("output_symbol", "key()")

        # we could do a lot more tests here but since pydantic uses the same validation
        # code as for the initialization we only need to make sure that the
        # assignment validation is active

    def test_set_invalid_combination_with_callback(self):
        cfg = {
            "event_combination": "1,1,1",
            "target_uinput": "keyboard",
            "output_symbol": "a",
        }
        m = Mapping(**cfg)
        m.set_combination_changed_callback(lambda *args: None)
        self.assertRaises(ValidationError, m.__setattr__, "event_combination", "1,2")
        m.event_combination = "1,2,3"
        m.event_combination = "1,2,3"

    def test_is_valid(self):
        cfg = {
            "event_combination": "1,1,1",
            "target_uinput": "keyboard",
            "output_symbol": "a",
        }
        m = Mapping(**cfg)
        self.assertTrue(m.is_valid())


class TestUIMapping(unittest.IsolatedAsyncioTestCase):
    def test_init(self):
        """should be able to initialize without an error"""
        UIMapping()

    def test_is_valid(self):
        """should be invalid at first
        and become valid once all data is provided"""
        m = UIMapping()
        self.assertFalse(m.is_valid())

        m.event_combination = "1,2,3"
        m.output_symbol = "a"
        self.assertFalse(m.is_valid())
        m.target_uinput = "keyboard"
        self.assertTrue(m.is_valid())

    def test_updates_validation_error(self):
        m = UIMapping()
        self.assertGreaterEqual(len(m.get_error().errors()), 2)
        m.event_combination = "1,2,3"
        m.output_symbol = "a"
        self.assertIn(
            "1 validation error for Mapping\ntarget_uinput", str(m.get_error())
        )
        m.target_uinput = "keyboard"
        self.assertTrue(m.is_valid())
        self.assertIsNone(m.get_error())

    def test_copy_returns_ui_mapping(self):
        """copy should also be a UIMapping with all the invalid data"""
        m = UIMapping()
        m2 = m.copy()
        self.assertIsInstance(m2, UIMapping)
        self.assertEqual(m2.event_combination, EventCombination.empty_combination())
        self.assertIsNone(m2.output_symbol)

    def test_get_bus_massage(self):
        m = UIMapping()
        m2 = m.get_bus_message()
        self.assertEqual(m2.message_type, MessageType.mapping)

        with self.assertRaises(TypeError):
            # the massage should be immutable
            m2.output_symbol = "a"
        self.assertIsNone(m2.output_symbol)

        # the original should be not immutable
        m.output_symbol = "a"
        self.assertEqual(m.output_symbol, "a")

    def test_has_input_defined(self):
        m = UIMapping()
        self.assertFalse(m.has_input_defined())
        m.event_combination = EventCombination((EV_KEY, 1, 1))
        self.assertTrue(m.has_input_defined())


if __name__ == "__main__":
    unittest.main()
