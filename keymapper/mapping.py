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


"""TODO"""


import os
import re

from keymapper.paths import get_home_path
from keymapper.logger import logger


class Mapping:
    """Contains and manages mappings.

    The keycode is always unique, multiple keycodes may map to the same
    character.
    """
    def __init__(self):
        self._mapping = {}
        self.changed = False

    def __iter__(self):
        """Iterate over tuples of unique keycodes and their character."""
        return iter(self._mapping.items())

    def __len__(self):
        return len(self._mapping)

    def load(self, device, preset):
        """Parse the X config to replace the current mapping with that one."""
        # TODO put that logic out of the mapper to make mapper display server
        #   agnostic
        path = get_home_path(device, preset)

        if not os.path.exists(path):
            logger.debug(
                'Tried to load non existing preset "%s" for %s',
                preset, device
            )
            self._mapping = {}
            return

        with open(path, 'r') as f:
            # from "key <12> { [ 1 ] };" extract 12 and 1,
            # avoid lines that start with special characters
            # (might be comments)
            result = re.findall(r'\n\s+?key <(.+?)>.+?\[\s+(\w+)', f.read())
            logger.debug('Found %d mappings in this preset', len(result))
            self._mapping = {
                int(keycode): character
                for keycode, character
                in result
            }

        self.changed = False

    def change(self, previous_keycode, new_keycode, character):
        """Replace the mapping of a keycode with a different one.

        Return True on success.

        Parameters
        ----------
        previous_keycode : int or None
            If None, will not remove any previous mapping.
        new_keycode : int
        character : string
        """
        try:
            new_keycode = int(new_keycode)
        except ValueError:
            logger.error('Cannot use %s as keycode', new_keycode)
            return False

        if previous_keycode is not None:
            try:
                previous_keycode = int(previous_keycode)
            except ValueError:
                logger.error('Cannot use %s as keycode', previous_keycode)
                return False

        if new_keycode and character:
            self._mapping[new_keycode] = str(character)
            if new_keycode != previous_keycode:
                # clear previous mapping of that code, because the line
                # representing that one will now represent a different one.
                self.clear(previous_keycode)
            self.changed = True
            return True

        return False

    def clear(self, keycode):
        """Remove a keycode from the mapping.

        Parameters
        ----------
        keycode : int
        """
        if self._mapping.get(keycode) is not None:
            del self._mapping[keycode]
            self.changed = True

    def empty(self):
        """Remove all mappings."""
        self._mapping = {}
        self.changed = True

    def get(self, keycode):
        """Read the character that is mapped to this keycode.

        Parameters
        ----------
        keycode : int
        """
        return self._mapping.get(keycode)


# one mapping object for the whole application
mapping = Mapping()
