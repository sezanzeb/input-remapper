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


"""Store which presets should be enabled for which device on login."""


import os
import json
import shutil
import copy

from keymapper.paths import CONFIG, USER, touch
from keymapper.logger import logger


CONFIG_PATH = os.path.join(CONFIG, 'config')

INITIAL_CONFIG = {
    'autoload': {},
    'macros': {
        # some time between keystrokes might be required for them to be
        # detected properly in software.
        'keystroke_sleep_ms': 10
    },
    'gamepad': {
        'non_linearity': 4,
        'pointer_speed': 80
    }
}


class _Config:
    def __init__(self):
        self._config = {}
        self.load_config()

    def _resolve(self, path, func):
        """Call func for the given config value."""
        chunks = path.split('.')
        child = self._config
        while True:
            chunk = chunks.pop(0)
            parent = child
            child = child.get(chunk)
            if len(chunks) == 0:
                # child is the value _resolve is looking for
                return func(parent, child, chunk)
            else:
                # child is another object
                if child is None:
                    parent[chunk] = {}
                    child = parent[chunk]

    def remove(self, path):
        """Remove a config key.

        Parameters
        ----------
        path : string
            For example 'macros.keystroke_sleep_ms'
        """
        def do(parent, child, chunk):
            if child is not None:
                del parent[chunk]

        self._resolve(path, do)

    def set(self, path, value):
        """Set a config key.

        Parameters
        ----------
        path : string
            For example 'macros.keystroke_sleep_ms'
        value : any
        """
        def do(parent, child, chunk):
            parent[chunk] = value

        self._resolve(path, do)

    def get(self, path, default=None):
        """Get a config value.

        Parameters
        ----------
        path : string
            For example 'macros.keystroke_sleep_ms'
        """
        return self._resolve(path, lambda parent, child, chunk: child)

    def set_autoload_preset(self, device, preset):
        """Set a preset to be automatically applied on start.

        Parameters
        ----------
        device : string
        preset : string or None
            if None, don't autoload something for this device
        """
        if preset is not None:
            self.set(f'autoload.{device}', preset)
        else:
            self.remove(f'autoload.{device}')

    def iterate_autoload_presets(self):
        """Get tuples of (device, preset)."""
        return self._config.get('autoload', {}).items()

    def is_autoloaded(self, device, preset):
        """Should this preset be loaded automatically?"""
        return self.get(f'autoload.{device}') == preset

    def load_config(self):
        """Load the config from the file system."""
        self.clear_config()

        if not os.path.exists(CONFIG_PATH):
            # treated like an empty config
            logger.debug('Config file "%s" doesn\'t exist', CONFIG_PATH)
            return

        with open(CONFIG_PATH, 'r') as file:
            self._config.update(json.load(file))
            logger.info('Loaded config from "%s"', CONFIG_PATH)

    def clear_config(self):
        """Reset the configuration to the initial values."""
        self._config = copy.deepcopy(INITIAL_CONFIG)

    def save_config(self):
        """Save the config to the file system."""
        touch(CONFIG_PATH)

        with open(CONFIG_PATH, 'w') as file:
            json.dump(self._config, file, indent=4)
            logger.info('Saved config to %s', CONFIG_PATH)
            shutil.chown(CONFIG_PATH, USER, USER)
            file.write('\n')


config = _Config()
