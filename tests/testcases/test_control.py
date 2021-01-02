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
import unittest
import collections
from importlib.util import spec_from_loader, module_from_spec
from importlib.machinery import SourceFileLoader

from keymapper.state import custom_mapping
from keymapper.config import config
from keymapper.daemon import Daemon
from keymapper.mapping import Mapping
from keymapper.paths import get_preset_path

from tests.test import cleanup


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
    ['command', 'preset', 'device', 'list_devices', 'key_names']
)


class TestControl(unittest.TestCase):
    def tearDown(self):
        cleanup()

    def test_autoload(self):
        devices = ['device 1234', 'device 2345']
        presets = ['preset', 'bar']
        paths = [
            get_preset_path(devices[0], presets[0]),
            get_preset_path(devices[1], presets[1])
        ]
        xmodmap = 'a/xmodmap.json'

        Mapping().save(paths[0])
        Mapping().save(paths[1])

        daemon = Daemon()

        start_history = []
        stop_history = []
        daemon.start_injecting = lambda *args: start_history.append(args)
        daemon.stop = lambda *args: stop_history.append(args)

        config.set_autoload_preset(devices[0], presets[0])
        config.set_autoload_preset(devices[1], presets[1])

        control(options('autoload', None, None, False, False), daemon, xmodmap)

        self.assertEqual(len(start_history), 2)
        self.assertEqual(len(stop_history), 1)
        self.assertEqual(start_history[0], (devices[0], os.path.expanduser(paths[0]), xmodmap))
        self.assertEqual(start_history[1], (devices[1], os.path.abspath(paths[1]), xmodmap))

    def test_start_stop(self):
        device = 'device 1234'
        path = '~/a/preset.json'
        xmodmap = 'a/xmodmap.json'

        daemon = Daemon()

        start_history = []
        stop_history = []
        daemon.start_injecting = lambda *args: start_history.append(args)
        daemon.stop_injecting = lambda *args: stop_history.append(args)

        control(options('start', path, device, False, False), daemon, xmodmap)
        control(options('stop', None, device, False, False), daemon, None)

        self.assertEqual(len(start_history), 1)
        self.assertEqual(len(stop_history), 1)
        self.assertEqual(start_history[0], (device, os.path.expanduser(path), xmodmap))
        self.assertEqual(stop_history[0], (device,))


if __name__ == "__main__":
    unittest.main()
