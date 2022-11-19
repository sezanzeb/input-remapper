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
"""Store which presets should be enabled for which device on login."""

import os
import json
import copy

from inputremapper.configs.paths import CONFIG_PATH, USER, touch
from inputremapper.logger import logger
from inputremapper.configs.base_config import ConfigBase, INITIAL_CONFIG

MOUSE = "mouse"
WHEEL = "wheel"
BUTTONS = "buttons"
NONE = "none"


class GlobalConfig(ConfigBase):
    """Global default configuration.
    It can also contain some extra stuff not relevant for presets, like the
    autoload stuff. If presets have a config key set, it will ignore
    the default global configuration for that one. If none of the configs
    have the key set, a hardcoded default value will be used.
    """

    def __init__(self):
        self.path = os.path.join(CONFIG_PATH, "config.json")
        super().__init__()

    def set_autoload_preset(self, group_key, preset):
        """Set a preset to be automatically applied on start.
        Parameters
        ----------
        group_key : string
            the unique identifier of the group. This is used instead of the
            name to enable autoloading two different presets when two similar
            devices are connected.
        preset : string or None
            if None, don't autoload something for this device.
        """
        if preset is not None:
            self.set(["autoload", group_key], preset)
        else:
            logger.info('Not injecting for "%s" automatically anmore', group_key)
            self.remove(["autoload", group_key])

        self._save_config()

    def iterate_autoload_presets(self):
        """Get tuples of (device, preset)."""
        return self._config.get("autoload", {}).items()

    def is_autoloaded(self, group_key, preset):
        """Should this preset be loaded automatically?"""
        if group_key is None or preset is None:
            raise ValueError("Expected group_key and preset to not be None")

        return self.get(["autoload", group_key], log_unknown=False) == preset

    def load_config(self, path=None):
        """Load the config from the file system.
        Parameters
        ----------
        path : string or None
            If set, will change the path to load from and save to.
        """
        if path is not None:
            if not os.path.exists(path):
                logger.error('Config at "%s" not found', path)
                return

            self.path = path

        self.clear_config()

        if not os.path.exists(self.path):
            # treated like an empty config
            logger.debug('Config "%s" doesn\'t exist yet', self.path)
            self.clear_config()
            self._config = copy.deepcopy(INITIAL_CONFIG)
            self._save_config()
            return

        with open(self.path, "r") as file:
            try:
                self._config.update(json.load(file))
                logger.info('Loaded config from "%s"', self.path)
            except json.decoder.JSONDecodeError as error:
                logger.error(
                    'Failed to parse config "%s": %s. Using defaults',
                    self.path,
                    str(error),
                )
                # uses the default configuration when the config object
                # is empty automatically

    def _save_config(self):
        """Save the config to the file system."""
        if USER == "root":
            logger.debug("Skipping config file creation for the root user")
            return

        touch(self.path)

        with open(self.path, "w") as file:
            json.dump(self._config, file, indent=4)
            logger.info("Saved config to %s", self.path)
            file.write("\n")


global_config = GlobalConfig()
