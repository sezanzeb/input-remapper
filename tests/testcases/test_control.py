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


"""Testing the key-mapper-control command"""


import os
import time
import unittest
import collections
from importlib.util import spec_from_loader, module_from_spec
from importlib.machinery import SourceFileLoader

from keymapper.state import custom_mapping
from keymapper.config import config
from keymapper.daemon import Daemon
from keymapper.mapping import Mapping
from keymapper.paths import get_preset_path

from tests.test import quick_cleanup, tmp


def import_control():
    """Import the core function of the key-mapper-control command."""
    custom_mapping.empty()

    bin_path = os.path.join(os.getcwd(), 'bin', 'key-mapper-control')

    loader = SourceFileLoader('__not_main_idk__', bin_path)
    spec = spec_from_loader('__not_main_idk__', loader)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    return module.main


control = import_control()


options = collections.namedtuple(
    'options',
    ['command', 'config_dir', 'preset', 'device', 'list_devices', 'key_names']
)


class TestControl(unittest.TestCase):
    def tearDown(self):
        quick_cleanup()

    def test_autoload(self):
        devices = ['device 1', 'device 2']
        presets = ['bar0', 'bar', 'bar2']
        paths = [
            get_preset_path(devices[0], presets[0]),
            get_preset_path(devices[1], presets[1]),
            get_preset_path(devices[1], presets[2])
        ]

        Mapping().save(paths[0])
        Mapping().save(paths[1])
        Mapping().save(paths[2])

        daemon = Daemon()

        start_history = []
        stop_counter = 0
        # using an actual injector is not within the scope of this test
        class Injector:
            def stop_injecting(self, *args, **kwargs):
                nonlocal stop_counter
                stop_counter += 1
        def start_injecting(device, preset):
            print(f'\033[90mstart_injecting\033[0m')
            start_history.append((device, preset))
            daemon.injectors[device] = Injector()
        daemon.start_injecting = start_injecting

        config.set_autoload_preset(devices[0], presets[0])
        config.set_autoload_preset(devices[1], presets[1])
        config.save_config()

        control(options('autoload', None, None, None, False, False), daemon)
        self.assertEqual(len(start_history), 2)
        self.assertEqual(start_history[0], (devices[0], presets[0]))
        self.assertEqual(start_history[1], (devices[1], presets[1]))
        self.assertIn(devices[0], daemon.injectors)
        self.assertIn(devices[1], daemon.injectors)
        self.assertFalse(daemon.autoload_history.may_autoload(devices[0], presets[0]))
        self.assertFalse(daemon.autoload_history.may_autoload(devices[1], presets[1]))

        # calling autoload again doesn't load redundantly
        control(options('autoload', None, None, None, False, False), daemon)
        self.assertEqual(len(start_history), 2)
        self.assertEqual(stop_counter, 0)
        self.assertFalse(daemon.autoload_history.may_autoload(devices[0], presets[0]))
        self.assertFalse(daemon.autoload_history.may_autoload(devices[1], presets[1]))

        # unless the injection in question ist stopped
        control(options('stop', None, None, devices[0], False, False), daemon)
        self.assertEqual(stop_counter, 1)
        self.assertTrue(daemon.autoload_history.may_autoload(devices[0], presets[0]))
        self.assertFalse(daemon.autoload_history.may_autoload(devices[1], presets[1]))
        control(options('autoload', None, None, None, False, False), daemon)
        self.assertEqual(len(start_history), 3)
        self.assertEqual(start_history[2], (devices[0], presets[0]))
        self.assertFalse(daemon.autoload_history.may_autoload(devices[0], presets[0]))
        self.assertFalse(daemon.autoload_history.may_autoload(devices[1], presets[1]))

        # if a device name is passed, will only start injecting for that one
        control(options('stop-all', None, None, None, False, False), daemon)
        self.assertTrue(daemon.autoload_history.may_autoload(devices[0], presets[0]))
        self.assertTrue(daemon.autoload_history.may_autoload(devices[1], presets[1]))
        self.assertEqual(stop_counter, 3)
        config.set_autoload_preset(devices[1], presets[2])
        config.save_config()
        control(options('autoload', None, None, devices[1], False, False), daemon)
        self.assertEqual(len(start_history), 4)
        self.assertEqual(start_history[3], (devices[1], presets[2]))
        self.assertTrue(daemon.autoload_history.may_autoload(devices[0], presets[0]))
        self.assertFalse(daemon.autoload_history.may_autoload(devices[1], presets[2]))

        # autoloading for the same device again redundantly will not autoload
        # again
        control(options('autoload', None, None, devices[1], False, False), daemon)
        self.assertEqual(len(start_history), 4)
        self.assertEqual(stop_counter, 3)
        self.assertFalse(daemon.autoload_history.may_autoload(devices[1], presets[2]))

        # any other arbitrary preset may be autoloaded
        self.assertTrue(daemon.autoload_history.may_autoload(devices[1], 'quuuux'))

        # after 15 seconds it may be autoloaded again
        daemon.autoload_history._autoload_history[devices[1]] = (time.time() - 16, presets[2])
        self.assertTrue(daemon.autoload_history.may_autoload(devices[1], presets[2]))

    def test_autoload_other_path(self):
        devices = ['device 1', 'device 2']
        presets = ['bar123', 'bar2']
        config_dir = os.path.join(tmp, 'qux', 'quux')
        paths = [
            os.path.join(config_dir, 'presets', devices[0], presets[0] + '.json'),
            os.path.join(config_dir, 'presets', devices[1], presets[1] + '.json')
        ]

        Mapping().save(paths[0])
        Mapping().save(paths[1])

        daemon = Daemon()

        start_history = []
        daemon.start_injecting = lambda *args: start_history.append(args)

        config.path = os.path.join(config_dir, 'config.json')
        config.load_config()
        config.set_autoload_preset(devices[0], presets[0])
        config.set_autoload_preset(devices[1], presets[1])
        config.save_config()

        control(options('autoload', config_dir, None, None, False, False), daemon)

        self.assertEqual(len(start_history), 2)
        self.assertEqual(start_history[0], (devices[0], presets[0]))
        self.assertEqual(start_history[1], (devices[1], presets[1]))

    def test_start_stop(self):
        device = 'device 1234'
        preset = 'preset9'

        daemon = Daemon()

        start_history = []
        stop_history = []
        stop_all_history = []
        daemon.start_injecting = lambda *args: start_history.append(args)
        daemon.stop_injecting = lambda *args: stop_history.append(args)
        daemon.stop_all = lambda *args: stop_all_history.append(args)

        control(options('start', None, preset, device, False, False), daemon)
        self.assertEqual(len(start_history), 1)
        self.assertEqual(start_history[0], (device, preset))

        control(options('stop', None, None, device, False, False), daemon)
        self.assertEqual(len(stop_history), 1)
        self.assertEqual(stop_history[0], (device,))

        control(options('stop-all', None, None, None, False, False), daemon)
        self.assertEqual(len(stop_all_history), 1)
        self.assertEqual(stop_all_history[0], ())

    def test_config_not_found(self):
        device = 'device 1234'
        path = '~/a/preset.json'
        config_dir = '/foo/bar'

        daemon = Daemon()

        start_history = []
        stop_history = []
        daemon.start_injecting = lambda *args: start_history.append(args)
        daemon.stop_injecting = lambda *args: stop_history.append(args)

        options_1 = options('start', config_dir, path, device, False, False)
        self.assertRaises(SystemExit, lambda: control(options_1, daemon))

        options_2 = options('stop', config_dir, None, device, False, False)
        self.assertRaises(SystemExit, lambda: control(options_2, daemon))

    def test_autoload_config_dir(self):
        daemon = Daemon()

        path = os.path.join(tmp, 'foo')
        os.makedirs(path)
        with open(os.path.join(path, 'config.json'), 'w') as file:
            file.write('{"foo":"bar"}')

        self.assertIsNone(config.get('foo'))
        daemon.set_config_dir(path)
        # since daemon and this test share the same memory, the config
        # object that this test can access will be modified
        self.assertEqual(config.get('foo'), 'bar')

        # passing a path that doesn't exist or a path that doesn't contain
        # a config.json file won't do anything
        os.makedirs(os.path.join(tmp, 'bar'))
        daemon.set_config_dir(os.path.join(tmp, 'bar'))
        self.assertEqual(config.get('foo'), 'bar')
        daemon.set_config_dir(os.path.join(tmp, 'qux'))
        self.assertEqual(config.get('foo'), 'bar')


if __name__ == "__main__":
    unittest.main()
