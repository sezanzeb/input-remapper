#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@sezanzeb.de>
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
import asyncio

import evdev
from evdev.ecodes import EV_KEY, EV_ABS, ABS_Y, EV_REL

from keymapper.injection.consumers.keycode_mapper import active_macros
from keymapper.config import BUTTONS, MOUSE, WHEEL

from keymapper.injection.context import Context
from keymapper.mapping import Mapping
from keymapper.key import Key
from keymapper.injection.consumer_control import ConsumerControl, consumer_classes
from keymapper.injection.consumers.consumer import Consumer
from keymapper.injection.consumers.keycode_mapper import KeycodeMapper
from keymapper.system_mapping import system_mapping

from tests.test import new_event, quick_cleanup


class ExampleConsumer(Consumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def is_enabled(self):
        return True

    async def notify(self, event):
        pass

    def is_handled(self, event):
        pass

    async def run(self):
        pass


class TestConsumerControl(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        consumer_classes.append(ExampleConsumer)
        self.gamepad_source = evdev.InputDevice("/dev/input/event30")
        self.mapping = Mapping()

    def tearDown(self):
        quick_cleanup()
        consumer_classes.remove(ExampleConsumer)

    def setup(self, source, mapping):
        """Set a a ConsumerControl up for the test and run it in the background."""
        forward_to = evdev.UInput()
        context = Context(mapping)
        context.miscellaneous_output = evdev.UInput()
        consumer_control = ConsumerControl(context, source, forward_to)
        for consumer in consumer_control._consumers:
            consumer._abs_range = (-10, 10)
        asyncio.ensure_future(consumer_control.run())
        return context, consumer_control

    async def test_no_keycode_mapper_needed(self):
        self.mapping.change(Key(EV_KEY, 1, 1), "b")
        _, consumer_control = self.setup(self.gamepad_source, self.mapping)
        consumer_types = [type(consumer) for consumer in consumer_control._consumers]
        self.assertIn(KeycodeMapper, consumer_types)

        self.mapping.empty()
        _, consumer_control = self.setup(self.gamepad_source, self.mapping)
        consumer_types = [type(consumer) for consumer in consumer_control._consumers]
        self.assertNotIn(KeycodeMapper, consumer_types)

        self.mapping.change(Key(EV_KEY, 1, 1), "k(a)")
        _, consumer_control = self.setup(self.gamepad_source, self.mapping)
        consumer_types = [type(consumer) for consumer in consumer_control._consumers]
        self.assertIn(KeycodeMapper, consumer_types)

    async def test_if_single_joystick_then(self):
        # Integration test style for if_single.
        # won't care about the event, because the purpose is not set to BUTTON
        code_a = system_mapping.get("a")
        code_shift = system_mapping.get("KEY_LEFTSHIFT")
        trigger = 1
        self.mapping.change(
            Key(EV_KEY, trigger, 1), "if_single(k(a), k(KEY_LEFTSHIFT))"
        )
        self.mapping.change(Key(EV_ABS, ABS_Y, 1), "b")

        self.mapping.set("gamepad.joystick.left_purpose", MOUSE)
        self.mapping.set("gamepad.joystick.right_purpose", WHEEL)
        context, _ = self.setup(self.gamepad_source, self.mapping)

        self.gamepad_source.push_events(
            [
                new_event(EV_KEY, trigger, 1),  # start the macro
                new_event(EV_ABS, ABS_Y, 10),  # ignored
                new_event(EV_KEY, 2, 2),  # ignored
                new_event(EV_KEY, 2, 0),  # ignored
                new_event(EV_REL, 1, 1),  # ignored
                new_event(
                    EV_KEY, trigger, 0
                ),  # stop it, the only way to trigger `then`
            ]
        )
        await asyncio.sleep(0.1)
        self.assertFalse(active_macros[(EV_KEY, 1)].running)
        history = [a.t for a in context.miscellaneous_output.write_history]
        self.assertIn((EV_KEY, code_a, 1), history)
        self.assertIn((EV_KEY, code_a, 0), history)
        self.assertNotIn((EV_KEY, code_shift, 1), history)
        self.assertNotIn((EV_KEY, code_shift, 0), history)

    async def test_if_single_joystick_else(self):
        """triggers else + delayed_handle_keycode"""
        # Integration test style for if_single.
        # If a joystick that is mapped to a button is moved, if_single stops
        code_b = system_mapping.get("b")
        code_shift = system_mapping.get("KEY_LEFTSHIFT")
        trigger = 1
        self.mapping.change(
            Key(EV_KEY, trigger, 1), "if_single(k(a), k(KEY_LEFTSHIFT))"
        )
        self.mapping.change(Key(EV_ABS, ABS_Y, 1), "b")

        self.mapping.set("gamepad.joystick.left_purpose", BUTTONS)
        self.mapping.set("gamepad.joystick.right_purpose", BUTTONS)
        context, _ = self.setup(self.gamepad_source, self.mapping)

        self.gamepad_source.push_events(
            [
                new_event(EV_KEY, trigger, 1),  # start the macro
                new_event(EV_ABS, ABS_Y, 10),  # not ignored, stops it
            ]
        )
        await asyncio.sleep(0.1)
        self.assertFalse(active_macros[(EV_KEY, 1)].running)
        history = [a.t for a in context.miscellaneous_output.write_history]

        # the key that triggered if_single should be injected after
        # if_single had a chance to inject keys (if the macro is fast enough),
        # so that if_single can inject a modifier to e.g. capitalize the
        # triggering key. This is important for the space cadet shift
        self.assertListEqual(
            history,
            [
                (EV_KEY, code_shift, 1),
                (EV_KEY, code_b, 1),  # would be capitalized now
                (EV_KEY, code_shift, 0),
            ],
        )

    async def test_if_single_joystick_under_threshold(self):
        """triggers then because the joystick events value is too low."""
        code_a = system_mapping.get("a")
        trigger = 1
        self.mapping.change(
            Key(EV_KEY, trigger, 1), "if_single(k(a), k(KEY_LEFTSHIFT))"
        )
        self.mapping.change(Key(EV_ABS, ABS_Y, 1), "b")

        self.mapping.set("gamepad.joystick.left_purpose", BUTTONS)
        self.mapping.set("gamepad.joystick.right_purpose", BUTTONS)
        context, _ = self.setup(self.gamepad_source, self.mapping)

        self.gamepad_source.push_events(
            [
                new_event(EV_KEY, trigger, 1),  # start the macro
                new_event(EV_ABS, ABS_Y, 1),  # ignored because value too low
                new_event(EV_KEY, trigger, 0),  # stop, only way to trigger `then`
            ]
        )
        await asyncio.sleep(0.1)
        self.assertFalse(active_macros[(EV_KEY, 1)].running)
        history = [a.t for a in context.miscellaneous_output.write_history]

        # the key that triggered if_single should be injected after
        # if_single had a chance to inject keys (if the macro is fast enough),
        # so that if_single can inject a modifier to e.g. capitalize the
        # triggering key. This is important for the space cadet shift
        self.assertListEqual(
            history,
            [
                (EV_KEY, code_a, 1),
                (EV_KEY, code_a, 0),
            ],
        )
