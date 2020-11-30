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
import sys
import multiprocessing
import unittest
import time
from unittest.mock import patch
from importlib.util import spec_from_loader, module_from_spec
from importlib.machinery import SourceFileLoader

import dbus
import evdev
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from keymapper.state import custom_mapping, system_mapping, \
    clear_system_mapping
from keymapper.config import config
from keymapper.daemon import Daemon, get_dbus_interface

from test import uinput_write_history_pipe, Event, pending_events


def gtk_iteration():
    """Iterate while events are pending."""
    while Gtk.events_pending():
        Gtk.main_iteration()


class TestDBusDaemon(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.process = multiprocessing.Process(
            target=os.system,
            args=('key-mapper-service',)
        )
        cls.process.start()
        time.sleep(0.5)
        cls.interface = get_dbus_interface()

    @classmethod
    def tearDownClass(cls):
        cls.interface.stop()
        time.sleep(0.1)
        cls.process.terminate()
        time.sleep(0.1)
        os.system('pkill -f key-mapper-service')
        time.sleep(0.1)

    def test_can_connect(self):
        self.assertIsInstance(self.interface, dbus.Interface)


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

    def test_daemon(self):
        keycode_from = 9
        keycode_to = 100

        custom_mapping.change(keycode_from, 'a')
        clear_system_mapping()
        system_mapping['a'] = keycode_to

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
