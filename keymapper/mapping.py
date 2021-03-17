#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@sezanzeb.de>
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
from keymapper.paths import touch
from keymapper.config import ConfigBase, config
from keymapper.key import Key


DISABLE_NAME = 'disable'

DISABLE_CODE = -1


def split_key(key):
    """Take a key like "1,2,3" and return a 3-tuple of ints."""
    key = key.strip()

    if ',' not in key:
        logger.error('Found invalid key: "%s"', key)
        return None

    if key.count(',') == 1:
        # support for legacy mapping objects that didn't include
        # the value in the key
        ev_type, code = key.split(',')
        value = 1
    elif key.count(',') == 2:
        ev_type, code, value = key.split(',')
    else:
        logger.error('Found more than two commas in the key: "%s"', key)
        return None

    try:
        key = (int(ev_type), int(code), int(value))
    except ValueError:
        logger.error('Found non-int in: "%s"', key)
        return None

    return key


class Mapping(ConfigBase):
    """Contains and manages mappings and config of a single preset."""
    def __init__(self):
        self._mapping = {}  # a mapping of Key objects to strings
        self.changed = False

        # are there actually any keys set in the mapping file?
        self.num_saved_keys = 0

        super().__init__(fallback=config)

    def __iter__(self):
        """Iterate over Key objects and their character."""
        return iter(self._mapping.items())

    def __len__(self):
        return len(self._mapping)

    def set(self, *args):
        """Set a config value. See `ConfigBase.set`."""
        self.changed = True
        return super().set(*args)

    def remove(self, *args):
        """Remove a config value. See `ConfigBase.remove`."""
        self.changed = True
        return super().remove(*args)

    def change(self, new_key, character, previous_key=None):
        """Replace the mapping of a keycode with a different one.

        Parameters
        ----------
        new_key : Key
        character : string
            A single character known to xkb or linux.
            Examples: KP_1, Shift_L, a, B, BTN_LEFT.
        previous_key : Key or None
            the previous key

            If not set, will not remove any previous mapping. If you recently
            used (1, 10, 1) for new_key and want to overwrite that with
            (1, 11, 1), provide (1, 10, 1) here.
        """
        if not isinstance(new_key, Key):
            raise TypeError(f'Expected {new_key} to be a Key object')

        if character is None:
            raise ValueError('Expected `character` not to be None')

        character = character.strip()
        logger.debug('%s will map to "%s"', new_key, character)
        self.clear(new_key)  # this also clears all equivalent keys
        self._mapping[new_key] = character

        if previous_key is not None:
            code_changed = new_key != previous_key
            if code_changed:
                # clear previous mapping of that code, because the line
                # representing that one will now represent a different one
                self.clear(previous_key)

        self.changed = True

    def clear(self, key):
        """Remove a keycode from the mapping.

        Parameters
        ----------
        key : Key
        """
        if not isinstance(key, Key):
            raise TypeError('Expected key to be a Key object')

        for permutation in key.get_permutations():
            if permutation in self._mapping:
                logger.debug('%s will be cleared', permutation)
                del self._mapping[permutation]
                self.changed = True
                # there should be only one variation of the permutations
                # in the mapping actually

    def empty(self):
        """Remove all mappings."""
        self._mapping = {}
        self.changed = True

    def load(self, path):
        """Load a dumped JSON from home to overwrite the mappings.

        Parameters
        path : string
            Path of the preset file
        """
        logger.info('Loading preset from "%s"', path)

        if not os.path.exists(path):
            raise FileNotFoundError(
                f'Tried to load non-existing preset "{path}"'
            )

        self.clear_config()

        with open(path, 'r') as file:
            preset_dict = json.load(file)

            if not isinstance(preset_dict.get('mapping'), dict):
                logger.error(
                    'Expected mapping to be a dict, but was %s. '
                    'Invalid preset config at "%s"',
                    preset_dict.get('mapping'), path
                )
                return

            for key, character in preset_dict['mapping'].items():
                try:
                    key = Key(*[
                        split_key(chunk) for chunk in key.split('+')
                        if chunk.strip() != ''
                    ])
                except ValueError as error:
                    logger.error(str(error))
                    continue

                if None in key:
                    continue

                logger.spam('%s maps to %s', key, character)
                self._mapping[key] = character

            # add any metadata of the mapping
            for key in preset_dict:
                if key == 'mapping':
                    continue
                self._config[key] = preset_dict[key]

        self.changed = False
        self.num_saved_keys = len(self)

    def clone(self):
        """Create a copy of the mapping."""
        mapping = Mapping()
        mapping._mapping = copy.deepcopy(self._mapping)
        mapping.changed = self.changed
        return mapping

    def save(self, path):
        """Dump as JSON into home."""
        logger.info('Saving preset to %s', path)

        touch(path)

        with open(path, 'w') as file:
            if self._config.get('mapping') is not None:
                logger.error(
                    '"mapping" is reserved and cannot be used as config '
                    'key: %s',
                    self._config.get('mapping')
                )

            preset_dict = self._config.copy()  # shallow copy

            # make sure to keep the option to add metadata if ever needed,
            # so put the mapping into a special key
            json_ready_mapping = {}
            # tuple keys are not possible in json, encode them as string
            for key, value in self._mapping.items():
                new_key = '+'.join([
                    ','.join([
                        str(value)
                        for value in sub_key
                    ])
                    for sub_key in key
                ])
                json_ready_mapping[new_key] = value

            preset_dict['mapping'] = json_ready_mapping
            json.dump(preset_dict, file, indent=4)
            file.write('\n')

        self.changed = False
        self.num_saved_keys = len(self)

    def get_character(self, key):
        """Read the character that is mapped to this keycode.

        Parameters
        ----------
        key : Key or InputEvent
            If an InputEvent, will test if that event is mapped
            and take the sign of the value.
        """
        if not isinstance(key, Key):
            raise TypeError('Expected key to be a Key object')

        for permutation in key.get_permutations():
            existing = self._mapping.get(permutation)
            if existing is not None:
                return existing

        return None
