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


from tests.test import (
    InputDevice,
    UInput,
    MAX_ABS,
    clear_write_history,
    uinput_write_history,
    quick_cleanup,
    new_event,
    MIN_ABS,
)

import unittest
import asyncio

from evdev.ecodes import (
    EV_REL,
    REL_X,
    REL_Y,
    REL_WHEEL,
    REL_HWHEEL,
    EV_ABS,
    ABS_X,
    ABS_Y,
    ABS_RX,
    ABS_RY,
)

from inputremapper.configs.global_config import global_config
from inputremapper.configs.preset import Preset
from inputremapper.injection.context import Context
from inputremapper.injection.consumers.joystick_to_mouse import (
    JoystickToMouse,
    MOUSE,
    WHEEL,
)


abs_state = [0, 0, 0, 0]


class TestJoystickToMouse(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.mapping = Preset()
        self.context = Context(self.mapping)

        uinput = UInput()
        self.context.uinput = uinput

        source = InputDevice("/dev/input/event30")
        self.joystick_to_mouse = JoystickToMouse(self.context, source)

        global_config.set("gamepad.joystick.x_scroll_speed", 1)
        global_config.set("gamepad.joystick.y_scroll_speed", 1)

    def tearDown(self):
        quick_cleanup()

    def assertClose(self, a, b, within):
        """a has to be within b - b * within, b + b * within."""
        self.assertLess(a - abs(a) * within, b)
        self.assertGreater(a + abs(a) * within, b)

    async def test_assertClose(self):
        self.assertClose(5, 5, 0.1)
        self.assertClose(5, 5, 1)
        self.assertClose(6, 5, 0.2)
        self.assertClose(4, 5, 0.3)
        self.assertRaises(AssertionError, lambda: self.assertClose(6, 5, 0.1))
        self.assertRaises(AssertionError, lambda: self.assertClose(4, 5, 0.1))

        self.assertClose(-5, -5, 0.1)
        self.assertClose(-5, -5, 1)
        self.assertClose(-6, -5, 0.2)
        self.assertClose(-4, -5, 0.3)
        self.assertRaises(AssertionError, lambda: self.assertClose(-6, -5, 0.1))
        self.assertRaises(AssertionError, lambda: self.assertClose(-4, -5, 0.1))

    async def do(self, a, b, c, d, expectation):
        """Present fake values to the loop and observe the outcome.

        Depending on the configuration, the cursor or wheel should move.
        """
        clear_write_history()
        self.joystick_to_mouse.context.update_purposes()
        await self.joystick_to_mouse.notify(new_event(EV_ABS, ABS_X, a))
        await self.joystick_to_mouse.notify(new_event(EV_ABS, ABS_Y, b))
        await self.joystick_to_mouse.notify(new_event(EV_ABS, ABS_RX, c))
        await self.joystick_to_mouse.notify(new_event(EV_ABS, ABS_RY, d))

        # sleep long enough to test if multiple events are written
        await asyncio.sleep(5 / 60)

        history = [h.t for h in uinput_write_history]
        self.assertGreater(len(history), 1)
        self.assertIn(expectation, history)

        for history_entry in history:
            self.assertEqual(history_entry[:2], expectation[:2])
            # if the injected cursor movement is 19 or 20 doesn't really matter
            self.assertClose(history_entry[2], expectation[2], 0.1)

    async def test_joystick_purpose_1(self):
        asyncio.ensure_future(self.joystick_to_mouse.run())

        speed = 20
        self.mapping.set("gamepad.joystick.non_linearity", 1)
        self.mapping.set("gamepad.joystick.pointer_speed", speed)
        self.mapping.set("gamepad.joystick.left_purpose", MOUSE)
        self.mapping.set("gamepad.joystick.right_purpose", WHEEL)

        min_abs = 0
        # if `rest` is not exactly `max_abs / 2` decimal places might add up
        # and cause higher or lower values to be written after a few events,
        # which might be difficult to test.
        max_abs = 256
        rest = 128  # resting position of the cursor
        self.joystick_to_mouse.set_abs_range(min_abs, max_abs)

        await self.do(max_abs, rest, rest, rest, (EV_REL, REL_X, speed))
        await self.do(min_abs, rest, rest, rest, (EV_REL, REL_X, -speed))
        await self.do(rest, max_abs, rest, rest, (EV_REL, REL_Y, speed))
        await self.do(rest, min_abs, rest, rest, (EV_REL, REL_Y, -speed))

        # vertical wheel event values are negative
        await self.do(rest, rest, max_abs, rest, (EV_REL, REL_HWHEEL, 1))
        await self.do(rest, rest, min_abs, rest, (EV_REL, REL_HWHEEL, -1))
        await self.do(rest, rest, rest, max_abs, (EV_REL, REL_WHEEL, -1))
        await self.do(rest, rest, rest, min_abs, (EV_REL, REL_WHEEL, 1))

    async def test_joystick_purpose_2(self):
        asyncio.ensure_future(self.joystick_to_mouse.run())

        speed = 30
        global_config.set("gamepad.joystick.non_linearity", 1)
        global_config.set("gamepad.joystick.pointer_speed", speed)
        global_config.set("gamepad.joystick.left_purpose", WHEEL)
        global_config.set("gamepad.joystick.right_purpose", MOUSE)
        global_config.set("gamepad.joystick.x_scroll_speed", 1)
        global_config.set("gamepad.joystick.y_scroll_speed", 2)

        # vertical wheel event values are negative
        await self.do(MAX_ABS, 0, 0, 0, (EV_REL, REL_HWHEEL, 1))
        await self.do(MIN_ABS, 0, 0, 0, (EV_REL, REL_HWHEEL, -1))
        await self.do(0, MAX_ABS, 0, 0, (EV_REL, REL_WHEEL, -2))
        await self.do(0, MIN_ABS, 0, 0, (EV_REL, REL_WHEEL, 2))

        await self.do(0, 0, MAX_ABS, 0, (EV_REL, REL_X, speed))
        await self.do(0, 0, MIN_ABS, 0, (EV_REL, REL_X, -speed))
        await self.do(0, 0, 0, MAX_ABS, (EV_REL, REL_Y, speed))
        await self.do(0, 0, 0, MIN_ABS, (EV_REL, REL_Y, -speed))

    async def test_joystick_purpose_3(self):
        asyncio.ensure_future(self.joystick_to_mouse.run())

        speed = 40
        self.mapping.set("gamepad.joystick.non_linearity", 1)
        global_config.set("gamepad.joystick.pointer_speed", speed)
        self.mapping.set("gamepad.joystick.left_purpose", MOUSE)
        global_config.set("gamepad.joystick.right_purpose", MOUSE)

        await self.do(MAX_ABS, 0, 0, 0, (EV_REL, REL_X, speed))
        await self.do(MIN_ABS, 0, 0, 0, (EV_REL, REL_X, -speed))
        await self.do(0, MAX_ABS, 0, 0, (EV_REL, REL_Y, speed))
        await self.do(0, MIN_ABS, 0, 0, (EV_REL, REL_Y, -speed))

        await self.do(0, 0, MAX_ABS, 0, (EV_REL, REL_X, speed))
        await self.do(0, 0, MIN_ABS, 0, (EV_REL, REL_X, -speed))
        await self.do(0, 0, 0, MAX_ABS, (EV_REL, REL_Y, speed))
        await self.do(0, 0, 0, MIN_ABS, (EV_REL, REL_Y, -speed))

    async def test_joystick_purpose_4(self):
        asyncio.ensure_future(self.joystick_to_mouse.run())

        global_config.set("gamepad.joystick.left_purpose", WHEEL)
        global_config.set("gamepad.joystick.right_purpose", WHEEL)
        self.mapping.set("gamepad.joystick.x_scroll_speed", 2)
        self.mapping.set("gamepad.joystick.y_scroll_speed", 3)

        await self.do(MAX_ABS, 0, 0, 0, (EV_REL, REL_HWHEEL, 2))
        await self.do(MIN_ABS, 0, 0, 0, (EV_REL, REL_HWHEEL, -2))
        await self.do(0, MAX_ABS, 0, 0, (EV_REL, REL_WHEEL, -3))
        await self.do(0, MIN_ABS, 0, 0, (EV_REL, REL_WHEEL, 3))

        # vertical wheel event values are negative
        await self.do(0, 0, MAX_ABS, 0, (EV_REL, REL_HWHEEL, 2))
        await self.do(0, 0, MIN_ABS, 0, (EV_REL, REL_HWHEEL, -2))
        await self.do(0, 0, 0, MAX_ABS, (EV_REL, REL_WHEEL, -3))
        await self.do(0, 0, 0, MIN_ABS, (EV_REL, REL_WHEEL, 3))


if __name__ == "__main__":
    unittest.main()
