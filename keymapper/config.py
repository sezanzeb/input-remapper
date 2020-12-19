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

from keymapper.paths import CONFIG, USER, touch
from keymapper.logger import logger


MOUSE = 'mouse'
WHEEL = 'wheel'

CONFIG_PATH = os.path.join(CONFIG, 'config.json')

# to support early versions in which the .json ending was missing:
deprecated_path = os.path.join(CONFIG, 'config')
if os.path.exists(deprecated_path) and not os.path.exists(CONFIG_PATH):
    logger.info('Moving "%s" to "%s"', deprecated_path, CONFIG_PATH)
    os.rename(os.path.join(CONFIG, 'config'), CONFIG_PATH)

INITIAL_CONFIG = {
    'autoload': {},
    'macros': {
        # some time between keystrokes might be required for them to be
        # detected properly in software.
        'keystroke_sleep_ms': 10
    },
    'gamepad': {
        'joystick': {
            # very small movements of the joystick should result in very
            # small mouse movements. With a non_linearity of 1 it is
            # impossible/hard to even find a resting position that won't
            # move the cursor.
            'non_linearity': 4,
            'pointer_speed': 80,
            'left_purpose': MOUSE,
            'right_purpose': WHEEL,
        },
    }
}


class ConfigBase:
    """Base class for config objects.

    Loading and saving is optional and handled by classes that derive from
    this base.
    """
    def __init__(self, fallback=None):
        """Set up the needed members to turn your object into a config.

        Parameters
        ----------
        fallback : ConfigBase
            a configuration that contains fallback default configs, if your
            object doesn't configure a certain key.
        """
        self._config = {}
        self.fallback = fallback

    def _resolve(self, path, func, config=None):
        """Call func for the given config value.

        Parameters
        ----------
        config : dict
            The dictionary to search. Defaults to self._config.
        """
        chunks = path.split('.')

        if config is None:
            child = self._config
        else:
            child = config

        while True:
            chunk = chunks.pop(0)
            parent = child
            child = child.get(chunk)
            if len(chunks) == 0:
                # child is the value _resolve is looking for
                return func(parent, child, chunk)

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
        def callback(parent, child, chunk):
            if child is not None:
                del parent[chunk]

        self._resolve(path, callback)

    def set(self, path, value):
        """Set a config key.

        Parameters
        ----------
        path : string
            For example 'macros.keystroke_sleep_ms'
        value : any
        """
        logger.debug(
            'Changing "%s" to "%s" in %s',
            path, value, self.__class__.__name__
        )

        def callback(parent, child, chunk):
            parent[chunk] = value

        self._resolve(path, callback)

    def get(self, path, log_unknown=True):
        """Get a config value. If not set, return the default

        Parameters
        ----------
        path : string
            For example 'macros.keystroke_sleep_ms'
        log_unknown : bool
            If True, write an error.
        """
        def callback(parent, child, chunk):
            return child

        resolved = self._resolve(path, callback)
        if resolved is None and self.fallback is not None:
            resolved = self.fallback._resolve(path, callback)
        if resolved is None:
            resolved = self._resolve(path, callback, INITIAL_CONFIG)

        if resolved is None and log_unknown:
            logger.error('Unknown config key "%s"', path)

        return resolved

    def clear_config(self):
        """Remove all configurations in memory."""
        self._config = {}


class GlobalConfig(ConfigBase):
    """Global default configuration.

    It can also contain some extra stuff not relevant for presets, like the
    autoload stuff. If presets have a config key set, it will ignore
    the default global configuration for that one. If none of the configs
    have the key set, a hardcoded default value will be used.
    """
    def __init__(self):
        super().__init__()
        self.load_config()

    def set_autoload_preset(self, device, preset):
        """Set a preset to be automatically applied on start.

        Parameters
        ----------
        device : string
        preset : string or None
            if None, don't autoload something for this device.
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
        return self.get(f'autoload.{device}', '') == preset

    def load_config(self):
        """Load the config from the file system."""
        self.clear_config()

        if not os.path.exists(CONFIG_PATH):
            # treated like an empty config
            logger.debug('Config "%s" doesn\'t exist yet', CONFIG_PATH)
            self.clear_config()
            self._config = INITIAL_CONFIG
            self.save_config()
            return

        with open(CONFIG_PATH, 'r') as file:
            self._config.update(json.load(file))
            logger.info('Loaded config from "%s"', CONFIG_PATH)

    def save_config(self):
        """Save the config to the file system."""
        touch(CONFIG_PATH)

        with open(CONFIG_PATH, 'w') as file:
            json.dump(self._config, file, indent=4)
            logger.info('Saved config to %s', CONFIG_PATH)
            shutil.chown(CONFIG_PATH, USER, USER)
            file.write('\n')


config = GlobalConfig()
