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


import os
import multiprocessing
import unittest
import time

import evdev
from evdev.ecodes import EV_KEY
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from keymapper.state import custom_mapping, system_mapping
from keymapper.config import config
from keymapper.daemon import Daemon, get_dbus_interface, BUS_NAME

from tests.test import uinput_write_history_pipe, Event, pending_events


def gtk_iteration():
    """Iterate while events are pending."""
    while Gtk.events_pending():
        Gtk.main_iteration()


class TestDBusDaemon(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.process = multiprocessing.Process(
            target=os.system,
            args=('key-mapper-service -d',)
        )
        cls.process.start()
        time.sleep(0.5)
        cls.interface = get_dbus_interface()

    @classmethod
    def tearDownClass(cls):
        cls.interface.stop(True)

    def test_can_connect(self):
        # it's a remote dbus object
        self.assertEqual(self.interface._bus_name, BUS_NAME)
        self.assertFalse(isinstance(self.interface, Daemon))
        self.assertEqual(self.interface.hello('foo'), 'foo')


class TestDaemon(unittest.TestCase):
    def setUp(self):
        self.grab = evdev.InputDevice.grab
        self.daemon = None

    def tearDown(self):
        # avoid race conditions with other tests, daemon may run processes
        if self.daemon is not None:
            self.daemon.stop()
            self.daemon = None
        evdev.InputDevice.grab = self.grab
        config.clear_config()
        system_mapping.populate()

    def test_daemon(self):
        keycode_from_1 = 9
        keycode_to_1 = 100
        keycode_from_2 = 12
        keycode_to_2 = 100

        custom_mapping.change((EV_KEY, keycode_from_1), 'a')
        custom_mapping.change((EV_KEY, keycode_from_2), 'b')
        system_mapping.clear()
        system_mapping._set('a', keycode_to_1)
        system_mapping._set('b', keycode_to_2)

        preset = 'foo'

        custom_mapping.save('device 2', preset)
        config.set_autoload_preset('device 2', preset)

        pending_events['device 2'] = [
            Event(evdev.events.EV_KEY, keycode_from_1, 0),
        ]

        self.daemon = Daemon()
        # starts mapping right after creation

        self.assertTrue(self.daemon.is_injecting('device 2'))
        self.assertFalse(self.daemon.is_injecting('device 1'))

        event = uinput_write_history_pipe[0].recv()
        self.assertEqual(event.type, evdev.events.EV_KEY)
        self.assertEqual(event.code, keycode_to_1)
        self.assertEqual(event.value, 0)

        self.daemon.stop_injecting('device 2')
        self.assertFalse(self.daemon.is_injecting('device 2'))

        pending_events['device 2'] = [
            Event(evdev.events.EV_KEY, keycode_from_2, 1),
            Event(evdev.events.EV_KEY, keycode_from_2, 0),
        ]

        time.sleep(0.2)
        self.assertFalse(uinput_write_history_pipe[0].poll())

        self.daemon.start_injecting('device 2', preset)

        event = uinput_write_history_pipe[0].recv()
        self.assertEqual(event.type, evdev.events.EV_KEY)
        self.assertEqual(event.code, keycode_to_2)
        self.assertEqual(event.value, 1)

        event = uinput_write_history_pipe[0].recv()
        self.assertEqual(event.type, evdev.events.EV_KEY)
        self.assertEqual(event.code, keycode_to_2)
        self.assertEqual(event.value, 0)


if __name__ == "__main__":
    unittest.main()
