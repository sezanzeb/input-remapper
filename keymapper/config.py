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

from keymapper.paths import CONFIG
from keymapper.logger import logger


CONFIG_PATH = os.path.join(CONFIG, 'config')

# an empty config with basic expected substructures
INITIAL_CONFIG = {
    'autoload': {},
    'map_EV_REL_devices': True
}


class _Config:
    def __init__(self):
        self._config = {}
        self.load_config()

    def set_autoload_preset(self, device, preset):
        """Set a preset to be automatically applied on start."""
        self._config['autoload'][device] = preset

    def iterate_autoload_presets(self):
        """get tuples of (device, preset)."""
        return self._config['autoload'].items()

    def set_modify_movement_devices(self, active):
        """Set if devices that control movements should also be mapped.

        This causes many movements event to be passed through python code,
        and if this ever seems to affect the responsiveness of mouse movements,
        it can be disabled. This is just an optional precaution. Disabling this
        may make mapping some keys of the device impossible.
        """
        self._config['map_EV_REL_devices'] = active

    def may_modify_movement_devices(self):
        """Get if devices that control movements may be modified as well.

        Since movement events happen quite often and fast, I'd like to
        add the option to disabling mapping those if it affects their
        performance. TODO figure out which devices to inject to instead?
        """
        return self._config['map_EV_REL_devices']

    def load_config(self):
        """Load the config from the file system."""
        if not os.path.exists(CONFIG_PATH):
            # has not yet been saved
            logger.info('Creating initial config')
            self._config = copy.deepcopy(INITIAL_CONFIG)
            self.save_config()
            return

        with open(CONFIG_PATH, 'r') as f:
            self._config = copy.deepcopy(INITIAL_CONFIG)
            self._config.update(json.load(f))
            logger.info('Loaded config from %s', CONFIG_PATH)

    def clear_config(self):
        """Needed for tests."""
        self._config = copy.deepcopy(INITIAL_CONFIG)

    def save_config(self):
        """Save the config to the file system."""
        if not os.path.exists(CONFIG_PATH):
            logger.debug('Creating "%s"', CONFIG_PATH)
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            os.mknod(CONFIG_PATH)

        with open(CONFIG_PATH, 'w') as f:
            json.dump(self._config, f, indent=4)
            logger.info('Saved config to %s', CONFIG_PATH)
            shutil.chown(CONFIG_PATH, os.getlogin())
            f.write('\n')


config = _Config()
