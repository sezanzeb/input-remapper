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


from tests.test import new_event, InputDevice, MAX_ABS, MIN_ABS

import unittest

from evdev import ecodes
from evdev.ecodes import (
    EV_KEY,
    EV_ABS,
    ABS_HAT0X,
    KEY_A,
    EV_REL,
    REL_X,
    REL_WHEEL,
    REL_HWHEEL,
)

from inputremapper.configs.global_config import global_config, BUTTONS
from inputremapper.configs.preset import Preset
from inputremapper import utils


class TestDevUtils(unittest.TestCase):
    def test_max_abs(self):
        self.assertEqual(
            utils.get_abs_range(InputDevice("/dev/input/event30"))[1], MAX_ABS
        )
        self.assertIsNone(utils.get_abs_range(InputDevice("/dev/input/event10")))

    def test_will_report_key_up(self):
        self.assertFalse(utils.will_report_key_up(new_event(EV_REL, REL_WHEEL, 1)))
        self.assertFalse(utils.will_report_key_up(new_event(EV_REL, REL_HWHEEL, -1)))
        self.assertTrue(utils.will_report_key_up(new_event(EV_KEY, KEY_A, 1)))
        self.assertTrue(utils.will_report_key_up(new_event(EV_ABS, ABS_HAT0X, -1)))

    def test_is_wheel(self):
        self.assertTrue(utils.is_wheel(new_event(EV_REL, REL_WHEEL, 1)))
        self.assertTrue(utils.is_wheel(new_event(EV_REL, REL_HWHEEL, -1)))
        self.assertFalse(utils.is_wheel(new_event(EV_KEY, KEY_A, 1)))
        self.assertFalse(utils.is_wheel(new_event(EV_ABS, ABS_HAT0X, -1)))

    def test_should_map_as_btn(self):
        mapping = Preset()

        def do(gamepad, event):
            return utils.should_map_as_btn(event, mapping, gamepad)

        """D-Pad"""

        self.assertTrue(do(1, new_event(EV_ABS, ABS_HAT0X, 1)))
        self.assertTrue(do(0, new_event(EV_ABS, ABS_HAT0X, -1)))

        """Mouse movements"""

        self.assertTrue(do(1, new_event(EV_REL, REL_WHEEL, 1)))
        self.assertTrue(do(0, new_event(EV_REL, REL_WHEEL, -1)))
        self.assertTrue(do(1, new_event(EV_REL, REL_HWHEEL, 1)))
        self.assertTrue(do(0, new_event(EV_REL, REL_HWHEEL, -1)))
        self.assertFalse(do(1, new_event(EV_REL, REL_X, -1)))

        """regular keys and buttons"""

        self.assertTrue(do(1, new_event(EV_KEY, KEY_A, 1)))
        self.assertTrue(do(0, new_event(EV_KEY, KEY_A, 1)))
        self.assertTrue(do(1, new_event(EV_ABS, ABS_HAT0X, -1)))
        self.assertTrue(do(0, new_event(EV_ABS, ABS_HAT0X, -1)))

        """mousepad events"""

        self.assertFalse(do(1, new_event(EV_ABS, ecodes.ABS_MT_SLOT, 1)))
        self.assertFalse(do(0, new_event(EV_ABS, ecodes.ABS_MT_SLOT, 1)))
        self.assertFalse(do(1, new_event(EV_ABS, ecodes.ABS_MT_TOOL_Y, 1)))
        self.assertFalse(do(0, new_event(EV_ABS, ecodes.ABS_MT_TOOL_Y, 1)))
        self.assertFalse(do(1, new_event(EV_ABS, ecodes.ABS_MT_POSITION_X, 1)))
        self.assertFalse(do(0, new_event(EV_ABS, ecodes.ABS_MT_POSITION_X, 1)))
        self.assertFalse(do(1, new_event(EV_KEY, ecodes.BTN_TOUCH, 1)))
        self.assertFalse(do(0, new_event(EV_KEY, ecodes.BTN_TOUCH, 1)))

        """stylus movements"""

        self.assertFalse(do(0, new_event(EV_KEY, ecodes.BTN_DIGI, 1)))
        self.assertFalse(do(1, new_event(EV_KEY, ecodes.BTN_DIGI, 1)))
        self.assertFalse(do(0, new_event(EV_ABS, ecodes.ABS_TILT_X, 1)))
        self.assertFalse(do(1, new_event(EV_ABS, ecodes.ABS_TILT_X, 1)))
        self.assertFalse(do(0, new_event(EV_ABS, ecodes.ABS_TILT_Y, 1)))
        self.assertFalse(do(1, new_event(EV_ABS, ecodes.ABS_TILT_Y, 1)))
        self.assertFalse(do(0, new_event(EV_ABS, ecodes.ABS_DISTANCE, 1)))
        self.assertFalse(do(1, new_event(EV_ABS, ecodes.ABS_DISTANCE, 1)))
        self.assertFalse(do(0, new_event(EV_ABS, ecodes.ABS_PRESSURE, 1)))
        self.assertFalse(do(1, new_event(EV_ABS, ecodes.ABS_PRESSURE, 1)))

        """joysticks"""

        # we no longer track the purpose for the gamepad sticks, it is always allowed to map them as buttons
        self.assertFalse(do(0, new_event(EV_ABS, ecodes.ABS_Y, -1)))
        self.assertTrue(do(1, new_event(EV_ABS, ecodes.ABS_Y, -1)))
        self.assertFalse(do(0, new_event(EV_ABS, ecodes.ABS_RY, -1)))
        self.assertTrue(do(1, new_event(EV_ABS, ecodes.ABS_RY, -1)))

        """weird events"""

        self.assertFalse(do(0, new_event(EV_ABS, ecodes.ABS_MISC, -1)))
        self.assertFalse(do(1, new_event(EV_ABS, ecodes.ABS_MISC, -1)))

    def test_classify_action(self):
        """"""

        """0 to MAX_ABS"""

        def do(event):
            return utils.classify_action(event, (0, MAX_ABS))

        event = new_event(EV_ABS, ecodes.ABS_RX, MAX_ABS)
        self.assertEqual(do(event), 1)
        event = new_event(EV_ABS, ecodes.ABS_Y, MAX_ABS)
        self.assertEqual(do(event), 1)
        event = new_event(EV_ABS, ecodes.ABS_Y, 0)
        self.assertEqual(do(event), -1)
        event = new_event(EV_ABS, ecodes.ABS_X, MAX_ABS // 4)
        self.assertEqual(do(event), -1)
        event = new_event(EV_ABS, ecodes.ABS_X, MAX_ABS // 2)
        self.assertEqual(do(event), 0)

        """MIN_ABS to MAX_ABS"""

        def do2(event):
            return utils.classify_action(event, (MIN_ABS, MAX_ABS))

        event = new_event(EV_ABS, ecodes.ABS_RX, MAX_ABS)
        self.assertEqual(do2(event), 1)
        event = new_event(EV_ABS, ecodes.ABS_Y, MIN_ABS)
        self.assertEqual(do2(event), -1)
        event = new_event(EV_ABS, ecodes.ABS_X, MIN_ABS // 4)
        self.assertEqual(do2(event), 0)
        event = new_event(EV_ABS, ecodes.ABS_RX, MAX_ABS)
        self.assertEqual(do2(event), 1)
        event = new_event(EV_ABS, ecodes.ABS_Y, MAX_ABS)
        self.assertEqual(do2(event), 1)
        event = new_event(EV_ABS, ecodes.ABS_X, MAX_ABS // 4)
        self.assertEqual(do2(event), 0)

        """None"""

        # it just forwards the value
        event = new_event(EV_ABS, ecodes.ABS_RX, MAX_ABS)
        self.assertEqual(utils.classify_action(event, None), MAX_ABS)

        """Not a joystick"""

        event = new_event(EV_ABS, ecodes.ABS_Z, 1234)
        self.assertEqual(do(event), 1)
        self.assertEqual(do2(event), 1)
        event = new_event(EV_ABS, ecodes.ABS_Z, 0)
        self.assertEqual(do(event), 0)
        self.assertEqual(do2(event), 0)
        event = new_event(EV_ABS, ecodes.ABS_Z, -1234)
        self.assertEqual(do(event), -1)
        self.assertEqual(do2(event), -1)

        event = new_event(EV_KEY, ecodes.KEY_A, 1)
        self.assertEqual(do(event), 1)
        self.assertEqual(do2(event), 1)
        event = new_event(EV_ABS, ecodes.ABS_HAT0X, 0)
        self.assertEqual(do(event), 0)
        self.assertEqual(do2(event), 0)
        event = new_event(EV_ABS, ecodes.ABS_HAT0X, -1)
        self.assertEqual(do(event), -1)
        self.assertEqual(do2(event), -1)
