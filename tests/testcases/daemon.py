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
import time

import evdev

from keymapper.state import custom_mapping, system_mapping
from keymapper.config import config
from keymapper.daemon import Daemon

from test import uinput_write_history_pipe, Event, pending_events


class TestDaemon(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.grab = evdev.InputDevice.grab
        cls.daemon = None

    def tearDown(self):
        # avoid race conditions with other tests, daemon may run processes
        if self.daemon is not None:
            self.daemon.stop()
            self.daemon = None
        evdev.InputDevice.grab = self.grab

    def test_daemon(self):
        keycode_from = 9
        keycode_to = 100

        custom_mapping.change(keycode_from, 'a')
        system_mapping.empty()
        system_mapping.change(keycode_to, 'a')

        custom_mapping.save('device 2', 'foo')
        config.set_autoload_preset('device 2', 'foo')

        pending_events['device 2'] = [
            Event(evdev.events.EV_KEY, keycode_from - 8, 0)
        ]

        self.daemon = Daemon()

        event = uinput_write_history_pipe[0].recv()
        self.assertEqual(event.type, evdev.events.EV_KEY)
        self.assertEqual(event.code, keycode_to - 8)
        self.assertEqual(event.value, 0)


if __name__ == "__main__":
    unittest.main()
