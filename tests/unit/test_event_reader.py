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

import asyncio
import unittest

import evdev
from evdev.ecodes import (
    EV_KEY,
    EV_ABS,
    ABS_X,
    ABS_Y,
    ABS_RX,
    ABS_RY,
    EV_REL,
    REL_X,
    REL_Y,
    REL_HWHEEL_HI_RES,
    REL_WHEEL_HI_RES,
)

from inputremapper.configs.mapping import Mapping
from inputremapper.configs.preset import Preset
from inputremapper.configs.system_mapping import system_mapping
from inputremapper.configs.input_config import InputCombination, InputConfig
from inputremapper.injection.context import Context
from inputremapper.injection.event_reader import EventReader
from inputremapper.injection.global_uinputs import global_uinputs
from tests.lib.fixtures import (
    new_event,
    get_key_mapping,
    fixtures,
)
from tests.lib.cleanup import quick_cleanup


class TestEventReader(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.gamepad_source = evdev.InputDevice(fixtures.gamepad.path)
        self.stop_event = asyncio.Event()
        self.preset = Preset()

    def tearDown(self):
        quick_cleanup()

    async def setup(self, source, mapping):
        """Set a EventReader up for the test and run it in the background."""
        context = Context(mapping, {}, {})
        context.uinput = evdev.UInput()
        # TODO removed usage of forward_to, test that the forwardDummy is used?
        event_reader = EventReader(context, source, self.stop_event)
        asyncio.ensure_future(event_reader.run())
        await asyncio.sleep(0.1)
        return context, event_reader

    async def test_if_single_joystick_then(self):
        # TODO: Move this somewhere more sensible
        # Integration test style for if_single.
        # won't care about the event, because the purpose is not set to BUTTON
        code_a = system_mapping.get("a")
        code_shift = system_mapping.get("KEY_LEFTSHIFT")
        trigger = evdev.ecodes.BTN_A

        self.preset.add(
            get_key_mapping(
                InputCombination(
                    InputConfig(
                        type=EV_KEY,
                        code=trigger,
                        origin_hash=fixtures.gamepad.get_device_hash(),
                    )
                ),
                "keyboard",
                "if_single(key(a), key(KEY_LEFTSHIFT))",
            )
        )
        self.preset.add(
            get_key_mapping(
                InputCombination(
                    InputConfig(
                        type=EV_ABS,
                        code=ABS_Y,
                        analog_threshold=1,
                        origin_hash=fixtures.gamepad.get_device_hash(),
                    )
                ),
                "keyboard",
                "b",
            ),
        )

        # left x to mouse x
        cfg = {
            "input_combination": InputConfig(
                type=EV_ABS, code=ABS_X, origin_hash=fixtures.gamepad.get_device_hash()
            ),
            "target_uinput": "mouse",
            "output_type": EV_REL,
            "output_code": REL_X,
        }
        self.preset.add(Mapping(**cfg))

        # left y to mouse y
        cfg["input_combination"] = InputConfig(
            type=EV_ABS, code=ABS_Y, origin_hash=fixtures.gamepad.get_device_hash()
        )
        cfg["output_code"] = REL_Y
        self.preset.add(Mapping(**cfg))

        # right x to wheel x
        cfg["input_combination"] = InputConfig(
            type=EV_ABS, code=ABS_RX, origin_hash=fixtures.gamepad.get_device_hash()
        )
        cfg["output_code"] = REL_HWHEEL_HI_RES
        self.preset.add(Mapping(**cfg))

        # right y to wheel y
        cfg["input_combination"] = InputConfig(
            type=EV_ABS, code=ABS_RY, origin_hash=fixtures.gamepad.get_device_hash()
        )
        cfg["output_code"] = REL_WHEEL_HI_RES
        self.preset.add(Mapping(**cfg))

        context, _ = await self.setup(self.gamepad_source, self.preset)

        self.gamepad_source.push_events(
            [
                InputEvent.key(trigger, 1),  # start the macro
                InputEvent.abs(ABS_Y, 10),  # ignored
                InputEvent.key(evdev.ecodes.BTN_B, 2),  # ignored
                InputEvent.key(evdev.ecodes.BTN_B, 0),  # ignored
                # stop it, the only way to trigger `then`
                InputEvent.key(trigger, 0),
            ]
        )

        await asyncio.sleep(0.1)
        self.stop_event.set()  # stop the reader
        self.assertEqual(len(context.listeners), 0)
        history = [a.t for a in global_uinputs.get_uinput("keyboard").write_history]
        self.assertIn((EV_KEY, code_a, 1), history)
        self.assertIn((EV_KEY, code_a, 0), history)
        self.assertNotIn((EV_KEY, code_shift, 1), history)
        self.assertNotIn((EV_KEY, code_shift, 0), history)

    async def test_if_single_joystick_under_threshold(self):
        """Triggers then because the joystick events value is too low."""
        # TODO: Move this somewhere more sensible
        code_a = system_mapping.get("a")
        trigger = evdev.ecodes.BTN_A
        self.preset.add(
            get_key_mapping(
                InputCombination(
                    InputConfig(
                        type=EV_KEY,
                        code=trigger,
                        origin_hash=fixtures.gamepad.get_device_hash(),
                    )
                ),
                "keyboard",
                "if_single(k(a), k(KEY_LEFTSHIFT))",
            )
        )
        self.preset.add(
            get_key_mapping(
                InputCombination(
                    InputConfig(
                        type=EV_ABS,
                        code=ABS_Y,
                        analog_threshold=1,
                        origin_hash=fixtures.gamepad.get_device_hash(),
                    )
                ),
                "keyboard",
                "b",
            ),
        )

        # self.preset.set("gamepad.joystick.left_purpose", BUTTONS)
        # self.preset.set("gamepad.joystick.right_purpose", BUTTONS)
        context, _ = await self.setup(self.gamepad_source, self.preset)

        self.gamepad_source.push_events(
            [
                InputEvent.key(trigger, 1),  # start the macro
                InputEvent.abs(ABS_Y, 1),  # ignored because value too low
                InputEvent.key(trigger, 0),  # stop, only way to trigger `then`
            ]
        )
        await asyncio.sleep(0.1)
        self.assertEqual(len(context.listeners), 0)
        history = [a.t for a in global_uinputs.get_uinput("keyboard").write_history]

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
