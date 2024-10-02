#!/usr/bin/python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2024 sezanzeb <b8x45ygc9@mozmail.com>
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


"""Testing the input-remapper-control command"""
import collections
import os
import time
import unittest
from importlib.machinery import SourceFileLoader
from importlib.util import spec_from_loader, module_from_spec
from unittest.mock import patch

from inputremapper.configs.global_config import GlobalConfig
from inputremapper.configs.migrations import Migrations
from inputremapper.configs.paths import PathUtils
from inputremapper.configs.preset import Preset
from inputremapper.daemon import Daemon
from inputremapper.groups import groups
from inputremapper.injection.global_uinputs import GlobalUInputs, FrontendUInput
from inputremapper.injection.mapping_handlers.mapping_parser import MappingParser
from tests.lib.test_setup import test_setup
from tests.lib.tmp import tmp


def import_control():
    """Import the core function of the input-remapper-control command."""
    bin_path = os.path.join(
        os.getcwd().rsplit("input-remapper")[0],
        "input-remapper",
        "bin",
        "input-remapper-control",
    )

    loader = SourceFileLoader("__not_main_idk__", bin_path)
    spec = spec_from_loader("__not_main_idk__", loader)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    return module.InputRemapperControl, module.Options


InputRemapperControl, Options = import_control()


options = collections.namedtuple(
    "options",
    ["command", "config_dir", "preset", "device", "list_devices", "key_names", "debug"],
)


@test_setup
class TestControl(unittest.TestCase):
    def setUp(self):
        self.global_config = GlobalConfig()
        self.global_uinputs = GlobalUInputs(FrontendUInput)
        self.migrations = Migrations(self.global_uinputs)
        self.mapping_parser = MappingParser(self.global_uinputs)
        self.input_remapper_control = InputRemapperControl(
            self.global_config, self.migrations
        )

    def test_autoload(self):
        device_keys = ["Foo Device 2", "Bar Device"]
        groups_ = [groups.find(key=key) for key in device_keys]
        presets = ["bar0", "bar", "bar2"]
        paths = [
            PathUtils.get_preset_path(groups_[0].name, presets[0]),
            PathUtils.get_preset_path(groups_[1].name, presets[1]),
            PathUtils.get_preset_path(groups_[1].name, presets[2]),
        ]

        Preset(paths[0]).save()
        Preset(paths[1]).save()
        Preset(paths[2]).save()

        daemon = Daemon(self.global_config, self.global_uinputs, self.mapping_parser)

        self.input_remapper_control.set_daemon(daemon)

        start_history = []
        stop_counter = 0

        # using an actual injector is not within the scope of this test
        class Injector:
            def stop_injecting(self, *args, **kwargs):
                nonlocal stop_counter
                stop_counter += 1

        def start_injecting(device: str, preset: str):
            print(f'\033[90mstart_injecting "{device}" "{preset}"\033[0m')
            start_history.append((device, preset))
            daemon.injectors[device] = Injector()

        patch.object(daemon, "start_injecting", start_injecting).start()

        self.global_config.set_autoload_preset(groups_[0].key, presets[0])
        self.global_config.set_autoload_preset(groups_[1].key, presets[1])

        self.input_remapper_control.communicate(
            command="autoload",
            config_dir=None,
            preset=None,
            device=None,
        )
        self.assertEqual(len(start_history), 2)
        self.assertEqual(start_history[0], (groups_[0].key, presets[0]))
        self.assertEqual(start_history[1], (groups_[1].key, presets[1]))
        self.assertIn(groups_[0].key, daemon.injectors)
        self.assertIn(groups_[1].key, daemon.injectors)
        self.assertFalse(
            daemon.autoload_history.may_autoload(groups_[0].key, presets[0])
        )
        self.assertFalse(
            daemon.autoload_history.may_autoload(groups_[1].key, presets[1])
        )

        # calling autoload again doesn't load redundantly
        self.input_remapper_control.communicate(
            command="autoload",
            config_dir=None,
            preset=None,
            device=None,
        )
        self.assertEqual(len(start_history), 2)
        self.assertEqual(stop_counter, 0)
        self.assertFalse(
            daemon.autoload_history.may_autoload(groups_[0].key, presets[0])
        )
        self.assertFalse(
            daemon.autoload_history.may_autoload(groups_[1].key, presets[1])
        )

        # unless the injection in question ist stopped
        self.input_remapper_control.communicate(
            command="stop",
            config_dir=None,
            preset=None,
            device=groups_[0].key,
        )
        self.assertEqual(stop_counter, 1)
        self.assertTrue(
            daemon.autoload_history.may_autoload(groups_[0].key, presets[0])
        )
        self.assertFalse(
            daemon.autoload_history.may_autoload(groups_[1].key, presets[1])
        )
        self.input_remapper_control.communicate(
            command="autoload",
            config_dir=None,
            preset=None,
            device=None,
        )
        self.assertEqual(len(start_history), 3)
        self.assertEqual(start_history[2], (groups_[0].key, presets[0]))
        self.assertFalse(
            daemon.autoload_history.may_autoload(groups_[0].key, presets[0])
        )
        self.assertFalse(
            daemon.autoload_history.may_autoload(groups_[1].key, presets[1])
        )

        # if a device name is passed, will only start injecting for that one
        self.input_remapper_control.communicate(
            command="stop-all",
            config_dir=None,
            preset=None,
            device=None,
        )
        self.assertTrue(
            daemon.autoload_history.may_autoload(groups_[0].key, presets[0])
        )
        self.assertTrue(
            daemon.autoload_history.may_autoload(groups_[1].key, presets[1])
        )
        self.assertEqual(stop_counter, 3)
        self.global_config.set_autoload_preset(groups_[1].key, presets[2])
        self.input_remapper_control.communicate(
            command="autoload",
            config_dir=None,
            preset=None,
            device=groups_[1].key,
        )
        self.assertEqual(len(start_history), 4)
        self.assertEqual(start_history[3], (groups_[1].key, presets[2]))
        self.assertTrue(
            daemon.autoload_history.may_autoload(groups_[0].key, presets[0])
        )
        self.assertFalse(
            daemon.autoload_history.may_autoload(groups_[1].key, presets[2])
        )

        # autoloading for the same device again redundantly will not autoload
        # again
        self.input_remapper_control.communicate(
            command="autoload",
            config_dir=None,
            preset=None,
            device=groups_[1].key,
        )
        self.assertEqual(len(start_history), 4)
        self.assertEqual(stop_counter, 3)
        self.assertFalse(
            daemon.autoload_history.may_autoload(groups_[1].key, presets[2])
        )

        # any other arbitrary preset may be autoloaded
        self.assertTrue(daemon.autoload_history.may_autoload(groups_[1].key, "quuuux"))

        # after 15 seconds it may be autoloaded again
        daemon.autoload_history._autoload_history[groups_[1].key] = (
            time.time() - 16,
            presets[2],
        )
        self.assertTrue(
            daemon.autoload_history.may_autoload(groups_[1].key, presets[2])
        )

    def test_autoload_other_path(self):
        device_names = ["Foo Device", "Bar Device"]
        groups_ = [groups.find(name=name) for name in device_names]
        presets = ["bar123", "bar2"]
        config_dir = os.path.join(tmp, "qux", "quux")
        paths = [
            os.path.join(config_dir, "presets", device_names[0], presets[0] + ".json"),
            os.path.join(config_dir, "presets", device_names[1], presets[1] + ".json"),
        ]

        Preset(paths[0]).save()
        Preset(paths[1]).save()

        daemon = Daemon(self.global_config, self.global_uinputs, self.mapping_parser)
        self.input_remapper_control.set_daemon(daemon)

        start_history = []
        daemon.start_injecting = lambda *args: start_history.append(args)

        self.global_config.path = os.path.join(config_dir, "config.json")
        self.global_config.load_config()
        self.global_config.set_autoload_preset(device_names[0], presets[0])
        self.global_config.set_autoload_preset(device_names[1], presets[1])

        self.input_remapper_control.communicate(
            command="autoload",
            config_dir=config_dir,
            preset=None,
            device=None,
        )

        self.assertEqual(len(start_history), 2)
        self.assertEqual(start_history[0], (groups_[0].key, presets[0]))
        self.assertEqual(start_history[1], (groups_[1].key, presets[1]))

    def test_start_stop(self):
        group = groups.find(key="Foo Device 2")
        preset = "preset9"

        daemon = Daemon(self.global_config, self.global_uinputs, self.mapping_parser)
        self.input_remapper_control.set_daemon(daemon)

        start_history = []
        stop_history = []
        stop_all_history = []
        daemon.start_injecting = lambda *args: start_history.append(args)
        daemon.stop_injecting = lambda *args: stop_history.append(args)
        daemon.stop_all = lambda *args: stop_all_history.append(args)

        self.input_remapper_control.communicate(
            command="start",
            config_dir=None,
            preset=preset,
            device=group.paths[0],
        )
        self.assertEqual(len(start_history), 1)
        self.assertEqual(start_history[0], (group.key, preset))

        self.input_remapper_control.communicate(
            command="stop",
            config_dir=None,
            preset=None,
            device=group.paths[1],
        )
        self.assertEqual(len(stop_history), 1)
        # provided any of the groups paths as --device argument, figures out
        # the correct group.key to use here
        self.assertEqual(stop_history[0], (group.key,))

        self.input_remapper_control.communicate(
            command="stop-all",
            config_dir=None,
            preset=None,
            device=None,
        )
        self.assertEqual(len(stop_all_history), 1)
        self.assertEqual(stop_all_history[0], ())

    def test_config_not_found(self):
        key = "Foo Device 2"
        path = "~/a/preset.json"
        config_dir = "/foo/bar"

        daemon = Daemon(self.global_config, self.global_uinputs, self.mapping_parser)
        self.input_remapper_control.set_daemon(daemon)

        start_history = []
        stop_history = []
        daemon.start_injecting = lambda *args: start_history.append(args)
        daemon.stop_injecting = lambda *args: stop_history.append(args)

        self.assertRaises(
            SystemExit,
            lambda: self.input_remapper_control.communicate(
                command="start",
                config_dir=config_dir,
                preset=path,
                device=key,
            ),
        )

        self.assertRaises(
            SystemExit,
            lambda: self.input_remapper_control.communicate(
                command="stop",
                config_dir=config_dir,
                preset=None,
                device=key,
            ),
        )

    def test_autoload_config_dir(self):
        daemon = Daemon(self.global_config, self.global_uinputs, self.mapping_parser)

        path = os.path.join(tmp, "foo")
        os.makedirs(path)
        with open(os.path.join(path, "config.json"), "w") as file:
            file.write('{"foo":"bar"}')

        self.assertIsNone(self.global_config.get("foo"))
        daemon.set_config_dir(path)
        # since daemon and this test share the same memory, the global_config
        # object that this test can access will be modified
        self.assertEqual(self.global_config.get("foo"), "bar")

        # passing a path that doesn't exist or a path that doesn't contain
        # a config.json file won't do anything
        os.makedirs(os.path.join(tmp, "bar"))
        daemon.set_config_dir(os.path.join(tmp, "bar"))
        self.assertEqual(self.global_config.get("foo"), "bar")
        daemon.set_config_dir(os.path.join(tmp, "qux"))
        self.assertEqual(self.global_config.get("foo"), "bar")

    def test_internals_reader(self):
        with patch.object(os, "system") as os_system_patch:
            self.input_remapper_control.internals("start-reader-service", False)
            os_system_patch.assert_called_once()
            self.assertIn(
                "input-remapper-reader-service", os_system_patch.call_args.args[0]
            )
            self.assertNotIn("-d", os_system_patch.call_args.args[0])

    def test_internals_daemon(self):
        with patch.object(os, "system") as os_system_patch:
            self.input_remapper_control.internals("start-daemon", True)
            os_system_patch.assert_called_once()
            self.assertIn("input-remapper-service", os_system_patch.call_args.args[0])
            self.assertIn("-d", os_system_patch.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
