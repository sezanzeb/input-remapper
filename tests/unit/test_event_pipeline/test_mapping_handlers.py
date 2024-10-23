#!/usr/bin/python3
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


"""See TestEventPipeline for more tests."""


import asyncio
import unittest
from unittest.mock import MagicMock

import evdev
from evdev.ecodes import (
    EV_KEY,
    EV_ABS,
    EV_REL,
    ABS_X,
    REL_X,
    BTN_LEFT,
    BTN_RIGHT,
    KEY_A,
    REL_Y,
    REL_WHEEL,
)

from inputremapper.injection.mapping_handlers.combination_handler import (
    CombinationHandler,
)

from inputremapper.injection.mapping_handlers.rel_to_btn_handler import RelToBtnHandler

from inputremapper.configs.mapping import Mapping, DEFAULT_REL_RATE
from inputremapper.configs.input_config import InputCombination, InputConfig
from inputremapper.injection.global_uinputs import GlobalUInputs, UInput
from inputremapper.injection.mapping_handlers.abs_to_abs_handler import AbsToAbsHandler
from inputremapper.injection.mapping_handlers.abs_to_btn_handler import AbsToBtnHandler
from inputremapper.injection.mapping_handlers.abs_to_rel_handler import AbsToRelHandler
from inputremapper.injection.mapping_handlers.rel_to_rel_handler import RelToRelHandler
from inputremapper.injection.mapping_handlers.axis_switch_handler import (
    AxisSwitchHandler,
)
from inputremapper.injection.mapping_handlers.hierarchy_handler import HierarchyHandler
from inputremapper.injection.mapping_handlers.key_handler import KeyHandler
from inputremapper.injection.mapping_handlers.macro_handler import MacroHandler
from inputremapper.injection.mapping_handlers.mapping_handler import MappingHandler
from inputremapper.injection.mapping_handlers.rel_to_abs_handler import RelToAbsHandler
from inputremapper.input_event import InputEvent, EventActions

from tests.lib.cleanup import cleanup
from tests.lib.patches import InputDevice
from tests.lib.constants import MAX_ABS
from tests.lib.fixtures import fixtures
from tests.lib.test_setup import test_setup


class BaseTests:
    """implements test that should pass on most mapping handlers
    in special cases override specific tests.
    """

    handler: MappingHandler

    def setUp(self):
        raise NotImplementedError

    def tearDown(self) -> None:
        cleanup()

    def test_reset(self):
        mock = MagicMock()
        self.handler.set_sub_handler(mock)
        self.handler.reset()
        mock.reset.assert_called()


@test_setup
class TestAxisSwitchHandler(BaseTests, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        input_combination = InputCombination(
            (
                InputConfig(type=2, code=5),
                InputConfig(type=1, code=3),
            )
        )
        self.global_uinputs = GlobalUInputs(UInput)
        self.global_uinputs.prepare_all()
        self.handler = AxisSwitchHandler(
            input_combination,
            Mapping(
                input_combination=input_combination.to_config(),
                target_uinput="mouse",
                output_type=2,
                output_code=1,
            ),
            MagicMock(),
            self.global_uinputs,
        )


@test_setup
class TestAbsToBtnHandler(BaseTests, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        input_combination = InputCombination(
            [InputConfig(type=3, code=5, analog_threshold=10)]
        )
        self.global_uinputs = GlobalUInputs(UInput)
        self.global_uinputs.prepare_all()
        self.handler = AbsToBtnHandler(
            input_combination,
            Mapping(
                input_combination=input_combination.to_config(),
                target_uinput="mouse",
                output_symbol="BTN_LEFT",
            ),
            global_uinputs=self.global_uinputs,
        )


@test_setup
class TestAbsToAbsHandler(BaseTests, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        input_combination = InputCombination([InputConfig(type=EV_ABS, code=ABS_X)])
        self.global_uinputs = GlobalUInputs(UInput)
        self.global_uinputs.prepare_all()
        self.handler = AbsToAbsHandler(
            input_combination,
            Mapping(
                input_combination=input_combination.to_config(),
                target_uinput="gamepad",
                output_type=EV_ABS,
                output_code=ABS_X,
            ),
            global_uinputs=self.global_uinputs,
        )

    async def test_reset(self):
        self.handler.notify(
            InputEvent(0, 0, EV_ABS, ABS_X, MAX_ABS),
            source=InputDevice("/dev/input/event15"),
        )
        self.handler.reset()
        history = self.global_uinputs.get_uinput("gamepad").write_history
        self.assertEqual(
            history,
            [InputEvent.from_tuple((3, 0, MAX_ABS)), InputEvent.from_tuple((3, 0, 0))],
        )


@test_setup
class TestRelToAbsHandler(BaseTests, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        input_combination = InputCombination([InputConfig(type=EV_REL, code=REL_X)])
        self.global_uinputs = GlobalUInputs(UInput)
        self.global_uinputs.prepare_all()
        self.handler = RelToAbsHandler(
            input_combination,
            Mapping(
                input_combination=input_combination.to_config(),
                target_uinput="gamepad",
                output_type=EV_ABS,
                output_code=ABS_X,
            ),
            self.global_uinputs,
        )

    async def test_reset(self):
        self.handler.notify(
            InputEvent(0, 0, EV_REL, REL_X, 123),
            source=InputDevice("/dev/input/event15"),
        )
        self.handler.reset()
        history = self.global_uinputs.get_uinput("gamepad").write_history
        self.assertEqual(len(history), 2)

        # something large, doesn't matter
        self.assertGreater(history[0].value, MAX_ABS / 10)

        # 0, because of the reset
        self.assertEqual(history[1].value, 0)

    async def test_rate_changes(self):
        expected_rate = 100

        # delta in usec
        delta = 1000000 / expected_rate

        self.handler.notify(
            InputEvent(0, delta, EV_REL, REL_X, 100),
            source=InputDevice("/dev/input/event15"),
        )

        self.handler.notify(
            InputEvent(0, delta * 2, EV_REL, REL_X, 100),
            source=InputDevice("/dev/input/event15"),
        )

        self.assertEqual(self.handler._observed_rate, expected_rate)

    async def test_rate_stays(self):
        # if two timestamps are equal, the rate stays at its previous value,
        # in this case the default

        self.handler.notify(
            InputEvent(0, 50, EV_REL, REL_X, 100),
            source=InputDevice("/dev/input/event15"),
        )

        self.handler.notify(
            InputEvent(0, 50, EV_REL, REL_X, 100),
            source=InputDevice("/dev/input/event15"),
        )

        self.assertEqual(self.handler._observed_rate, DEFAULT_REL_RATE)


@test_setup
class TestAbsToRelHandler(BaseTests, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        input_combination = InputCombination([InputConfig(type=EV_ABS, code=ABS_X)])
        self.global_uinputs = GlobalUInputs(UInput)
        self.global_uinputs.prepare_all()
        self.handler = AbsToRelHandler(
            input_combination,
            Mapping(
                input_combination=input_combination.to_config(),
                target_uinput="mouse",
                output_type=EV_REL,
                output_code=REL_X,
            ),
            self.global_uinputs,
        )

    async def test_reset(self):
        self.handler.notify(
            InputEvent(0, 0, EV_ABS, ABS_X, MAX_ABS),
            source=InputDevice("/dev/input/event15"),
        )
        await asyncio.sleep(0.2)
        self.handler.reset()
        await asyncio.sleep(0.05)

        count = self.global_uinputs.get_uinput("mouse").write_count
        self.assertGreater(count, 6)  # count should be 60*0.2 = 12
        await asyncio.sleep(0.2)
        self.assertEqual(count, self.global_uinputs.get_uinput("mouse").write_count)


@test_setup
class TestCombinationHandler(BaseTests, unittest.IsolatedAsyncioTestCase):
    handler: CombinationHandler

    def setUp(self):
        mouse = fixtures.foo_device_2_mouse
        self.mouse_hash = mouse.get_device_hash()

        keyboard = fixtures.foo_device_2_keyboard
        self.keyboard_hash = keyboard.get_device_hash()

        gamepad = fixtures.gamepad
        self.gamepad_hash = gamepad.get_device_hash()

        input_combination = InputCombination(
            (
                InputConfig(
                    type=EV_REL,
                    code=5,
                    analog_threshold=10,
                    origin_hash=self.mouse_hash,
                ),
                InputConfig(
                    type=EV_KEY,
                    code=3,
                    origin_hash=self.keyboard_hash,
                ),
                InputConfig(
                    type=EV_KEY,
                    code=4,
                    origin_hash=self.gamepad_hash,
                ),
            )
        )

        self.input_combination = input_combination

        self.context_mock = MagicMock()

        self.global_uinputs = GlobalUInputs(UInput)
        self.global_uinputs.prepare_all()
        self.handler = CombinationHandler(
            input_combination,
            Mapping(
                input_combination=input_combination.to_config(),
                target_uinput="mouse",
                output_symbol="BTN_LEFT",
            ),
            self.context_mock,
            global_uinputs=self.global_uinputs,
        )

    def test_forward_correctly(self):
        # In the past, if a mapping has inputs from two different sub devices, it
        # always failed to send the release events to the correct one.
        # Nowadays, self._context.get_forward_uinput(origin_hash) is used to
        # release them correctly.
        mock = MagicMock()
        self.handler.set_sub_handler(mock)

        # insert our own test-uinput to see what is being written to it
        uinputs = {
            self.mouse_hash: evdev.UInput(),
            self.keyboard_hash: evdev.UInput(),
            self.gamepad_hash: evdev.UInput(),
        }
        self.context_mock.get_forward_uinput = lambda origin_hash: uinputs[origin_hash]

        # 1. trigger the combination
        self.handler.notify(
            InputEvent.rel(
                code=self.input_combination[0].code,
                value=1,
                origin_hash=self.input_combination[0].origin_hash,
            ),
            source=fixtures.foo_device_2_mouse,
        )
        self.handler.notify(
            InputEvent.key(
                code=self.input_combination[1].code,
                value=1,
                origin_hash=self.input_combination[1].origin_hash,
            ),
            source=fixtures.foo_device_2_keyboard,
        )
        self.handler.notify(
            InputEvent.key(
                code=self.input_combination[2].code,
                value=1,
                origin_hash=self.input_combination[2].origin_hash,
            ),
            source=fixtures.gamepad,
        )

        # 2. expect release events to be written to the correct devices, as indicated
        # by the origin_hash of the InputConfigs
        self.assertListEqual(
            uinputs[self.mouse_hash].write_history,
            [InputEvent.rel(self.input_combination[0].code, 0)],
        )
        self.assertListEqual(
            uinputs[self.keyboard_hash].write_history,
            [InputEvent.key(self.input_combination[1].code, 0)],
        )
        self.assertListEqual(
            uinputs[self.gamepad_hash].write_history,
            [InputEvent.key(self.input_combination[2].code, 0)],
        )

    def test_no_forwards(self):
        # if a combination is not triggered, nothing is released
        mock = MagicMock()
        self.handler.set_sub_handler(mock)

        # insert our own test-uinput to see what is being written to it
        uinputs = {
            self.mouse_hash: evdev.UInput(),
            self.keyboard_hash: evdev.UInput(),
        }
        self.context_mock.get_forward_uinput = lambda origin_hash: uinputs[origin_hash]

        # 1. inject any two events
        self.handler.notify(
            InputEvent.rel(
                code=self.input_combination[0].code,
                value=1,
                origin_hash=self.input_combination[0].origin_hash,
            ),
            source=fixtures.foo_device_2_mouse,
        )
        self.handler.notify(
            InputEvent.key(
                code=self.input_combination[1].code,
                value=1,
                origin_hash=self.input_combination[1].origin_hash,
            ),
            source=fixtures.foo_device_2_keyboard,
        )

        # 2. expect no release events to be written
        self.assertListEqual(uinputs[self.mouse_hash].write_history, [])
        self.assertListEqual(uinputs[self.keyboard_hash].write_history, [])


@test_setup
class TestHierarchyHandler(BaseTests, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock1 = MagicMock()
        self.mock2 = MagicMock()
        self.mock3 = MagicMock()
        self.global_uinputs = GlobalUInputs(UInput)
        self.global_uinputs.prepare_all()
        self.handler = HierarchyHandler(
            [self.mock1, self.mock2, self.mock3],
            InputConfig(type=EV_KEY, code=KEY_A),
            self.global_uinputs,
        )

    def test_reset(self):
        self.handler.reset()
        self.mock1.reset.assert_called()
        self.mock2.reset.assert_called()
        self.mock3.reset.assert_called()


@test_setup
class TestKeyHandler(BaseTests, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        input_combination = InputCombination(
            (
                InputConfig(type=2, code=0, analog_threshold=10),
                InputConfig(type=1, code=3),
            )
        )
        self.global_uinputs = GlobalUInputs(UInput)
        self.global_uinputs.prepare_all()
        self.handler = KeyHandler(
            input_combination,
            Mapping(
                input_combination=input_combination.to_config(),
                target_uinput="mouse",
                output_symbol="BTN_LEFT",
            ),
            self.global_uinputs,
        )

    def test_reset(self):
        self.handler.notify(
            InputEvent(0, 0, EV_REL, REL_X, 1, actions=(EventActions.as_key,)),
            source=InputDevice("/dev/input/event11"),
        )
        history = self.global_uinputs.get_uinput("mouse").write_history
        self.assertEqual(history[0], InputEvent.key(BTN_LEFT, 1))
        self.assertEqual(len(history), 1)

        self.handler.reset()
        history = self.global_uinputs.get_uinput("mouse").write_history
        self.assertEqual(history[1], InputEvent.key(BTN_LEFT, 0))
        self.assertEqual(len(history), 2)


@test_setup
class TestMacroHandler(BaseTests, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        input_combination = InputCombination(
            (
                InputConfig(type=2, code=0, analog_threshold=10),
                InputConfig(type=1, code=3),
            )
        )
        self.context_mock = MagicMock()
        self.global_uinputs = GlobalUInputs(UInput)
        self.global_uinputs.prepare_all()
        self.handler = MacroHandler(
            input_combination,
            Mapping(
                input_combination=input_combination.to_config(),
                target_uinput="mouse",
                output_symbol="hold_keys(BTN_LEFT, BTN_RIGHT)",
            ),
            context=self.context_mock,
            global_uinputs=self.global_uinputs,
        )

    async def test_reset(self):
        self.handler.notify(
            InputEvent(0, 0, EV_REL, REL_X, 1, actions=(EventActions.as_key,)),
            source=InputDevice("/dev/input/event11"),
        )

        await asyncio.sleep(0.1)
        history = self.global_uinputs.get_uinput("mouse").write_history
        self.assertIn(InputEvent.key(BTN_LEFT, 1), history)
        self.assertIn(InputEvent.key(BTN_RIGHT, 1), history)
        self.assertEqual(len(history), 2)

        self.handler.reset()
        await asyncio.sleep(0.1)
        history = self.global_uinputs.get_uinput("mouse").write_history
        self.assertIn(InputEvent.key(BTN_LEFT, 0), history[-2:])
        self.assertIn(InputEvent.key(BTN_RIGHT, 0), history[-2:])
        self.assertEqual(len(history), 4)


@test_setup
class TestRelToBtnHandler(BaseTests, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        input_combination = InputCombination(
            [InputConfig(type=2, code=0, analog_threshold=10)]
        )
        self.global_uinputs = GlobalUInputs(UInput)
        self.global_uinputs.prepare_all()
        self.handler = RelToBtnHandler(
            input_combination,
            Mapping(
                input_combination=input_combination.to_config(),
                target_uinput="mouse",
                output_symbol="BTN_LEFT",
            ),
            self.global_uinputs,
        )


@test_setup
class TestRelToRelHanlder(BaseTests, unittest.IsolatedAsyncioTestCase):
    handler: RelToRelHandler

    def setUp(self):
        input_combination = InputCombination([InputConfig(type=EV_REL, code=REL_X)])
        self.global_uinputs = GlobalUInputs(UInput)
        self.global_uinputs.prepare_all()
        self.handler = RelToRelHandler(
            input_combination,
            Mapping(
                input_combination=input_combination.to_config(),
                output_type=EV_REL,
                output_code=REL_Y,
                output_value=20,
                target_uinput="mouse",
            ),
            self.global_uinputs,
        )

    def test_should_map(self):
        self.assertTrue(
            self.handler._should_map(
                InputEvent(
                    0,
                    0,
                    EV_REL,
                    REL_X,
                    0,
                )
            )
        )
        self.assertFalse(
            self.handler._should_map(
                InputEvent(
                    0,
                    0,
                    EV_REL,
                    REL_WHEEL,
                    1,
                )
            )
        )

    def test_reset(self):
        # nothing special has to happen here
        pass
