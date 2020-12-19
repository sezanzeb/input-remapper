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
from evdev.ecodes import EV_KEY, EV_ABS
from gi.repository import Gtk

from keymapper.state import custom_mapping, system_mapping
from keymapper.config import config
from keymapper.daemon import Daemon, get_dbus_interface, BUS_NAME

from tests.test import uinput_write_history_pipe, InputEvent, pending_events


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
        ev_1 = (EV_KEY, 9)
        ev_2 = (EV_ABS, 12)
        keycode_to_1 = 100
        keycode_to_2 = 101

        custom_mapping.change((*ev_1, 1), 'a')
        custom_mapping.change((*ev_2, -1), 'b')

        system_mapping.clear()
        system_mapping._set('a', keycode_to_1)
        system_mapping._set('b', keycode_to_2)

        preset = 'foo'

        custom_mapping.save('device 2', preset)
        config.set_autoload_preset('device 2', preset)

        """injection 1"""

        # should forward the event unchanged
        pending_events['device 2'] = [
            InputEvent(EV_KEY, 13, 1)
        ]

        self.daemon = Daemon()
        self.daemon.autoload()

        self.assertTrue(self.daemon.is_injecting('device 2'))
        self.assertFalse(self.daemon.is_injecting('device 1'))

        event = uinput_write_history_pipe[0].recv()
        self.assertEqual(event.type, EV_KEY)
        self.assertEqual(event.code, 13)
        self.assertEqual(event.value, 1)

        self.daemon.stop_injecting('device 2')
        self.assertFalse(self.daemon.is_injecting('device 2'))

        """injection 2"""

        # -1234 will be normalized to -1 by the injector
        pending_events['device 2'] = [
            InputEvent(*ev_2, -1234)
        ]

        time.sleep(0.2)
        self.assertFalse(uinput_write_history_pipe[0].poll())

        self.daemon.start_injecting('device 2', preset)

        # the written key is a key-down event, not the original
        # event value of -5678
        event = uinput_write_history_pipe[0].recv()
        self.assertEqual(event.type, EV_KEY)
        self.assertEqual(event.code, keycode_to_2)
        self.assertEqual(event.value, 1)


if __name__ == "__main__":
    unittest.main()
