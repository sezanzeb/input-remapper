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


class Mapping:
    """Contains and manages mappings.

    The keycode is always unique, multiple keycodes may map to the same
    character.
    """
    def __init__(self):
        self._mapping = {}

        self.changed = False

        self.config = {}

    def __iter__(self):
        """Iterate over tuples of unique keycodes and their character."""
        return iter(sorted(self._mapping.items()))

    def __len__(self):
        return len(self._mapping)

    def change(self, new, character, previous=(None, None)):
        """Replace the mapping of a keycode with a different one.

        Return True on success.

        Parameters
        ----------
        new : int, int
            0: type, one of evdev.events, taken from the original source
            event. Everything will be mapped to EV_KEY.
            1: The source keycode, what the mouse would report without any
            modification.
        character : string or string[]
            A single character known to xkb or linux.
            Examples: KP_1, Shift_L, a, B, BTN_LEFT.
        previous : int, int
            If None, will not remove any previous mapping. If you recently
            used 10 for new_keycode and want to overwrite that with 11,
            provide 5 here.
        """
        new_type, new_keycode = new
        prev_type, prev_keycode = previous

        # either both of them are None, or both integers
        if prev_keycode is None and prev_keycode != prev_type:
            logger.error('Got (%s, %s) for previous', prev_type, prev_keycode)
        if new_keycode is None and prev_keycode != new_type:
            logger.error('Got (%s, %s) for new', new_type, new_keycode)

        try:
            new_keycode = int(new_keycode)
            new_type = int(new_type)
            if prev_keycode is not None:
                prev_keycode = int(prev_keycode)
            if prev_type is not None:
                prev_type = int(prev_type)
        except (TypeError, ValueError):
            logger.error('Can only use numbers in the tuples')
            return False

        if new_keycode and character:
            logger.debug(
                'type:%s, code:%s will map to %s, replacing type:%s, code:%s',
                new_type, new_keycode, character, prev_type, prev_keycode
            )
            self._mapping[(new_type, new_keycode)] = character
            code_changed = new_keycode != prev_keycode
            if code_changed and prev_keycode is not None:
                # clear previous mapping of that code, because the line
                # representing that one will now represent a different one.
                self.clear(prev_type, prev_keycode)
            self.changed = True
            return True

        return False

    def clear(self, ev_type, keycode):
        """Remove a keycode from the mapping.

        Parameters
        ----------
        keycode : int
        ev_type : int
            one of evdev.events
        """
        assert keycode is not None
        assert ev_type is not None
        assert isinstance(ev_type, int)
        assert isinstance(keycode, int)

        if self._mapping.get((ev_type, keycode)) is not None:
            logger.debug(
                'type:%s, code:%s will be cleared',
                ev_type, keycode
            )
            del self._mapping[(ev_type, keycode)]
            self.changed = True

    def empty(self):
        """Remove all mappings."""
        self._mapping = {}
        self.changed = True

    def load(self, device, preset):
        """Load a dumped JSON from home to overwrite the mappings."""
        path = get_config_path(device, preset)
        logger.info('Loading preset from "%s"', path)

        if not os.path.exists(path):
            logger.error('Tried to load non-existing preset "%s"', path)
            return

        with open(path, 'r') as file:
            preset_dict = json.load(file)
            if preset_dict.get('mapping') is None:
                logger.error('Invalid preset config at "%s"', path)
                return

            for key, character in preset_dict['mapping'].items():
                if ',' not in key:
                    logger.error('Found invalid key: "%s"', key)
                    continue

                ev_type, keycode = key.split(',')
                try:
                    keycode = int(keycode)
                except ValueError:
                    logger.error('Found non-int keycode: "%s"', keycode)
                    continue
                try:
                    ev_type = int(ev_type)
                except ValueError:
                    logger.error('Found non-int ev_type: "%s"', ev_type)
                    continue
                self._mapping[(ev_type, keycode)] = character

            # add any metadata of the mapping
            for key in preset_dict:
                if key == 'mapping':
                    continue
                self.config[key] = preset_dict[key]

        self.changed = False

    def clone(self):
        """Create a copy of the mapping."""
        mapping = Mapping()
        mapping._mapping = copy.deepcopy(self._mapping)
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
            json_ready_mapping = {}
            # tuple keys are not possible in json
            for key, value in self._mapping.items():
                new_key = f'{key[0]},{key[1]}'
                json_ready_mapping[new_key] = value

            preset_dict = {'mapping': json_ready_mapping}
            preset_dict.update(self.config)
            json.dump(preset_dict, file, indent=4)
            file.write('\n')

        self.changed = False

    def get_character(self, ev_type, keycode):
        """Read the character that is mapped to this keycode.

        Parameters
        ----------
        keycode : int
        ev_type : int
            one of evdev.events. codes may be the same for various
            event types.
        """
        return self._mapping.get((ev_type, keycode))
