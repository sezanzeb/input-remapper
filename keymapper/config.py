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

from keymapper.paths import CONFIG, touch
from keymapper.logger import logger


CONFIG_PATH = os.path.join(CONFIG, 'config')

INITIAL_CONFIG = {
    'autoload': {},
    'macros': {
        # some time between keystrokes might be required for them to be
        # detected properly in software.
        'keystroke_sleep_ms': 10
    }
}


class _Config:
    def __init__(self):
        self._config = {}
        self.load_config()

    def set_autoload_preset(self, device, preset, load=True):
        """Set a preset to be automatically applied on start."""
        if self._config.get('autoload') is None:
            self._config['autoload'] = {}

        if load:
            self._config['autoload'][device] = preset
        elif self._config['autoload'].get(device) is not None:
            del self._config['autoload'][device]

    def get_keystroke_sleep(self):
        """Get the seconds of sleep between key down and up events."""
        macros = self._config.get('macros', {})
        return macros.get('keystroke_sleep_ms', 10)

    def iterate_autoload_presets(self):
        """Get tuples of (device, preset)."""
        return self._config.get('autoload', {}).items()

    def is_autoloaded(self, device, preset):
        """Should this preset be loaded automatically?"""
        autoload_map = self._config.get('autoload')
        if autoload_map is None:
            return False

        autoload_preset = autoload_map.get(device)
        if autoload_preset is None:
            return False

        return autoload_preset == preset

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
            shutil.chown(CONFIG_PATH, os.getlogin(), os.getlogin())
            file.write('\n')


config = _Config()
