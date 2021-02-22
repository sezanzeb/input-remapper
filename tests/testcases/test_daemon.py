#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@sezanzeb.de>
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
import json

import evdev
from evdev.ecodes import EV_KEY, EV_ABS
from gi.repository import Gtk
from pydbus import SystemBus

from keymapper.state import custom_mapping, system_mapping
from keymapper.config import config
from keymapper.getdevices import get_devices
from keymapper.paths import get_preset_path, get_config_path
from keymapper.key import Key
from keymapper.mapping import Mapping
from keymapper.injection.injector import STARTING, RUNNING, STOPPED, UNKNOWN
from keymapper.daemon import Daemon, get_dbus_interface, BUS_NAME, \
    path_to_device_name

from tests.test import cleanup, uinput_write_history_pipe, new_event, \
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
        self.interface.stop_all()
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
            self.daemon.stop_all()
            self.daemon = None
        evdev.InputDevice.grab = self.grab

        subprocess.check_output = check_output
        type(SystemBus()).get = dbus_get

        cleanup()

    def test_path_to_device_name(self):
        self.assertEqual(path_to_device_name('/dev/input/event13'), 'device 1')
        self.assertEqual(path_to_device_name('/dev/input/event30'), 'gamepad')
        self.assertEqual(path_to_device_name('/dev/input/event1234'), None)
        self.assertEqual(path_to_device_name('asdf'), 'asdf')

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
        # remove the existing system mapping to force our own into it
        os.remove(get_config_path('xmodmap.json'))

        ev_1 = (EV_KEY, 9)
        ev_2 = (EV_ABS, 12)
        keycode_to_1 = 100
        keycode_to_2 = 101

        device = 'device 2'

        custom_mapping.change(Key(*ev_1, 1), 'a')
        custom_mapping.change(Key(*ev_2, -1), 'b')

        system_mapping.clear()
        # since this is in the same memory as the daemon, there is no need
        # to save it to disk
        system_mapping._set('a', keycode_to_1)
        system_mapping._set('b', keycode_to_2)

        preset = 'foo'

        custom_mapping.save(get_preset_path(device, preset))
        config.set_autoload_preset(device, preset)

        """injection 1"""

        # should forward the event unchanged
        pending_events[device] = [
            new_event(EV_KEY, 13, 1)
        ]

        self.daemon = Daemon()
        self.daemon.set_config_dir(get_config_path())

        self.assertFalse(uinput_write_history_pipe[0].poll())
        self.daemon.start_injecting(device, preset)

        self.assertEqual(self.daemon.get_state(device), STARTING)
        self.assertEqual(self.daemon.get_state('device 1'), UNKNOWN)

        event = uinput_write_history_pipe[0].recv()
        self.assertEqual(self.daemon.get_state(device), RUNNING)
        self.assertEqual(event.type, EV_KEY)
        self.assertEqual(event.code, 13)
        self.assertEqual(event.value, 1)

        self.daemon.stop_injecting(device)
        self.assertEqual(self.daemon.get_state(device), STOPPED)

        time.sleep(0.1)
        try:
            self.assertFalse(uinput_write_history_pipe[0].poll())
        except AssertionError:
            print('Unexpected', uinput_write_history_pipe[0].recv())
            # possibly a duplicate write!
            raise

        """injection 2"""

        # -1234 will be normalized to -1 by the injector
        pending_events[device] = [
            new_event(*ev_2, -1234)
        ]

        self.daemon.start_injecting(device, preset)

        time.sleep(0.1)
        self.assertTrue(uinput_write_history_pipe[0].poll())

        # the written key is a key-down event, not the original
        # event value of -1234
        event = uinput_write_history_pipe[0].recv()

        self.assertEqual(event.type, EV_KEY)
        self.assertEqual(event.code, keycode_to_2)
        self.assertEqual(event.value, 1)

    def test_refresh_devices_on_start(self):
        os.remove(get_config_path('xmodmap.json'))

        ev = (EV_KEY, 9)
        keycode_to = 100
        device = '9876 name'
        # this test only makes sense if this device is unknown yet
        self.assertIsNone(get_devices().get(device))
        custom_mapping.change(Key(*ev, 1), 'a')
        system_mapping.clear()
        system_mapping._set('a', keycode_to)

        # make the daemon load the file instead
        with open(get_config_path('xmodmap.json'), 'w') as file:
            json.dump(system_mapping._mapping, file, indent=4)
        system_mapping.clear()

        preset = 'foo'
        custom_mapping.save(get_preset_path(device, preset))
        config.set_autoload_preset(device, preset)
        pending_events[device] = [
            new_event(*ev, 1)
        ]
        self.daemon = Daemon()

        # make sure the devices are populated
        get_devices()
        fixtures[self.new_fixture] = {
            'capabilities': {evdev.ecodes.EV_KEY: [ev[1]]},
            'phys': '9876 phys',
            'info': evdev.device.DeviceInfo(4, 5, 6, 7),
            'name': device
        }

        self.daemon.set_config_dir(get_config_path())
        self.daemon.start_injecting(device, preset)

        # test if the injector called refresh_devices successfully
        self.assertIsNotNone(get_devices().get(device))

        time.sleep(0.1)
        self.assertTrue(uinput_write_history_pipe[0].poll())

        event = uinput_write_history_pipe[0].recv()
        self.assertEqual(event.t, (EV_KEY, keycode_to, 1))

        self.daemon.stop_injecting(device)
        self.assertEqual(self.daemon.get_state(device), STOPPED)

    def test_refresh_devices_for_unknown_paths(self):
        device = '9876 name'
        # this test only makes sense if this device is unknown yet
        self.assertIsNone(get_devices().get(device))

        self.daemon = Daemon()

        # make sure the devices are populated
        get_devices()

        self.daemon.refresh_devices()

        fixtures[self.new_fixture] = {
            'capabilities': {evdev.ecodes.EV_KEY: [evdev.ecodes.KEY_A]},
            'phys': '9876 phys',
            'info': evdev.device.DeviceInfo(4, 5, 6, 7),
            'name': device
        }

        self.daemon._autoload(self.new_fixture)

        # test if the injector called refresh_devices successfully
        self.assertIsNotNone(get_devices().get(device))

    def test_xmodmap_file(self):
        from_keycode = evdev.ecodes.KEY_A
        to_name = 'qux'
        to_keycode = 100
        event = (EV_KEY, from_keycode, 1)

        device = 'device 2'
        preset = 'foo'

        config_dir = os.path.join(tmp, 'foo')

        path = os.path.join(config_dir, 'presets', device, f'{preset}.json')

        custom_mapping.change(Key(event), to_name)
        custom_mapping.save(path)

        system_mapping.clear()

        pending_events[device] = [
            new_event(*event)
        ]

        # an existing config file is needed otherwise set_config_dir refuses
        # to use the directory
        config_path = os.path.join(config_dir, 'config.json')
        config.path = config_path
        config.save_config()

        xmodmap_path = os.path.join(config_dir, 'xmodmap.json')
        with open(xmodmap_path, 'w') as file:
            file.write(f'{{"{to_name}":{to_keycode}}}')

        self.daemon = Daemon()
        self.daemon.set_config_dir(config_dir)

        self.daemon.start_injecting(device, preset)

        time.sleep(0.1)
        self.assertTrue(uinput_write_history_pipe[0].poll())

        event = uinput_write_history_pipe[0].recv()
        self.assertEqual(event.type, EV_KEY)
        self.assertEqual(event.code, to_keycode)
        self.assertEqual(event.value, 1)

    def test_start_stop(self):
        device = 'device 1'
        preset = 'preset8'
        path = '/dev/input/event11'

        daemon = Daemon()
        self.daemon = daemon

        mapping = Mapping()
        mapping.change(Key(3, 2, 1), 'a')
        mapping.save(get_preset_path(device, preset))

        # the daemon needs set_config_dir first before doing anything
        daemon.start_injecting(device, preset)
        self.assertNotIn(device, daemon.autoload_history._autoload_history)
        self.assertNotIn(device, daemon.injectors)
        self.assertTrue(daemon.autoload_history.may_autoload(device, preset))

        # start
        config.save_config()
        daemon.set_config_dir(get_config_path())
        daemon.start_injecting(path, preset)
        # explicit start, not autoload, so the history stays empty
        self.assertNotIn(device, daemon.autoload_history._autoload_history)
        self.assertTrue(daemon.autoload_history.may_autoload(device, preset))
        # path got translated to the device name
        self.assertIn(device, daemon.injectors)

        # start again
        previous_injector = daemon.injectors[device]
        self.assertNotEqual(previous_injector.get_state(), STOPPED)
        daemon.start_injecting(device, preset)
        self.assertNotIn(device, daemon.autoload_history._autoload_history)
        self.assertTrue(daemon.autoload_history.may_autoload(device, preset))
        self.assertIn(device, daemon.injectors)
        self.assertEqual(previous_injector.get_state(), STOPPED)
        # a different injetor is now running
        self.assertNotEqual(previous_injector, daemon.injectors[device])
        self.assertNotEqual(daemon.injectors[device].get_state(), STOPPED)

        # trying to inject a non existing preset keeps the previous inejction
        # alive
        injector = daemon.injectors[device]
        daemon.start_injecting(device, 'qux')
        self.assertEqual(injector, daemon.injectors[device])
        self.assertNotEqual(daemon.injectors[device].get_state(), STOPPED)

        # trying to start injecting for an unknown device also just does
        # nothing
        daemon.start_injecting('quux', 'qux')
        self.assertNotEqual(daemon.injectors[device].get_state(), STOPPED)

        # after all that stuff autoload_history is still unharmed
        self.assertNotIn(device, daemon.autoload_history._autoload_history)
        self.assertTrue(daemon.autoload_history.may_autoload(device, preset))

        # stop
        daemon.stop_injecting(device)
        self.assertNotIn(device, daemon.autoload_history._autoload_history)
        self.assertEqual(daemon.injectors[device].get_state(), STOPPED)
        self.assertTrue(daemon.autoload_history.may_autoload(device, preset))

    def test_autoload(self):
        device = 'device 1'
        preset = 'preset7'
        path = '/dev/input/event11'

        daemon = Daemon()
        self.daemon = daemon
        self.daemon.set_config_dir(get_config_path())

        mapping = Mapping()
        mapping.change(Key(3, 2, 1), 'a')
        mapping.save(get_preset_path(device, preset))

        # no autoloading is configured yet
        self.daemon._autoload(device)
        self.daemon._autoload(path)
        self.assertNotIn(device, daemon.autoload_history._autoload_history)
        self.assertTrue(daemon.autoload_history.may_autoload(device, preset))

        config.set_autoload_preset(device, preset)
        config.save_config()
        self.daemon.set_config_dir(get_config_path())
        len_before = len(self.daemon.autoload_history._autoload_history)
        self.daemon._autoload(path)
        len_after = len(self.daemon.autoload_history._autoload_history)
        self.assertEqual(daemon.autoload_history._autoload_history[device][1], preset)
        self.assertFalse(daemon.autoload_history.may_autoload(device, preset))
        injector = daemon.injectors[device]
        self.assertEqual(len_before + 1, len_after)

        # calling duplicate _autoload does nothing
        self.daemon._autoload(path)
        self.assertEqual(daemon.autoload_history._autoload_history[device][1], preset)
        self.assertEqual(injector, daemon.injectors[device])
        self.assertFalse(daemon.autoload_history.may_autoload(device, preset))

        # explicit start_injecting clears the autoload history
        self.daemon.start_injecting(device, preset)
        self.assertTrue(daemon.autoload_history.may_autoload(device, preset))

        # calling autoload for (yet) unknown devices does nothing
        len_before = len(self.daemon.autoload_history._autoload_history)
        self.daemon._autoload('/dev/input/qux')
        len_after = len(self.daemon.autoload_history._autoload_history)
        self.assertEqual(len_before, len_after)

        # autoloading key-mapper devices does nothing
        len_before = len(self.daemon.autoload_history._autoload_history)
        self.daemon.autoload_single('/dev/input/event40')
        len_after = len(self.daemon.autoload_history._autoload_history)
        self.assertEqual(len_before, len_after)


if __name__ == "__main__":
    unittest.main()
