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

import evdev
from dataclasses import FrozenInstanceError
from inputremapper.input_event import InputEvent
from inputremapper.exceptions import InputEventCreationError


class TestInputEvent(unittest.TestCase):
    def test_from_event(self):
        e1 = InputEvent.from_event(evdev.InputEvent(1, 2, 3, 4, 5))
        e2 = InputEvent.from_event(e1)

        self.assertEqual(e1, e2)
        self.assertEqual(e1.sec, 1)
        self.assertEqual(e1.usec, 2)
        self.assertEqual(e1.type, 3)
        self.assertEqual(e1.code, 4)
        self.assertEqual(e1.value, 5)

        self.assertEqual(e1.sec, e2.sec)
        self.assertEqual(e1.usec, e2.usec)
        self.assertEqual(e1.type, e2.type)
        self.assertEqual(e1.code, e2.code)
        self.assertEqual(e1.value, e2.value)

        self.assertRaises(InputEventCreationError, InputEvent.from_event, "1,2,3")

    def test_from_string(self):
        s1 = "1,2,3"
        s2 = "1 ,2, 3 "
        s3 = (1, 2, 3)
        s4 = "1,2,3,4"
        s5 = "1,2,_3"

        e1 = InputEvent.from_string(s1)
        e2 = InputEvent.from_string(s2)
        self.assertEqual(e1, e2)
        self.assertEqual(e1.sec, 0)
        self.assertEqual(e1.usec, 0)
        self.assertEqual(e1.type, 1)
        self.assertEqual(e1.code, 2)
        self.assertEqual(e1.value, 3)

        self.assertRaises(InputEventCreationError, InputEvent.from_string, s3)
        self.assertRaises(InputEventCreationError, InputEvent.from_string, s4)
        self.assertRaises(InputEventCreationError, InputEvent.from_string, s5)

    def test_from_event_tuple(self):
        t1 = (1, 2, 3)
        t2 = (1, "2", 3)
        t3 = (1, 2, 3, 4, 5)
        t4 = (1, "b", 3)

        e1 = InputEvent.from_tuple(t1)
        e2 = InputEvent.from_tuple(t2)
        self.assertEqual(e1, e2)
        self.assertEqual(e1.sec, 0)
        self.assertEqual(e1.usec, 0)
        self.assertEqual(e1.type, 1)
        self.assertEqual(e1.code, 2)
        self.assertEqual(e1.value, 3)

        self.assertRaises(InputEventCreationError, InputEvent.from_string, t3)
        self.assertRaises(InputEventCreationError, InputEvent.from_string, t4)

    def test_properties(self):
        e1 = InputEvent.btn_left()
        self.assertEqual(
            e1.event_tuple, (evdev.ecodes.EV_KEY, evdev.ecodes.BTN_LEFT, 1)
        )
        self.assertEqual(e1.type_and_code, (evdev.ecodes.EV_KEY, evdev.ecodes.BTN_LEFT))

        with self.assertRaises(TypeError):
            e1.event_tuple = (1, 2, 3)

        with self.assertRaises(TypeError):
            e1.type_and_code = (1, 2)

        with self.assertRaises(FrozenInstanceError):
            e1.value = 5

    def test_modify(self):
        e1 = InputEvent(1, 2, 3, 4, 5)
        e2 = e1.modify(value=6)
        e3 = e1.modify(sec=0, usec=0, type=0, code=0, value=0)

        self.assertNotEqual(e1, e2)
        self.assertEqual(e1.sec, e2.sec)
        self.assertEqual(e1.usec, e2.usec)
        self.assertEqual(e1.type, e2.type)
        self.assertEqual(e1.code, e2.code)
        self.assertNotEqual(e1.value, e2.value)
        self.assertEqual(e3.sec, 0)
        self.assertEqual(e3.usec, 0)
        self.assertEqual(e3.type, 0)
        self.assertEqual(e3.code, 0)
        self.assertEqual(e3.value, 0)
