# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2025 sezanzeb <b8x45ygc9@mozmail.com>
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

from __future__ import annotations

import copy
from typing import Union, List, Optional, Callable, Any, Dict

from inputremapper.logging.logger import logger, VERSION

NONE = "none"


class ConfigBase:
    """Base class for config objects.

    Loading and saving is optional and handled by classes that derive from
    this base.
    """

    def __init__(self, defaults: Optional[Dict] = None):
        """Set up the needed members to turn your object into a config."""
        self._config = {}
        self.defaults = defaults

    def _resolve(
        self,
        path: Union[str, List[str]],
        func: Callable,
        config: Optional[dict] = None,
    ):
        """Call func for the given config value.

        Parameters
        ----------
        path
            For example 'macros.keystroke_sleep_ms'
            or ['macros', 'keystroke_sleep_ms']
        config
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

    def remove(self, path: Union[str, List[str]]):
        """Remove a config key.

        Parameters
        ----------
        path
            For example 'macros.keystroke_sleep_ms'
            or ['macros', 'keystroke_sleep_ms']
        """

        def callback(parent, child, chunk):
            if child is not None:
                del parent[chunk]

        self._resolve(path, callback)

    def set(self, path: Union[str, List[str]], value: Any):
        """Set a config key.

        Parameters
        ----------
        path
            For example 'macros.keystroke_sleep_ms'
            or ['macros', 'keystroke_sleep_ms']
        """
        logger.info('Changing "%s" to "%s" in %s', path, value, self.__class__.__name__)

        def callback(parent, child, chunk):
            parent[chunk] = value

        self._resolve(path, callback)

    def get(self, path: Union[str, List[str]], log_unknown: bool = True):
        """Get a config value. If not set, return the default

        Parameters
        ----------
        path
            For example 'macros.keystroke_sleep_ms'
        log_unknown
            If True, write an error if `path` does not exist in the config
        """

        def callback(parent, child, chunk):
            return child

        resolved = self._resolve(path, callback)
        if resolved is None:
            # don't create new empty stuff in INITIAL_CONFIG with _resolve
            initial_copy = copy.deepcopy(self.defaults)
            resolved = self._resolve(path, callback, initial_copy)

        if resolved is None and log_unknown:
            logger.error('Unknown config key "%s"', path)

        # modifications are only allowed via set
        return copy.deepcopy(resolved)

    def clear_config(self):
        """Remove all configurations in memory."""
        self._config = {}
