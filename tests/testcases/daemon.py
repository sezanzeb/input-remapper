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
        custom_mapping.change(9, 'a')
        # one mapping that is unknown in the system_mapping on purpose
        custom_mapping.change(10, 'b')

        system_mapping.empty()
        a_code = 100
        system_mapping.change(a_code, 'a')

        custom_mapping.save('device 2', 'foo')
        config.set_autoload_preset('device 2', 'foo')

        pending_events['device 2'] = [
            Event(evdev.events.EV_KEY, 1, 0),
            Event(evdev.events.EV_KEY, 1, 1),
            # ignored because unknown to the system
            Event(evdev.events.EV_KEY, 2, 0),
            Event(evdev.events.EV_KEY, 2, 1),
            # just pass those over without modifying
            Event(3124, 3564, 6542),
        ]

        self.daemon = Daemon()

        time.sleep(0.5)

        write_history = []
        pipe = uinput_write_history_pipe[0]
        while pipe.poll():
            write_history.append(pipe.recv())

        self.assertEqual(write_history[0].type, evdev.events.EV_KEY)
        self.assertEqual(write_history[0].code, a_code - 8)
        self.assertEqual(write_history[0].value, 0)

        self.assertEqual(write_history[1].type, evdev.events.EV_KEY)
        self.assertEqual(write_history[1].code, a_code - 8)
        self.assertEqual(write_history[1].value, 1)

        self.assertEqual(write_history[2].type, 3124)
        self.assertEqual(write_history[2].code, 3564)
        self.assertEqual(write_history[2].value, 6542)


if __name__ == "__main__":
    unittest.main()
