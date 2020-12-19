#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2020 sezanzeb <proxima@hip70890b.de>
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

from evdev.ecodes import EV_REL, REL_X, REL_Y, REL_WHEEL, REL_HWHEEL

from keymapper.dev.ev_abs_mapper import ev_abs_mapper
from keymapper.config import config
from keymapper.dev.ev_abs_mapper import MOUSE, WHEEL

from tests.test import InputDevice, UInput, MAX_ABS, clear_write_history, \
    uinput_write_history


abs_state = [0, 0, 0, 0]


SPEED = 20


class TestEvAbsMapper(unittest.TestCase):
    # there is also `test_abs_to_rel` in test_injector.py
    def setUp(self):
        config.set('gamepad.joystick.non_linearity', 1)
        config.set('gamepad.joystick.pointer_speed', SPEED)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        device = InputDevice('/dev/input/event30')
        uinput = UInput()
        asyncio.ensure_future(ev_abs_mapper(abs_state, device, uinput))

    def tearDown(self):
        config.clear_config()
        loop = asyncio.get_event_loop()

        for task in asyncio.Task.all_tasks():
            task.cancel()

        loop.stop()
        loop.close()
        clear_write_history()

    def do(self, a, b, c, d, expectation):
        """Present fake values to the loop and observe the outcome."""
        clear_write_history()
        abs_state[0] = a
        abs_state[1] = b
        abs_state[2] = c
        abs_state[3] = d
        # 3 frames
        loop = asyncio.get_event_loop()
        loop.run_until_complete(asyncio.sleep(3 / 60))
        history = [h.t for h in uinput_write_history]
        # sleep long enough to test if multiple events are written
        self.assertGreater(len(history), 1)
        self.assertIn(expectation, history)
        self.assertEqual(history.count(expectation), len(history))

    def test_joystick_purpose_1(self):
        config.set('gamepad.joystick.left_purpose', MOUSE)
        config.set('gamepad.joystick.right_purpose', WHEEL)

        self.do(MAX_ABS, 0, 0, 0, (EV_REL, REL_X, SPEED))
        self.do(-MAX_ABS, 0, 0, 0, (EV_REL, REL_X, -SPEED))
        self.do(0, MAX_ABS, 0, 0, (EV_REL, REL_Y, SPEED))
        self.do(0, -MAX_ABS, 0, 0, (EV_REL, REL_Y, -SPEED))

        # wheel event values are negative
        self.do(0, 0, MAX_ABS, 0, (EV_REL, REL_HWHEEL, -1))
        self.do(0, 0, -MAX_ABS, 0, (EV_REL, REL_HWHEEL, 1))
        self.do(0, 0, 0, MAX_ABS, (EV_REL, REL_WHEEL, -1))
        self.do(0, 0, 0, -MAX_ABS, (EV_REL, REL_WHEEL, 1))

    def test_joystick_purpose_2(self):
        config.set('gamepad.joystick.left_purpose', WHEEL)
        config.set('gamepad.joystick.right_purpose', MOUSE)

        self.do(MAX_ABS, 0, 0, 0, (EV_REL, REL_HWHEEL, -1))
        self.do(-MAX_ABS, 0, 0, 0, (EV_REL, REL_HWHEEL, 1))
        self.do(0, MAX_ABS, 0, 0, (EV_REL, REL_WHEEL, -1))
        self.do(0, -MAX_ABS, 0, 0, (EV_REL, REL_WHEEL, 1))

        # wheel event values are negative
        self.do(0, 0, MAX_ABS, 0, (EV_REL, REL_X, SPEED))
        self.do(0, 0, -MAX_ABS, 0, (EV_REL, REL_X, -SPEED))
        self.do(0, 0, 0, MAX_ABS, (EV_REL, REL_Y, SPEED))
        self.do(0, 0, 0, -MAX_ABS, (EV_REL, REL_Y, -SPEED))

    def test_joystick_purpose_3(self):
        config.set('gamepad.joystick.left_purpose', MOUSE)
        config.set('gamepad.joystick.right_purpose', MOUSE)

        self.do(MAX_ABS, 0, 0, 0, (EV_REL, REL_X, SPEED))
        self.do(-MAX_ABS, 0, 0, 0, (EV_REL, REL_X, -SPEED))
        self.do(0, MAX_ABS, 0, 0, (EV_REL, REL_Y, SPEED))
        self.do(0, -MAX_ABS, 0, 0, (EV_REL, REL_Y, -SPEED))

        # wheel event values are negative
        self.do(0, 0, MAX_ABS, 0, (EV_REL, REL_X, SPEED))
        self.do(0, 0, -MAX_ABS, 0, (EV_REL, REL_X, -SPEED))
        self.do(0, 0, 0, MAX_ABS, (EV_REL, REL_Y, SPEED))
        self.do(0, 0, 0, -MAX_ABS, (EV_REL, REL_Y, -SPEED))

    def test_joystick_purpose_4(self):
        config.set('gamepad.joystick.left_purpose', WHEEL)
        config.set('gamepad.joystick.right_purpose', WHEEL)

        self.do(MAX_ABS, 0, 0, 0, (EV_REL, REL_HWHEEL, -1))
        self.do(-MAX_ABS, 0, 0, 0, (EV_REL, REL_HWHEEL, 1))
        self.do(0, MAX_ABS, 0, 0, (EV_REL, REL_WHEEL, -1))
        self.do(0, -MAX_ABS, 0, 0, (EV_REL, REL_WHEEL, 1))

        # wheel event values are negative
        self.do(0, 0, MAX_ABS, 0, (EV_REL, REL_HWHEEL, -1))
        self.do(0, 0, -MAX_ABS, 0, (EV_REL, REL_HWHEEL, 1))
        self.do(0, 0, 0, MAX_ABS, (EV_REL, REL_WHEEL, -1))
        self.do(0, 0, 0, -MAX_ABS, (EV_REL, REL_WHEEL, 1))


if __name__ == "__main__":
    unittest.main()
