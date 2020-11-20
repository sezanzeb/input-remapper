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

from keymapper.paths import CONFIG
from keymapper.logger import logger


CONFIG_PATH = os.path.join(CONFIG, 'config')

# an empty config with basic expected substructures
INITIAL_CONFIG = {
    'autoload': [],
    'map_EV_REL_devices': True
}

_config = INITIAL_CONFIG.copy()


def set_autoload_preset(device, preset):
    """Set a preset to be automatically applied on start."""
    _config['autoload'].append({
        'device': device,
        'preset': preset
    })


def iterate_autoload_presets():
    """Yield tuples of (device, preset)."""
    for entry in _config['autoload']:
        yield entry['device'], entry['preset']


def set_modify_movement_devices(active):
    """Set if devices that control movements should also be mapped.

    This causes many movements event to be passed through python code,
    and if this ever seems to affect the responsiveness of mouse movements,
    it can be disabled. This may make mapping some keys of the device
    impossible.
    """
    global _config
    _config['map_EV_REL_devices'] = active


def load_config():
    """Load the config from the file system."""
    global _config

    if not os.path.exists(CONFIG_PATH):
        # has not yet been saved
        logger.debug('Config file not found')
        _config = INITIAL_CONFIG.copy()
        return

    with open(CONFIG_PATH, 'r') as f:
        _config = INITIAL_CONFIG.copy()
        _config.update(json.load(f))
        logger.info('Loaded config from %s', CONFIG_PATH)


def save_config():
    """Save the config to the file system."""
    with open(CONFIG_PATH, 'w') as f:
        json.dump(_config, f)
        logger.info('Saved config to %s', CONFIG_PATH)
