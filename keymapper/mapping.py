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
import itertools
import copy

from keymapper.logger import logger
from keymapper.paths import touch
from keymapper.config import ConfigBase, config


def verify_key(key):
    """Check if the key describes a tuple or tuples of (type, code, value).

    For combinations it could be e.g. ((1, 2, 1), (1, 3, 1)).
    """
    if not isinstance(key, tuple):
        raise ValueError(f'Expected keys to be a 3-tuple, but got {key}')

    if isinstance(key[0], tuple):
        for sub_key in key:
            verify_key(sub_key)
    else:
        if len(key) != 3:
            raise ValueError(f'Expected key to be a 3-tuple, but got {key}')
        if sum([not isinstance(value, int) for value in key]) != 0:
            raise ValueError(f'Can only use numbers, but got {key}')


def split_key(key):
    """Take a key like "1,2,3" and return a 3-tuple of ints."""
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
        self._mapping = {}
        self.changed = False
        super().__init__(fallback=config)

    def __iter__(self):
        """Iterate over tuples of unique keycodes and their character."""
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
        new_key : int, int, int
            the new key. (type, code, value). key as in hashmap-key

            0: type, one of evdev.events, taken from the original source
            event. Everything will be mapped to EV_KEY.
            1: The source keycode, what the mouse would report without any
            modification.
            2. The value. 1 (down), 2 (up) or any
            other value that the device reports. Gamepads use a continuous
            space of values for joysticks and triggers.
        character : string
            A single character known to xkb or linux.
            Examples: KP_1, Shift_L, a, B, BTN_LEFT.
        previous_key : int, int, int
            the previous key, same format as new_key

            If not set, will not remove any previous mapping. If you recently
            used (1, 10, 1) for new_key and want to overwrite that with
            (1, 11, 1), provide (1, 5, 1) here.
        """
        if character is None:
            raise ValueError('Expected `character` not to be None')

        verify_key(new_key)
        if previous_key:
            verify_key(previous_key)

        logger.debug(
            '%s will map to %s, replacing %s',
            new_key, character, previous_key
        )
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
        key : int, int, int
            keycode : int
            ev_type : int
                one of evdev.events. codes may be the same for various
                event types.
            value : int
                event value. Usually you want 1 (down)
        """
        verify_key(key)

        if isinstance(key[0], tuple):
            for permutation in itertools.permutations(key[:-1]):
                permutation += (key[-1],)
                if permutation in self._mapping:
                    logger.debug('%s will be cleared', permutation)
                    del self._mapping[permutation]
            return

        if self._mapping.get(key) is not None:
            logger.debug('%s will be cleared', key)
            del self._mapping[key]
            self.changed = True
            return

        logger.error('Unknown key %s', key)

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
                logger.error('Invalid preset config at "%s"', path)
                return

            for key, character in preset_dict['mapping'].items():
                if '+' in key:
                    chunks = key.split('+')
                    key = tuple([split_key(chunk) for chunk in chunks])
                    if None in key:
                        continue
                else:
                    key = split_key(key)
                    if key is None:
                        continue

                logger.spam('%s maps to %s', key, character)
                self._mapping[key] = character

            # add any metadata of the mapping
            for key in preset_dict:
                if key == 'mapping':
                    continue
                self._config[key] = preset_dict[key]

        self.changed = False

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
                    '"mapping" is reserved and cannot be used as config key'
                )
            preset_dict = self._config

            # make sure to keep the option to add metadata if ever needed,
            # so put the mapping into a special key
            json_ready_mapping = {}
            # tuple keys are not possible in json, encode them as string
            for key, value in self._mapping.items():
                if isinstance(key[0], tuple):
                    # combinations to "1,2,1+1,3,1"
                    new_key = '+'.join([
                        ','.join([
                            str(value)
                            for value in sub_key
                        ])
                        for sub_key in key
                    ])
                else:
                    new_key = ','.join([str(value) for value in key])
                json_ready_mapping[new_key] = value

            preset_dict['mapping'] = json_ready_mapping
            json.dump(preset_dict, file, indent=4)
            file.write('\n')

        self.changed = False

    def get_character(self, key):
        """Read the character that is mapped to this keycode.

        Parameters
        ----------
        key : int, int, int
            keycode : int
            ev_type : int
                one of evdev.events. codes may be the same for various
                event types.
            value : int
                event value. Usually you want 1 (down)

            Or a tuple of multiple of those. Checks any possible permutation
            with the last key being always at the end, to work well with
            combinations.
        """
        if isinstance(key[0], tuple):
            for permutation in itertools.permutations(key[:-1]):
                permutation += (key[-1],)
                existing = self._mapping.get(permutation)
                if existing is not None:
                    return existing

        return self._mapping.get(key)
