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
"""Make the systems/environments mapping of keys and codes accessible."""

import json
import re
import subprocess
from typing import Optional, List, Iterable, Tuple

import evdev

from inputremapper.configs.paths import get_config_path, touch
from inputremapper.logger import logger
from inputremapper.utils import is_service

DISABLE_NAME = "disable"

DISABLE_CODE = -1

# xkb uses keycodes that are 8 higher than those from evdev
XKB_KEYCODE_OFFSET = 8

XMODMAP_FILENAME = "xmodmap.json"

LAZY_LOAD = None

_LAZY_LOADED_ATTRIBUTES = ["_mapping", "_xmodmap", "_case_insensitive_mapping"]


class SystemMapping:
    """Stores information about all available keycodes."""

    _mapping: Optional[dict] = LAZY_LOAD
    _xmodmap: Optional[List[Tuple[str, str]]] = LAZY_LOAD
    _case_insensitive_mapping: Optional[dict] = LAZY_LOAD

    def __getattribute__(self, wanted: str):
        """To lazy load system_mapping info only when needed.

        For example, this helps to keep logs of input-remapper-control clear when it
        doesn't need it the information.
        """
        lazy_loaded_attributes = ["_mapping", "_xmodmap", "_case_insensitive_mapping"]
        for lazy_loaded_attribute in lazy_loaded_attributes:
            if wanted != lazy_loaded_attribute:
                continue

            if object.__getattribute__(self, lazy_loaded_attribute) is LAZY_LOAD:
                # initialize _mapping and such with an empty dict, for populate
                # to write into
                object.__setattr__(self, lazy_loaded_attribute, {})
                object.__getattribute__(self, "populate")()

        return object.__getattribute__(self, wanted)

    def list_names(self, codes: Optional[Iterable[int]] = None) -> List[str]:
        """Get all possible names in the mapping, optionally filtered by codes.

        Parameters
        ----------
        codes: list of event codes
        """
        if not codes:
            return self._mapping.keys()

        return [name for name, code in self._mapping.items() if code in codes]

    def correct_case(self, symbol: str):
        """Return the correct casing for a symbol."""
        if symbol in self._mapping:
            return symbol
        # only if not e.g. both "a" and "A" are in the mapping
        return self._case_insensitive_mapping.get(symbol.lower(), symbol)

    def _use_xmodmap_symbols(self):
        """Look up xmodmap -pke, write xmodmap.json, and get the symbols."""
        try:
            xmodmap = subprocess.check_output(
                ["xmodmap", "-pke"],
                stderr=subprocess.STDOUT,
            ).decode()
        except FileNotFoundError:
            logger.info("Optional `xmodmap` command not found. This is not critical.")
            return
        except subprocess.CalledProcessError as e:
            logger.error('Call to `xmodmap -pke` failed with "%s"', e)
            return

        self._xmodmap = re.findall(r"(\d+) = (.+)\n", xmodmap + "\n")
        xmodmap_dict = self._find_legit_mappings()
        if len(xmodmap_dict) == 0:
            logger.info("`xmodmap -pke` did not yield any symbol")
            return

        # Write this stuff into the input-remapper config directory, because
        # the systemd service won't know the user sessions xmodmap.
        path = get_config_path(XMODMAP_FILENAME)
        touch(path)
        with open(path, "w") as file:
            logger.debug('Writing "%s"', path)
            json.dump(xmodmap_dict, file, indent=4)

        for name, code in xmodmap_dict.items():
            self._set(name, code)

    def _use_linux_evdev_symbols(self):
        """Look up the evdev constant names and use them."""
        for name, ecode in evdev.ecodes.ecodes.items():
            if name.startswith("KEY") or name.startswith("BTN"):
                self._set(name, ecode)

    def populate(self):
        """Get a mapping of all available names to their keycodes."""
        logger.debug("Gathering available keycodes")
        self.clear()

        if not is_service():
            # xmodmap is only available from within the login session.
            # The service that runs via systemd can't use this.
            self._use_xmodmap_symbols()

        self._use_linux_evdev_symbols()

        self._set(DISABLE_NAME, DISABLE_CODE)

    def update(self, mapping: dict):
        """Update this with new keys.

        Parameters
        ----------
        mapping
            maps from name to code. Make sure your keys are lowercase.
        """
        len_before = len(self._mapping)
        for name, code in mapping.items():
            self._set(name, code)

        logger.debug(
            "Updated keycodes with %d new ones", len(self._mapping) - len_before
        )

    def _set(self, name: str, code: int):
        """Map name to code."""
        self._mapping[str(name)] = code
        self._case_insensitive_mapping[str(name).lower()] = name

    def get(self, name: str) -> int:
        """Return the code mapped to the key."""
        # the correct casing should be shown when asking the system_mapping
        # for stuff. indexing case insensitive to support old presets.
        if name not in self._mapping:
            # only if not e.g. both "a" and "A" are in the mapping
            name = self._case_insensitive_mapping.get(str(name).lower())

        return self._mapping.get(name)

    def clear(self):
        """Remove all mapped keys. Only needed for tests."""
        keys = list(self._mapping.keys())
        for key in keys:
            del self._mapping[key]

    def get_name(self, code: int):
        """Get the first matching name for the code."""
        for entry in self._xmodmap:
            if int(entry[0]) - XKB_KEYCODE_OFFSET == code:
                return entry[1].split()[0]

        return None

    def _find_legit_mappings(self) -> dict:
        """From the parsed xmodmap list find usable symbols and their codes."""
        xmodmap_dict = {}
        for keycode, names in self._xmodmap:
            # there might be multiple, like:
            # keycode  64 = Alt_L Meta_L Alt_L Meta_L
            # keycode 204 = NoSymbol Alt_L NoSymbol Alt_L
            # Alt_L should map to code 64. Writing code 204 only works
            # if a modifier is applied at the same time. So take the first
            # one.
            name = names.split()[0]
            xmodmap_dict[name] = int(keycode) - XKB_KEYCODE_OFFSET

        return xmodmap_dict


# this mapping represents the xmodmap output, which stays constant
system_mapping = SystemMapping()
