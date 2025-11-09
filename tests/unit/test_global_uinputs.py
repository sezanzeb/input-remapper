#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2025 sezanzeb <b8x45ygc9@mozmail.com>
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
from evdev.ecodes import (
    KEY_A,
    ABS_X,
)

from inputremapper.exceptions import EventNotHandled, UinputNotAvailable
from inputremapper.injection.global_uinputs import (
    FrontendUInput,
    GlobalUInputs,
    UInput,
)
from inputremapper.input_event import InputEvent
from tests.lib.cleanup import cleanup
from tests.lib.test_setup import test_setup


@test_setup
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


@test_setup
class TestGlobalUInputs(unittest.TestCase):
    def setUp(self) -> None:
        cleanup()

    def test_iter(self):
        global_uinputs = GlobalUInputs(FrontendUInput)
        for uinput in global_uinputs:
            self.assertIsInstance(uinput, evdev.UInput)

    def test_write(self):
        """Test write and write failure

        implicitly tests get_uinput and UInput.can_emit
        """
        global_uinputs = GlobalUInputs(UInput)
        global_uinputs.prepare_all()

        ev_1 = InputEvent.key(KEY_A, 1)
        ev_2 = InputEvent.abs(ABS_X, 10)

        keyboard = global_uinputs.get_uinput("keyboard")

        global_uinputs.write(ev_1.event_tuple, "keyboard")
        self.assertEqual(keyboard.write_count, 1)

        with self.assertRaises(EventNotHandled):
            global_uinputs.write(ev_2.event_tuple, "keyboard")

        with self.assertRaises(UinputNotAvailable):
            global_uinputs.write(ev_1.event_tuple, "foo")

    def test_creates_frontend_uinputs(self):
        frontend_uinputs = GlobalUInputs(FrontendUInput)
        frontend_uinputs.prepare_all()
        uinput = frontend_uinputs.get_uinput("keyboard")
        self.assertIsInstance(uinput, FrontendUInput)

    def test_creates_backend_service_uinputs(self):
        frontend_uinputs = GlobalUInputs(UInput)
        frontend_uinputs.prepare_all()
        uinput = frontend_uinputs.get_uinput("keyboard")
        self.assertIsInstance(uinput, UInput)
