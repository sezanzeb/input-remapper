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


"""Contains and manages mappings."""


import os
import json
import copy

from keymapper.logger import logger
from keymapper.paths import get_config_path, touch


def keep_reverse_mapping_intact(func):
    """Decorator for Mapping.update_reverse_mapping."""
    def wrapper(self, *args, **kwargs):
        func(self, *args, **kwargs)
        self.update_reverse_mapping()
    return wrapper


class Mapping:
    """Contains and manages mappings.

    The keycode is always unique, multiple keycodes may map to the same
    character.
    """
    def __init__(self):
        self._mapping = {}

        # Maintain this second mapping in order to optimize get_keycode.
        # This mapping is not complete, since multiple keycodes can map
        # to the same character in _mapping which is not possible in
        # _reverse_mapping! It is based on _reverse_mapping and
        # reconstructed on changes.
        self._reverse_mapping = {}

        self.changed = False

    def __iter__(self):
        """Iterate over tuples of unique keycodes and their character."""
        return iter(sorted(self._mapping.items()))

    def __len__(self):
        return len(self._mapping)

    def update_reverse_mapping(self):
        """Generate a reverse mapping to optimize reverse lookups.

        If _mapping contains `20: "a, A"` (the xkb syntax for modified keys),
        reverse mapping will contain `"a": 20, "A": 20`.
        """
        self._reverse_mapping = {}
        for key, value in self._mapping.items():
            for character in value.split(','):
                self._reverse_mapping[character.strip()] = key

    @keep_reverse_mapping_intact
    def change(self, new_keycode, character, previous_keycode=None):
        """Replace the mapping of a keycode with a different one.

        Return True on success.

        Parameters
        ----------
        new_keycode : int
            The source keycode, what the mouse would report without any
            modification.
        character : string or string[]
            A single character known to xkb, Examples: KP_1, Shift_L, a, B.
            Can also be an array, which is used for reading the xkbmap output
            completely.
        previous_keycode : int or None
            If None, will not remove any previous mapping. If you recently
            used 10 for new_keycode and want to overwrite that with 11,
            provide 5 here.
        """
        try:
            new_keycode = int(new_keycode)
            if previous_keycode is not None:
                previous_keycode = int(previous_keycode)
        except ValueError:
            logger.error('Can only use numbers as keycodes')
            return False

        if new_keycode and character:
            self._mapping[new_keycode] = character
            if new_keycode != previous_keycode:
                # clear previous mapping of that code, because the line
                # representing that one will now represent a different one.
                self.clear(previous_keycode)
            self.changed = True
            return True

        return False

    @keep_reverse_mapping_intact
    def clear(self, keycode):
        """Remove a keycode from the mapping.

        Parameters
        ----------
        keycode : int
        """
        if self._mapping.get(keycode) is not None:
            del self._mapping[keycode]
            self.changed = True

    @keep_reverse_mapping_intact
    def empty(self):
        """Remove all mappings."""
        self._mapping = {}
        self.changed = True

    @keep_reverse_mapping_intact
    def load(self, device, preset):
        """Load a dumped JSON from home to overwrite the mappings."""
        path = get_config_path(device, preset)
        logger.info('Loading preset from "%s"', path)

        if not os.path.exists(path):
            logger.error('Tried to load non-existing preset "%s"', path)
            return

        with open(path, 'r') as file:
            mapping = json.load(file)
            if mapping.get('mapping') is None:
                logger.error('Invalid preset config at "%s"', path)
                return

            for keycode, character in mapping['mapping'].items():
                try:
                    keycode = int(keycode)
                except ValueError:
                    logger.error('Found non-int keycode: %s', keycode)
                    continue
                self._mapping[keycode] = character

        self.changed = False

    def clone(self):
        """Create a copy of the mapping."""
        mapping = Mapping()
        mapping._mapping = copy.deepcopy(self._mapping)
        mapping.update_reverse_mapping()
        mapping.changed = self.changed
        return mapping

    def save(self, device, preset):
        """Dump as JSON into home."""
        path = get_config_path(device, preset)
        logger.info('Saving preset to %s', path)

        touch(path)

        with open(path, 'w') as file:
            # make sure to keep the option to add metadata if ever needed,
            # so put the mapping into a special key
            json.dump({
                'mapping': self._mapping
            }, file, indent=4)
            file.write('\n')

        self.changed = False

    def get_keycode(self, character):
        """Get the keycode for that character.

        If multiple keycodes map to that character, an arbitrary one of
        those is returned.
        """
        return self._reverse_mapping.get(character)

    def get_character(self, keycode):
        """Read the character that is mapped to this keycode.

        Parameters
        ----------
        keycode : int
        """
        return self._mapping.get(keycode)
