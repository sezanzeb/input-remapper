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

import copy

from inputremapper.logger import logger, VERSION

NONE = "none"

INITIAL_CONFIG = {
    "version": VERSION,
    "autoload": {},
    "macros": {
        # some time between keystrokes might be required for them to be
        # detected properly in software.
        "keystroke_sleep_ms": 10
    },
    "gamepad": {
        "joystick": {
            # very small movements of the joystick should result in very
            # small mouse movements. With a non_linearity of 1 it is
            # impossible/hard to even find a resting position that won't
            # move the cursor.
            "non_linearity": 4,
            "pointer_speed": 80,
            "left_purpose": NONE,
            "right_purpose": NONE,
            "x_scroll_speed": 2,
            "y_scroll_speed": 0.5,
        },
    },
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
        path : string or string[]
            For example 'macros.keystroke_sleep_ms'
            or ['macros', 'keystroke_sleep_ms']
        config : dict
            The dictionary to search. Defaults to self._config.
        """
        chunks = path.copy() if isinstance(path, list) else path.split(".")

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
        path : string or string[]
            For example 'macros.keystroke_sleep_ms'
            or ['macros', 'keystroke_sleep_ms']
        """

        def callback(parent, child, chunk):
            if child is not None:
                del parent[chunk]

        self._resolve(path, callback)

    def set(self, path, value):
        """Set a config key.

        Parameters
        ----------
        path : string or string[]
            For example 'macros.keystroke_sleep_ms'
            or ['macros', 'keystroke_sleep_ms']
        value : any
        """
        logger.info('Changing "%s" to "%s" in %s', path, value, self.__class__.__name__)

        def callback(parent, child, chunk):
            parent[chunk] = value

        self._resolve(path, callback)

    def get(self, path, log_unknown=True):
        """Get a config value. If not set, return the default

        Parameters
        ----------
        path : string or string[]
            For example 'macros.keystroke_sleep_ms'
        log_unknown : bool
            If True, write an error if `path` does not exist in the config
        """

        def callback(parent, child, chunk):
            return child

        resolved = self._resolve(path, callback)
        if resolved is None and self.fallback is not None:
            resolved = self.fallback._resolve(path, callback)
        if resolved is None:
            # don't create new empty stuff in INITIAL_CONFIG with _resolve
            initial_copy = copy.deepcopy(INITIAL_CONFIG)
            resolved = self._resolve(path, callback, initial_copy)

        if resolved is None and log_unknown:
            logger.error('Unknown config key "%s"', path)

        # modifications are only allowed via set
        return copy.deepcopy(resolved)

    def clear_config(self):
        """Remove all configurations in memory."""
        self._config = {}
