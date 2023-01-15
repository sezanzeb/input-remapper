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

from inputremapper.input_event import InputEvent
from tests.test import is_service_running
from tests.lib.logger import logger
from tests.lib.cleanup import cleanup
from tests.lib.fixtures import new_event, get_combination_config, Fixture
from tests.lib.pipes import push_events, uinput_write_history_pipe
from tests.lib.tmp import tmp
from tests.lib.fixtures import fixtures

import os
import unittest
import time
import subprocess
import json

import evdev
from evdev.ecodes import EV_KEY, KEY_B, KEY_A, ABS_X, BTN_A, BTN_B
from pydbus import SystemBus

from inputremapper.configs.system_mapping import system_mapping
from inputremapper.configs.mapping import Mapping
from inputremapper.configs.global_config import global_config
from inputremapper.groups import groups
from inputremapper.configs.paths import get_config_path, mkdir, get_preset_path
from inputremapper.configs.input_config import InputCombination, InputConfig
from inputremapper.configs.preset import Preset
from inputremapper.injection.injector import InjectorState
from inputremapper.daemon import Daemon
from inputremapper.injection.global_uinputs import global_uinputs


check_output = subprocess.check_output
os_system = os.system
dbus_get = type(SystemBus()).get


class TestDaemon(unittest.TestCase):
    new_fixture_path = "/dev/input/event9876"

    def setUp(self):
        self.grab = evdev.InputDevice.grab
        self.daemon = None
        mkdir(get_config_path())
        global_config._save_config()

        # the daemon should be able to create them on demand:
        global_uinputs.devices = {}
        global_uinputs.is_service = True

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

        preset_name = "foo"

        group = groups.find(name="gamepad")

        # unrelated group that shouldn't be affected at all
        group2 = groups.find(name="Bar Device")

        preset = Preset(group.get_preset_path(preset_name))
        preset.add(
            Mapping.from_combination(
                input_combination=InputCombination([InputConfig.key(BTN_A)]),
                target_uinput="keyboard",
                output_symbol="a",
            )
        )
        preset.add(
            Mapping.from_combination(
                input_combination=InputCombination([InputConfig.abs(ABS_X, -1)]),
                target_uinput="keyboard",
                output_symbol="b",
            )
        )
        preset.save()
        global_config.set_autoload_preset(group.key, preset_name)

        """Injection 1"""

        # should forward the event unchanged
        push_events(
            fixtures.gamepad,
            [InputEvent.key(BTN_B, 1, fixtures.gamepad.get_device_hash())],
        )

        self.daemon = Daemon()

        self.assertFalse(uinput_write_history_pipe[0].poll())

        # has been cleanedUp in setUp
        self.assertNotIn("keyboard", global_uinputs.devices)

        logger.info(f"start injector for {group.key}")
        self.daemon.start_injecting(group.key, preset_name)

        # created on demand
        self.assertIn("keyboard", global_uinputs.devices)
        self.assertNotIn("gamepad", global_uinputs.devices)

        self.assertEqual(self.daemon.get_state(group.key), InjectorState.STARTING)
        self.assertEqual(self.daemon.get_state(group2.key), InjectorState.UNKNOWN)

        event = uinput_write_history_pipe[0].recv()
        self.assertEqual(self.daemon.get_state(group.key), InjectorState.RUNNING)
        self.assertEqual(event.type, EV_KEY)
        self.assertEqual(event.code, BTN_B)
        self.assertEqual(event.value, 1)

        logger.info(f"stopping injector for {group.key}")
        self.daemon.stop_injecting(group.key)
        time.sleep(0.2)
        self.assertEqual(self.daemon.get_state(group.key), InjectorState.STOPPED)

        try:
            self.assertFalse(uinput_write_history_pipe[0].poll())
        except AssertionError:
            print("Unexpected", uinput_write_history_pipe[0].recv())
            # possibly a duplicate write!
            raise

        """Injection 2"""
        logger.info(f"start injector for {group.key}")
        self.daemon.start_injecting(group.key, preset_name)

        time.sleep(0.1)
        # -1234 will be classified as -1 by the injector
        push_events(
            fixtures.gamepad,
            [InputEvent.abs(ABS_X, -1234, fixtures.gamepad.get_device_hash())],
        )
        time.sleep(0.1)

        self.assertTrue(uinput_write_history_pipe[0].poll())

        # the written key is a key-down event, not the original
        # event value of -1234
        event = uinput_write_history_pipe[0].recv()

        self.assertEqual(event.type, EV_KEY)
        self.assertEqual(event.code, KEY_B)
        self.assertEqual(event.value, 1)

    def test_config_dir(self):
        global_config.set("foo", "bar")
        self.assertEqual(global_config.get("foo"), "bar")

        # freshly loads the config and therefore removes the previosly added key.
        # This is important so that if the service is started via sudo or pkexec
        # it knows where to look for configuration files.
        self.daemon = Daemon()
        self.assertEqual(self.daemon.config_dir, get_config_path())
        self.assertIsNone(global_config.get("foo"))

    def test_refresh_on_start(self):
        if os.path.exists(get_config_path("xmodmap.json")):
            os.remove(get_config_path("xmodmap.json"))

        preset_name = "foo"
        key_code = 9
        group_name = "9876 name"

        # expected key of the group
        group_key = group_name

        group = groups.find(name=group_name)
        # this test only makes sense if this device is unknown yet
        self.assertIsNone(group)

        system_mapping.clear()
        system_mapping._set("a", KEY_A)

        preset = Preset(get_preset_path(group_name, preset_name))
        preset.add(
            Mapping.from_combination(
                InputCombination([InputConfig.key(key_code)]), "keyboard", "a"
            )
        )

        # make the daemon load the file instead
        with open(get_config_path("xmodmap.json"), "w") as file:
            json.dump(system_mapping._mapping, file, indent=4)
        system_mapping.clear()

        preset.save()
        global_config.set_autoload_preset(group_key, preset_name)
        self.daemon = Daemon()

        # make sure the devices are populated
        groups.refresh()

        # the daemon is supposed to find this device by calling refresh
        fixture = Fixture(
            capabilities={evdev.ecodes.EV_KEY: [key_code]},
            phys="9876 phys",
            info=evdev.device.DeviceInfo(4, 5, 6, 7),
            name=group_name,
            path=self.new_fixture_path,
        )
        fixtures[self.new_fixture_path] = fixture
        push_events(fixture, [InputEvent.key(key_code, 1, fixture.get_device_hash())])
        self.daemon.start_injecting(group_key, preset_name)

        # test if the injector called groups.refresh successfully
        group = groups.find(key=group_key)
        self.assertEqual(group.name, group_name)
        self.assertEqual(group.key, group_key)

        time.sleep(0.1)
        self.assertTrue(uinput_write_history_pipe[0].poll())

        event = uinput_write_history_pipe[0].recv()
        self.assertEqual(event, (EV_KEY, KEY_A, 1))

        self.daemon.stop_injecting(group_key)
        time.sleep(0.2)
        self.assertEqual(self.daemon.get_state(group_key), InjectorState.STOPPED)

    def test_refresh_for_unknown_key(self):
        device_9876 = "9876 name"
        # this test only makes sense if this device is unknown yet
        self.assertIsNone(groups.find(name=device_9876))

        self.daemon = Daemon()

        # make sure the devices are populated
        groups.refresh()

        self.daemon.refresh()

        fixtures[self.new_fixture_path] = Fixture(
            capabilities={evdev.ecodes.EV_KEY: [evdev.ecodes.KEY_A]},
            phys="9876 phys",
            info=evdev.device.DeviceInfo(4, 5, 6, 7),
            name=device_9876,
            path=self.new_fixture_path,
        )

        self.daemon._autoload("25v7j9q4vtj")
        # this is unknown, so the daemon will scan the devices again

        # test if the injector called groups.refresh successfully
        self.assertIsNotNone(groups.find(name=device_9876))

    def test_xmodmap_file(self):
        """Create a custom xmodmap file, expect the daemon to read keycodes from it."""
        from_keycode = evdev.ecodes.KEY_A
        target = "keyboard"
        to_name = "q"
        to_keycode = 100

        name = "Bar Device"
        preset_name = "foo"
        group = groups.find(name=name)

        config_dir = os.path.join(tmp, "foo")

        path = os.path.join(config_dir, "presets", name, f"{preset_name}.json")

        preset = Preset(path)
        preset.add(
            Mapping.from_combination(
                InputCombination([InputConfig.key(from_keycode)]),
                target,
                to_name,
            )
        )
        preset.save()

        system_mapping.clear()

        push_events(
            fixtures.bar_device,
            [
                InputEvent.key(
                    from_keycode,
                    1,
                    origin_hash=fixtures.bar_device.get_device_hash(),
                )
            ],
        )

        # an existing config file is needed otherwise set_config_dir refuses
        # to use the directory
        config_path = os.path.join(config_dir, "config.json")
        global_config.path = config_path
        global_config._save_config()

        # finally, create the xmodmap file
        xmodmap_path = os.path.join(config_dir, "xmodmap.json")
        with open(xmodmap_path, "w") as file:
            file.write(f'{{"{to_name}":{to_keycode}}}')

        # test setup complete

        self.daemon = Daemon()
        self.daemon.set_config_dir(config_dir)

        self.daemon.start_injecting(group.key, preset_name)

        time.sleep(0.1)
        self.assertTrue(uinput_write_history_pipe[0].poll())

        event = uinput_write_history_pipe[0].recv()
        self.assertEqual(event.type, EV_KEY)
        self.assertEqual(event.code, to_keycode)
        self.assertEqual(event.value, 1)

    def test_start_stop(self):
        group_key = "Qux/Device?"
        group = groups.find(key=group_key)
        preset_name = "preset8"

        daemon = Daemon()
        self.daemon = daemon

        pereset = Preset(group.get_preset_path(preset_name))
        pereset.add(
            Mapping.from_combination(
                InputCombination([InputConfig(type=EV_KEY, code=KEY_A)]),
                "keyboard",
                "a",
            )
        )
        pereset.save()

        # start
        daemon.start_injecting(group_key, preset_name)
        # explicit start, not autoload, so the history stays empty
        self.assertNotIn(group_key, daemon.autoload_history._autoload_history)
        self.assertTrue(daemon.autoload_history.may_autoload(group_key, preset_name))
        # path got translated to the device name
        self.assertIn(group_key, daemon.injectors)

        # start again
        previous_injector = daemon.injectors[group_key]
        self.assertNotEqual(previous_injector.get_state(), InjectorState.STOPPED)
        daemon.start_injecting(group_key, preset_name)
        self.assertNotIn(group_key, daemon.autoload_history._autoload_history)
        self.assertTrue(daemon.autoload_history.may_autoload(group_key, preset_name))
        self.assertIn(group_key, daemon.injectors)
        time.sleep(0.2)
        self.assertEqual(previous_injector.get_state(), InjectorState.STOPPED)
        # a different injetor is now running
        self.assertNotEqual(previous_injector, daemon.injectors[group_key])
        self.assertNotEqual(
            daemon.injectors[group_key].get_state(), InjectorState.STOPPED
        )

        # trying to inject a non existing preset keeps the previous inejction
        # alive
        injector = daemon.injectors[group_key]
        daemon.start_injecting(group_key, "qux")
        self.assertEqual(injector, daemon.injectors[group_key])
        self.assertNotEqual(
            daemon.injectors[group_key].get_state(), InjectorState.STOPPED
        )

        # trying to start injecting for an unknown device also just does
        # nothing
        daemon.start_injecting("quux", "qux")
        self.assertNotEqual(
            daemon.injectors[group_key].get_state(), InjectorState.STOPPED
        )

        # after all that stuff autoload_history is still unharmed
        self.assertNotIn(group_key, daemon.autoload_history._autoload_history)
        self.assertTrue(daemon.autoload_history.may_autoload(group_key, preset_name))

        # stop
        daemon.stop_injecting(group_key)
        time.sleep(0.2)
        self.assertNotIn(group_key, daemon.autoload_history._autoload_history)
        self.assertEqual(daemon.injectors[group_key].get_state(), InjectorState.STOPPED)
        self.assertTrue(daemon.autoload_history.may_autoload(group_key, preset_name))

    def test_autoload(self):
        preset_name = "preset7"
        group_key = "Qux/Device?"
        group = groups.find(key=group_key)

        daemon = Daemon()
        self.daemon = daemon

        preset = Preset(group.get_preset_path(preset_name))
        preset.add(
            Mapping.from_combination(
                InputCombination([InputConfig(type=EV_KEY, code=KEY_A)]),
                "keyboard",
                "a",
            )
        )
        preset.save()

        # no autoloading is configured yet
        self.daemon._autoload(group_key)
        self.assertNotIn(group_key, daemon.autoload_history._autoload_history)
        self.assertTrue(daemon.autoload_history.may_autoload(group_key, preset_name))

        global_config.set_autoload_preset(group_key, preset_name)
        len_before = len(self.daemon.autoload_history._autoload_history)
        # now autoloading is configured, so it will autoload
        self.daemon._autoload(group_key)
        len_after = len(self.daemon.autoload_history._autoload_history)
        self.assertEqual(
            daemon.autoload_history._autoload_history[group_key][1], preset_name
        )
        self.assertFalse(daemon.autoload_history.may_autoload(group_key, preset_name))
        injector = daemon.injectors[group_key]
        self.assertEqual(len_before + 1, len_after)

        # calling duplicate get_autoload does nothing
        self.daemon._autoload(group_key)
        self.assertEqual(
            daemon.autoload_history._autoload_history[group_key][1], preset_name
        )
        self.assertEqual(injector, daemon.injectors[group_key])
        self.assertFalse(daemon.autoload_history.may_autoload(group_key, preset_name))

        # explicit start_injecting clears the autoload history
        self.daemon.start_injecting(group_key, preset_name)
        self.assertTrue(daemon.autoload_history.may_autoload(group_key, preset_name))

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
        preset_name = "preset7"
        group = groups.find(key="Foo Device 2")
        preset = Preset(group.get_preset_path(preset_name))
        preset.add(
            Mapping.from_combination(
                InputCombination([InputConfig(type=3, code=2, analog_threshold=1)]),
                "keyboard",
                "a",
            )
        )
        preset.save()
        global_config.set_autoload_preset(group.key, preset_name)

        # ignored, won't cause problems:
        global_config.set_autoload_preset("non-existant-key", "foo")

        self.daemon.autoload()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[group.key][1], preset_name)

    def test_autoload_3(self):
        # based on a bug
        preset_name = "preset7"
        group = groups.find(key="Foo Device 2")

        preset = Preset(group.get_preset_path(preset_name))
        preset.add(
            Mapping.from_combination(
                InputCombination([InputConfig(type=3, code=2, analog_threshold=1)]),
                "keyboard",
                "a",
            )
        )
        preset.save()

        global_config.set_autoload_preset(group.key, preset_name)

        self.daemon = Daemon()
        groups.set_groups([])  # caused the bug
        self.assertIsNone(groups.find(key="Foo Device 2"))
        self.daemon.autoload()

        # it should try to refresh the groups because all the
        # group_keys are unknown at the moment
        history = self.daemon.autoload_history._autoload_history
        self.assertEqual(history[group.key][1], preset_name)
        self.assertEqual(self.daemon.get_state(group.key), InjectorState.STARTING)
        self.assertIsNotNone(groups.find(key="Foo Device 2"))


if __name__ == "__main__":
    unittest.main()
