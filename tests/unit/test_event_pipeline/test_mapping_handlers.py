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
)

from inputremapper.configs.mapping import Mapping
from inputremapper.event_combination import EventCombination
from inputremapper.injection.global_uinputs import global_uinputs
from inputremapper.injection.mapping_handlers.abs_to_abs_handler import AbsToAbsHandler
from inputremapper.injection.mapping_handlers.abs_to_btn_handler import AbsToBtnHandler
from inputremapper.injection.mapping_handlers.abs_to_rel_handler import AbsToRelHandler
from inputremapper.injection.mapping_handlers.axis_switch_handler import (
    AxisSwitchHandler,
)
from inputremapper.injection.mapping_handlers.hierarchy_handler import HierarchyHandler
from inputremapper.injection.mapping_handlers.key_handler import KeyHandler
from inputremapper.injection.mapping_handlers.macro_handler import MacroHandler
from inputremapper.injection.mapping_handlers.mapping_handler import MappingHandler
from inputremapper.injection.mapping_handlers.rel_to_abs_handler import RelToAbsHandler
from inputremapper.input_event import InputEvent, EventActions
from tests.test import (
    InputDevice,
    cleanup,
    convert_to_internal_events,
    MAX_ABS,
)


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


class TestAxisSwitchHandler(BaseTests, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.handler = AxisSwitchHandler(
            EventCombination.from_string("2,5,0+1,3,1"),
            Mapping(
                event_combination="2,5,0+1,3,1",
                target_uinput="mouse",
                output_type=2,
                output_code=1,
            ),
        )


class TestAbsToBtnHandler(BaseTests, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.handler = AbsToBtnHandler(
            EventCombination.from_string("3,5,10"),
            Mapping(
                event_combination="3,5,10",
                target_uinput="mouse",
                output_symbol="BTN_LEFT",
            ),
        )


class TestAbsToAbsHandler(BaseTests, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.handler = AbsToAbsHandler(
            EventCombination((EV_ABS, ABS_X, 0)),
            Mapping(
                event_combination=f"{EV_ABS},{ABS_X},0",
                target_uinput="gamepad",
                output_type=EV_ABS,
                output_code=ABS_X,
            ),
        )

    async def test_reset(self):
        self.handler.notify(
            InputEvent(0, 0, EV_ABS, ABS_X, MAX_ABS),
            source=InputDevice("/dev/input/event15"),
            forward=evdev.UInput(),
        )
        self.handler.reset()
        history = global_uinputs.get_uinput("gamepad").write_history
        self.assertEqual(
            history,
            [InputEvent.from_tuple((3, 0, 32768)), InputEvent.from_tuple((3, 0, 0))],
        )


class TestRelToAbsHandler(BaseTests, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.handler = RelToAbsHandler(
            EventCombination((EV_REL, REL_X, 0)),
            Mapping(
                event_combination=f"{EV_REL},{REL_X},0",
                target_uinput="gamepad",
                output_type=EV_ABS,
                output_code=ABS_X,
            ),
        )

    async def test_reset(self):
        self.handler.notify(
            InputEvent(0, 0, EV_REL, REL_X, 100),
            source=InputDevice("/dev/input/event15"),
            forward=evdev.UInput(),
        )
        self.handler.reset()
        history = global_uinputs.get_uinput("gamepad").write_history
        self.assertEqual(
            history,
            [InputEvent.from_tuple((3, 0, 32768)), InputEvent.from_tuple((3, 0, 0))],
        )


class TestAbsToRelHandler(BaseTests, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.handler = AbsToRelHandler(
            EventCombination((EV_ABS, ABS_X, 0)),
            Mapping(
                event_combination=f"{EV_ABS},{ABS_X},0",
                target_uinput="mouse",
                output_type=EV_REL,
                output_code=REL_X,
            ),
        )

    async def test_reset(self):
        self.handler.notify(
            InputEvent(0, 0, EV_ABS, ABS_X, MAX_ABS),
            source=InputDevice("/dev/input/event15"),
            forward=evdev.UInput(),
        )
        await asyncio.sleep(0.2)
        self.handler.reset()
        await asyncio.sleep(0.05)

        count = global_uinputs.get_uinput("mouse").write_count
        self.assertGreater(count, 6)  # count should be 60*0.2 = 12
        await asyncio.sleep(0.2)
        self.assertEqual(count, global_uinputs.get_uinput("mouse").write_count)


class TestCombinationHandler(BaseTests, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.handler = AxisSwitchHandler(
            EventCombination.from_string("2,0,10+1,3,1"),
            Mapping(
                event_combination="2,0,10+1,3,1",
                target_uinput="mouse",
                output_symbol="BTN_LEFT",
            ),
        )


class TestHierarchyHandler(BaseTests, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock1 = MagicMock()
        self.mock2 = MagicMock()
        self.mock3 = MagicMock()
        self.handler = HierarchyHandler(
            [self.mock1, self.mock2, self.mock3],
            InputEvent.from_tuple((EV_KEY, KEY_A, 1)),
        )

    def test_reset(self):
        self.handler.reset()
        self.mock1.reset.assert_called()
        self.mock2.reset.assert_called()
        self.mock3.reset.assert_called()


class TestKeyHandler(BaseTests, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.handler = KeyHandler(
            EventCombination.from_string("2,0,10+1,3,1"),
            Mapping(
                event_combination="2,0,10+1,3,1",
                target_uinput="mouse",
                output_symbol="BTN_LEFT",
            ),
        )

    def test_reset(self):
        self.handler.notify(
            InputEvent(0, 0, EV_REL, REL_X, 1, actions=(EventActions.as_key,)),
            source=InputDevice("/dev/input/event11"),
            forward=evdev.UInput(),
        )
        history = convert_to_internal_events(
            global_uinputs.get_uinput("mouse").write_history
        )
        self.assertEqual(history[0], InputEvent.from_tuple((EV_KEY, BTN_LEFT, 1)))
        self.assertEqual(len(history), 1)

        self.handler.reset()
        history = convert_to_internal_events(
            global_uinputs.get_uinput("mouse").write_history
        )
        self.assertEqual(history[1], InputEvent.from_tuple((EV_KEY, BTN_LEFT, 0)))
        self.assertEqual(len(history), 2)


class TestMacroHandler(BaseTests, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.context_mock = MagicMock()
        self.handler = MacroHandler(
            EventCombination.from_string("2,0,10+1,3,1"),
            Mapping(
                event_combination="2,0,10+1,3,1",
                target_uinput="mouse",
                output_symbol="hold_keys(BTN_LEFT, BTN_RIGHT)",
            ),
            context=self.context_mock,
        )

    async def test_reset(self):
        self.handler.notify(
            InputEvent(0, 0, EV_REL, REL_X, 1, actions=(EventActions.as_key,)),
            source=InputDevice("/dev/input/event11"),
            forward=evdev.UInput(),
        )

        await asyncio.sleep(0.1)
        history = convert_to_internal_events(
            global_uinputs.get_uinput("mouse").write_history
        )
        self.assertIn(InputEvent.from_tuple((EV_KEY, BTN_LEFT, 1)), history)
        self.assertIn(InputEvent.from_tuple((EV_KEY, BTN_RIGHT, 1)), history)
        self.assertEqual(len(history), 2)

        self.handler.reset()
        await asyncio.sleep(0.1)
        history = convert_to_internal_events(
            global_uinputs.get_uinput("mouse").write_history
        )
        self.assertIn(InputEvent.from_tuple((EV_KEY, BTN_LEFT, 0)), history[-2:])
        self.assertIn(InputEvent.from_tuple((EV_KEY, BTN_RIGHT, 0)), history[-2:])
        self.assertEqual(len(history), 4)


class TestRelToBtnHanlder(BaseTests, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.handler = AxisSwitchHandler(
            EventCombination.from_string("2,0,10+1,3,1"),
            Mapping(
                event_combination="2,0,10+1,3,1",
                target_uinput="mouse",
                output_symbol="BTN_LEFT",
            ),
        )
