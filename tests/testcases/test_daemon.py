#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@hip70890b.de>
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
import subprocess

import evdev
from evdev.ecodes import EV_KEY, EV_ABS
from gi.repository import Gtk
from pydbus import SystemBus

from keymapper.state import custom_mapping, system_mapping
from keymapper.config import config
from keymapper.getdevices import get_devices
from keymapper.paths import get_preset_path
from keymapper.key import Key
from keymapper.daemon import Daemon, get_dbus_interface, BUS_NAME

from tests.test import cleanup, uinput_write_history_pipe, InputEvent, \
    pending_events, is_service_running, fixtures, tmp


def gtk_iteration():
    """Iterate while events are pending."""
    while Gtk.events_pending():
        Gtk.main_iteration()


class TestDBusDaemon(unittest.TestCase):
    def setUp(self):
        self.process = multiprocessing.Process(
            target=os.system,
            args=('key-mapper-service -d',)
        )
        self.process.start()
        time.sleep(0.5)
        self.interface = get_dbus_interface()

    def tearDown(self):
        self.interface.stop()
        os.system('pkill -f key-mapper-service')

        for _ in range(10):
            time.sleep(0.1)
            if not is_service_running():
                break

        self.assertFalse(is_service_running())

    def test_can_connect(self):
        # it's a remote dbus object
        self.assertEqual(self.interface._bus_name, BUS_NAME)
        self.assertFalse(isinstance(self.interface, Daemon))
        self.assertEqual(self.interface.hello('foo'), 'foo')


check_output = subprocess.check_output
dbus_get = type(SystemBus()).get


class TestDaemon(unittest.TestCase):
    new_fixture = '/dev/input/event9876'

    def setUp(self):
        self.grab = evdev.InputDevice.grab
        self.daemon = None

    def tearDown(self):
        # avoid race conditions with other tests, daemon may run processes
        if self.daemon is not None:
            self.daemon.stop()
            self.daemon = None
        evdev.InputDevice.grab = self.grab

        subprocess.check_output = check_output
        type(SystemBus()).get = dbus_get

        cleanup()

    def test_get_dbus_interface(self):
        # no daemon runs, should return an instance of the object instead
        self.assertFalse(is_service_running())
        self.assertIsInstance(get_dbus_interface(), Daemon)
        self.assertIsNone(get_dbus_interface(False))

        subprocess.check_output = lambda *args: None
        self.assertTrue(is_service_running())
        # now it actually tries to use the dbus, but it fails
        # because none exists, so it returns an instance again
        self.assertIsInstance(get_dbus_interface(), Daemon)
        self.assertIsNone(get_dbus_interface(False))

        class FakeConnection:
            pass

        type(SystemBus()).get = lambda *args: FakeConnection()
        self.assertIsInstance(get_dbus_interface(), FakeConnection)
        self.assertIsInstance(get_dbus_interface(False), FakeConnection)

    def test_daemon(self):
        ev_1 = (EV_KEY, 9)
        ev_2 = (EV_ABS, 12)
        keycode_to_1 = 100
        keycode_to_2 = 101

        device = 'device 2'

        custom_mapping.change(Key(*ev_1, 1), 'a')
        custom_mapping.change(Key(*ev_2, -1), 'b')

        system_mapping.clear()
        system_mapping._set('a', keycode_to_1)
        system_mapping._set('b', keycode_to_2)

        preset = 'foo'

        custom_mapping.save(get_preset_path(device, preset))
        config.set_autoload_preset(device, preset)

        """injection 1"""

        # should forward the event unchanged
        pending_events[device] = [
            InputEvent(EV_KEY, 13, 1)
        ]

        self.daemon = Daemon()
        preset_path = get_preset_path(device, preset)

        self.assertFalse(uinput_write_history_pipe[0].poll())
        self.daemon.start_injecting(device, preset_path)

        self.assertTrue(self.daemon.is_injecting(device))
        self.assertFalse(self.daemon.is_injecting('device 1'))

        event = uinput_write_history_pipe[0].recv()
        self.assertEqual(event.type, EV_KEY)
        self.assertEqual(event.code, 13)
        self.assertEqual(event.value, 1)

        self.daemon.stop_injecting(device)
        self.assertFalse(self.daemon.is_injecting(device))

        time.sleep(0.2)
        try:
            self.assertFalse(uinput_write_history_pipe[0].poll())
        except AssertionError:
            print(uinput_write_history_pipe[0].recv())
            raise

        """injection 2"""

        # -1234 will be normalized to -1 by the injector
        pending_events[device] = [
            InputEvent(*ev_2, -1234)
        ]

        path = get_preset_path(device, preset)
        self.daemon.start_injecting(device, path)

        # the written key is a key-down event, not the original
        # event value of -5678
        event = uinput_write_history_pipe[0].recv()
        self.assertEqual(event.type, EV_KEY)
        self.assertEqual(event.code, keycode_to_2)
        self.assertEqual(event.value, 1)

    def test_refresh_devices_on_start(self):
        ev = (EV_KEY, 9)
        keycode_to = 100
        device = '9876 name'
        # this test only makes sense if this device is unknown yet
        self.assertIsNone(get_devices().get(device))
        custom_mapping.change(Key(*ev, 1), 'a')
        system_mapping.clear()
        system_mapping._set('a', keycode_to)
        preset = 'foo'
        custom_mapping.save(get_preset_path(device, preset))
        config.set_autoload_preset(device, preset)
        pending_events[device] = [
            InputEvent(*ev, 1)
        ]
        self.daemon = Daemon()
        preset_path = get_preset_path(device, preset)

        # make sure the devices are populated
        get_devices()
        fixtures[self.new_fixture] = {
            'capabilities': {evdev.ecodes.EV_KEY: [ev[1]]},
            'phys': '9876 phys',
            'info': 'abcd',
            'name': device
        }

        self.daemon.start_injecting(device, preset_path)

        # test if the injector called refresh_devices successfully
        self.assertIsNotNone(get_devices().get(device))

        event = uinput_write_history_pipe[0].recv()
        self.assertEqual(event.type, EV_KEY)
        self.assertEqual(event.code, keycode_to)
        self.assertEqual(event.value, 1)

        self.daemon.stop_injecting(device)
        self.assertFalse(self.daemon.is_injecting(device))

    def test_xmodmap_file(self):
        from_keycode = evdev.ecodes.KEY_A
        to_name = 'qux'
        to_keycode = 100
        event = (EV_KEY, from_keycode, 1)

        device = 'device 2'
        preset = 'foo'

        path = get_preset_path(device, preset)

        custom_mapping.change(Key(event), to_name)
        custom_mapping.save(path)

        system_mapping.clear()

        config.set_autoload_preset(device, preset)

        pending_events[device] = [
            InputEvent(*event)
        ]

        xmodmap_path = os.path.join(tmp, 'foobar.json')
        with open(xmodmap_path, 'w') as file:
            file.write(f'{{"{to_name}":{to_keycode}}}')

        self.daemon = Daemon()
        self.daemon.start_injecting(device, path, xmodmap_path)

        event = uinput_write_history_pipe[0].recv()
        self.assertEqual(event.type, EV_KEY)
        self.assertEqual(event.code, to_keycode)
        self.assertEqual(event.value, 1)


if __name__ == "__main__":
    unittest.main()
