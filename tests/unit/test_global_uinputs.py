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


from tests.test import cleanup

import sys
import unittest
import evdev

from unittest.mock import patch
from evdev.ecodes import (
    EV_KEY,
    EV_ABS,
    KEY_A,
    ABS_X,
)

from inputremapper.injection.global_uinputs import (
    global_uinputs,
    FrontendUInput,
    UInput,
    GlobalUInputs,
)
from inputremapper.exceptions import EventNotHandled, UinputNotAvailable


class TestFrontendUinput(unittest.TestCase):
    def setUp(self) -> None:
        cleanup()

    def test_init(self):
        name = "foo"
        capabilities = {1: [1, 2, 3], 2: [4, 5, 6]}
        uinput_defaults = FrontendUInput()
        uinput_custom = FrontendUInput(name=name, events=capabilities)

        self.assertEqual(uinput_defaults.name, "py-evdev-uinput")
        self.assertIsNone(uinput_defaults.capabilities())

        self.assertEqual(uinput_custom.name, name)
        self.assertEqual(uinput_custom.capabilities(), capabilities)


class TestGlobalUinputs(unittest.TestCase):
    def setUp(self) -> None:
        cleanup()

    def test_iter(self):
        for uinput in global_uinputs:
            self.assertIsInstance(uinput, evdev.UInput)

    def test_write(self):
        """test write and write failure

        implicitly tests get_uinput and UInput.can_emit
        """
        ev_1 = (EV_KEY, KEY_A, 1)
        ev_2 = (EV_ABS, ABS_X, 10)

        keyboard = global_uinputs.get_uinput("keyboard")

        global_uinputs.write(ev_1, "keyboard")
        self.assertEqual(keyboard.write_count, 1)

        with self.assertRaises(EventNotHandled):
            global_uinputs.write(ev_2, "keyboard")

        with self.assertRaises(UinputNotAvailable):
            global_uinputs.write(ev_1, "foo")

    def test_creates_frontend_uinputs(self):
        frontend_uinputs = GlobalUInputs()
        with patch.object(sys, "argv", ["foo"]):
            frontend_uinputs.prepare()

        uinput = frontend_uinputs.get_uinput("keyboard")
        self.assertIsInstance(uinput, FrontendUInput)
