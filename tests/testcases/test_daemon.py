#!/usr/bin/python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@sezanzeb.de>
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


import os
import multiprocessing
import unittest
import time
import subprocess
import json

import evdev
from evdev.ecodes import EV_KEY, EV_ABS, KEY_B, KEY_A
from gi.repository import Gtk
from pydbus import SystemBus

from inputremapper.system_mapping import system_mapping
from inputremapper.gui.custom_mapping import custom_mapping
from inputremapper.config import config
from inputremapper.groups import groups
from inputremapper.paths import get_config_path, mkdir, get_preset_path
from inputremapper.key import Key
from inputremapper.mapping import Mapping
from inputremapper.injection.injector import STARTING, RUNNING, STOPPED, UNKNOWN
from inputremapper.daemon import Daemon, BUS_NAME

from tests.test import (
    cleanup,
    uinput_write_history_pipe,
    new_event,
    push_events,
    is_service_running,
    fixtures,
    tmp,
)


def gtk_iteration():
    """Iterate while events are pending."""
    while Gtk.events_pending():
        Gtk.main_iteration()


class TestDBusDaemon(unittest.TestCase):
    def setUp(self):
        self.process = multiprocessing.Process(
            target=os.system, args=("input-remapper-service -d",)
        )
        self.process.start()
        time.sleep(0.5)

        # should not use pkexec, but rather connect to the previously
        # spawned process
        self.interface = Daemon.connect()

    def tearDown(self):
        self.interface.stop_all()
        os.system("pkill -f input-remapper-service")

        for _ in range(10):
            time.sleep(0.1)
            if not is_service_running():
                break

        self.assertFalse(is_service_running())

    def test_can_connect(self):
        # it's a remote dbus object
        self.assertEqual(self.interface._bus_name, BUS_NAME)
        self.assertFalse(isinstance(self.interface, Daemon))
        self.assertEqual(self.interface.hello("foo"), "foo")


check_output = subprocess.check_output
os_system = os.system
dbus_get = type(SystemBus()).get


class TestDaemon(unittest.TestCase):
    new_fixture_path = "/dev/input/event9876"

    def setUp(self):
        self.grab = evdev.InputDevice.grab
        self.daemon = None
        mkdir(get_config_path())
        config.save_config()

    def tearDown(self):
        # avoid race conditions with other tests, daemon may run processes
        if self.daemon is not None:
            self.daemon.stop_all()
            self.daemon = None
        evdev.InputDevice.grab = self.grab

        subprocess.check_output = check_output
        os.system = os_system
        type(SystemBus()).get = dbus_get

        cleanup()

    def test_connect(self):
        os_system_history = []
        os.system = os_system_history.append

        self.assertFalse(is_service_running())

        # no daemon runs, should try to run it via pkexec instead.
        # It fails due to the patch on os.system and therefore exits the process
        self.assertRaises(SystemExit, Daemon.connect)
        self.assertEqual(len(os_system_history), 1)
        self.assertIsNone(Daemon.connect(False))

        # make the connect command work this time by acting like a connection is
        # available:

        set_config_dir_callcount = 0

        class FakeConnection:
            def set_config_dir(self, *args, **kwargs):
                nonlocal set_config_dir_callcount
                set_config_dir_callcount += 1

        type(SystemBus()).get = lambda *args, **kwargs: FakeConnection()
        self.assertIsInstance(Daemon.connect(), FakeConnection)
        self.assertEqual(set_config_dir_callcount, 1)

        self.assertIsInstance(Daemon.connect(False), FakeConnection)
        self.assertEqual(set_config_dir_callcount, 2)

    def test_daemon(self):
        # remove the existing system mapping to force our own into it
        if os.path.exists(get_config_path("xmodmap.json")):
            os.remove(get_config_path("xmodmap.json"))

        ev_1 = (EV_KEY, 9)
        ev_2 = (EV_ABS, 12)

        group = groups.find(name="Bar Device")

        # unrelated group that shouldn't be affected at all
        group2 = groups.find(name="gamepad")

        custom_mapping.change(Key(*ev_1, 1), "a")
        custom_mapping.change(Key(*ev_2, -1), "b")

        preset = "foo"

        custom_mapping.save(group.get_preset_path(preset))
        config.set_autoload_preset(group.key, preset)

        """injection 1"""

        # should forward the event unchanged
        push_events(group.key, [new_event(EV_KEY, 13, 1)])

        self.daemon = Daemon()

        self.assertFalse(uinput_write_history_pipe[0].poll())
        self.daemon.start_injecting(group.key, preset)

        self.assertEqual(self.daemon.get_state(group.key), STARTING)
        self.assertEqual(self.daemon.get_state(group2.key), UNKNOWN)

        event = uinput_write_history_pipe[0].recv()
        self.assertEqual(self.daemon.get_state(group.key), RUNNING)
        self.assertEqual(event.type, EV_KEY)
        self.assertEqual(event.code, 13)
        self.assertEqual(event.value, 1)

        self.daemon.stop_injecting(group.key)
        self.assertEqual(self.daemon.get_state(group.key), STOPPED)

        time.sleep(0.1)
        try:
            self.assertFalse(uinput_write_history_pipe[0].poll())
        except AssertionError:
            print("Unexpected", uinput_write_history_pipe[0].recv())
            # possibly a duplicate write!
            raise

        """injection 2"""

        # -1234 will be classified as -1 by the injector
        push_events(group.key, [new_event(*ev_2, -1234)])

        self.daemon.start_injecting(group.key, preset)

        time.sleep(0.1)
        self.assertTrue(uinput_write_history_pipe[0].poll())

        # the written key is a key-down event, not the original
        # event value of -1234
        event = uinput_write_history_pipe[0].recv()

        self.assertEqual(event.type, EV_KEY)
        self.assertEqual(event.code, KEY_B)
        self.assertEqual(event.value, 1)

    def test_config_dir(self):
        config.set("foo", "bar")
        self.assertEqual(config.get("foo"), "bar")

        # freshly loads the config and therefore removes the previosly added key.
        # This is important so that if the service is started via sudo or pkexec
        # it knows where to look for configuration files.
        self.daemon = Daemon()
        self.assertEqual(self.daemon.config_dir, get_config_path())
        self.assertIsNone(config.get("foo"))

    def test_refresh_on_start(self):
        if os.path.exists(get_config_path("xmodmap.json")):
            os.remove(get_config_path("xmodmap.json"))

        ev = (EV_KEY, 9)
        group_name = "9876 name"

        # expected key of the group
        group_key = group_name

        group = groups.find(name=group_name)
        # this test only makes sense if this device is unknown yet
        self.assertIsNone(group)
        custom_mapping.change(Key(*ev, 1), "a")
        system_mapping.clear()
        system_mapping._set("a", KEY_A)

        # make the daemon load the file instead
        with open(get_config_path("xmodmap.json"), "w") as file:
            json.dump(system_mapping._mapping, file, indent=4)
        system_mapping.clear()

        preset = "foo"
        custom_mapping.save(get_preset_path(group_name, preset))
        config.set_autoload_preset(group_key, preset)
        push_events(group_key, [new_event(*ev, 1)])
        self.daemon = Daemon()

        # make sure the devices are populated
        groups.refresh()

        # the daemon is supposed to find this device by calling refresh
        fixtures[self.new_fixture_path] = {
            "capabilities": {evdev.ecodes.EV_KEY: [ev[1]]},
            "phys": "9876 phys",
            "info": evdev.device.DeviceInfo(4, 5, 6, 7),
            "name": group_name,
        }

        self.daemon.start_injecting(group_key, preset)

        # test if the injector called groups.refresh successfully
        group = groups.find(key=group_key)
        self.assertEqual(group.name, group_name)
        self.assertEqual(group.key, group_key)

        time.sleep(0.1)
        self.assertTrue(uinput_write_history_pipe[0].poll())

        event = uinput_write_history_pipe[0].recv()
        self.assertEqual(event.t, (EV_KEY, KEY_A, 1))

        self.daemon.stop_injecting(group_key)
        self.assertEqual(self.daemon.get_state(group_key), STOPPED)

    def test_refresh_for_unknown_key(self):
        device = "9876 name"
        # this test only makes sense if this device is unknown yet
        self.assertIsNone(groups.find(name=device))

        self.daemon = Daemon()

        # make sure the devices are populated
        groups.refresh()

        self.daemon.refresh()

        fixtures[self.new_fixture_path] = {
            "capabilities": {evdev.ecodes.EV_KEY: [evdev.ecodes.KEY_A]},
            "phys": "9876 phys",
            "info": evdev.device.DeviceInfo(4, 5, 6, 7),
            "name": device,
        }

        self.daemon._autoload("25v7j9q4vtj")
        # this is unknown, so the daemon will scan the devices again

        # test if the injector called groups.refresh successfully
        self.assertIsNotNone(groups.find(name=device))

    def test_xmodmap_file(self):
        from_keycode = evdev.ecodes.KEY_A
        to_name = "qux"
        to_keycode = 100
        event = (EV_KEY, from_keycode, 1)

        name = "Bar Device"
        preset = "foo"
        group = groups.find(name=name)

        config_dir = os.path.join(tmp, "foo")

        path = os.path.join(config_dir, "presets", name, f"{preset}.json")

        custom_mapping.change(Key(event), to_name)
        custom_mapping.save(path)

        system_mapping.clear()

        push_events(group.key, [new_event(*event)])

        # an existing config file is needed otherwise set_config_dir refuses
        # to use the directory
        config_path = os.path.join(config_dir, "config.json")
        config.path = config_path
        config.save_config()

        xmodmap_path = os.path.join(config_dir, "xmodmap.json")
        with open(xmodmap_path, "w") as file:
            file.write(f'{{"{to_name}":{to_keycode}}}')

        self.daemon = Daemon()
        self.daemon.set_config_dir(config_dir)

        self.daemon.start_injecting(group.key, preset)

        time.sleep(0.1)
        self.assertTrue(uinput_write_history_pipe[0].poll())

        event = uinput_write_history_pipe[0].recv()
        self.assertEqual(event.type, EV_KEY)
        self.assertEqual(event.code, to_keycode)
        self.assertEqual(event.value, 1)

    def test_start_stop(self):
        group = groups.find(key="Foo Device 2")
        preset = "preset8"

        daemon = Daemon()
        self.daemon = daemon

        mapping = Mapping()
        mapping.change(Key(3, 2, 1), "a")
        mapping.save(group.get_preset_path(preset))

        # start
        daemon.start_injecting(group.key, preset)
        # explicit start, not autoload, so the history stays empty
        self.assertNotIn(group.key, daemon.autoload_history._autoload_history)
        self.assertTrue(daemon.autoload_history.may_autoload(group.key, preset))
        # path got translated to the device name
        self.assertIn(group.key, daemon.injectors)

        # start again
        previous_injector = daemon.injectors[group.key]
        self.assertNotEqual(previous_injector.get_state(), STOPPED)
        daemon.start_injecting(group.key, preset)
        self.assertNotIn(group.key, daemon.autoload_history._autoload_history)
        self.assertTrue(daemon.autoload_history.may_autoload(group.key, preset))
        self.assertIn(group.key, daemon.injectors)
        self.assertEqual(previous_injector.get_state(), STOPPED)
        # a different injetor is now running
        self.assertNotEqual(previous_injector, daemon.injectors[group.key])
        self.assertNotEqual(daemon.injectors[group.key].get_state(), STOPPED)

        # trying to inject a non existing preset keeps the previous inejction
        # alive
        injector = daemon.injectors[group.key]
        daemon.start_injecting(group.key, "qux")
        self.assertEqual(injector, daemon.injectors[group.key])
        self.assertNotEqual(daemon.injectors[group.key].get_state(), STOPPED)

        # trying to start injecting for an unknown device also just does
        # nothing
        daemon.start_injecting("quux", "qux")
        self.assertNotEqual(daemon.injectors[group.key].get_state(), STOPPED)

        # after all that stuff autoload_history is still unharmed
        self.assertNotIn(group.key, daemon.autoload_history._autoload_history)
        self.assertTrue(daemon.autoload_history.may_autoload(group.key, preset))

        # stop
        daemon.stop_injecting(group.key)
        self.assertNotIn(group.key, daemon.autoload_history._autoload_history)
        self.assertEqual(daemon.injectors[group.key].get_state(), STOPPED)
        self.assertTrue(daemon.autoload_history.may_autoload(group.key, preset))

    def test_autoload(self):
        preset = "preset7"
        group = groups.find(key="Foo Device 2")

        daemon = Daemon()
        self.daemon = daemon

        mapping = Mapping()
        mapping.change(Key(3, 2, 1), "a")
        mapping.save(group.get_preset_path(preset))

        # no autoloading is configured yet
        self.daemon._autoload(group.key)
        self.assertNotIn(group.key, daemon.autoload_history._autoload_history)
        self.assertTrue(daemon.autoload_history.may_autoload(group.key, preset))

        config.set_autoload_preset(group.key, preset)
        config.save_config()
        len_before = len(self.daemon.autoload_history._autoload_history)
        # now autoloading is configured, so it will autoload
        self.daemon._autoload(group.key)
        len_after = len(self.daemon.autoload_history._autoload_history)
        self.assertEqual(
            daemon.autoload_history._autoload_history[group.key][1], preset
        )
        self.assertFalse(daemon.autoload_history.may_autoload(group.key, preset))
        injector = daemon.injectors[group.key]
        self.assertEqual(len_before + 1, len_after)

        # calling duplicate _autoload does nothing
        self.daemon._autoload(group.key)
        self.assertEqual(
            daemon.autoload_history._autoload_history[group.key][1], preset
        )
        self.assertEqual(injector, daemon.injectors[group.key])
        self.assertFalse(daemon.autoload_history.may_autoload(group.key, preset))

        # explicit start_injecting clears the autoload history
        self.daemon.start_injecting(group.key, preset)
        self.assertTrue(daemon.autoload_history.may_autoload(group.key, preset))

        # calling autoload for (yet) unknown devices does nothing
        len_before = len(self.daemon.autoload_history._autoload_history)
        self.daemon._autoload("unknown-key-1234")
        len_after = len(self.daemon.autoload_history._autoload_history)
        self.assertEqual(len_before, len_after)

        # autoloading input-remapper devices does nothing
        len_before = len(self.daemon.autoload_history._autoload_history)
        self.daemon.autoload_single("Bar Device")
        len_after = len(self.daemon.autoload_history._autoload_history)
        self.assertEqual(len_before, len_after)

    def test_autoload_2(self):
        self.daemon = Daemon()
        history = self.daemon.autoload_history._autoload_history

        # existing device
        preset = "preset7"
        group = groups.find(key="Foo Device 2")
        mapping = Mapping()
        mapping.change(Key(3, 2, 1), "a")
        mapping.save(group.get_preset_path(preset))
        config.set_autoload_preset(group.key, preset)

        # ignored, won't cause problems:
        config.set_autoload_preset("non-existant-key", "foo")

        self.daemon.autoload()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[group.key][1], preset)

    def test_autoload_3(self):
        # based on a bug
        preset = "preset7"
        group = groups.find(key="Foo Device 2")

        mapping = Mapping()
        mapping.change(Key(3, 2, 1), "a")
        mapping.save(group.get_preset_path(preset))

        config.set_autoload_preset(group.key, preset)
        config.save_config()

        self.daemon = Daemon()
        groups.set_groups([])  # caused the bug
        self.assertIsNone(groups.find(key="Foo Device 2"))
        self.daemon.autoload()

        # it should try to refresh the groups because all the
        # group_keys are unknown at the moment
        history = self.daemon.autoload_history._autoload_history
        self.assertEqual(history[group.key][1], preset)
        self.assertEqual(self.daemon.get_state(group.key), STARTING)
        self.assertIsNotNone(groups.find(key="Foo Device 2"))


if __name__ == "__main__":
    unittest.main()
