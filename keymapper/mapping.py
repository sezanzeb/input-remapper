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


from keymapper.logger import logger


# if MIN_KEYCODE < 255 and MAX_KEYCODE > 255: X crashes
# the maximum specified in /usr/share/X11/xkb/keycodes is usually 255
# and the minimum 8
MAX_KEYCODE = 255
MIN_KEYCODE = 8


# modes for change:
GENERATE = -1
DONTMAP = None


def get_input_keycode(keycode):
    """Same as get_output_keycode, but vice versa."""
    return keycode - MIN_KEYCODE


def get_target_keycode():
    # see HELP.md
    for keycode in range(MAX_KEYCODE, MIN_KEYCODE - 1, -1):
        # starting from the MAX_KEYCODE, find the first keycode that is
        # unused in both custom_mapping and system_mapping.
        if not (custom_mapping.has(keycode) or system_mapping.has(keycode)):
            return keycode

    # no unused keycode found, take the highest keycode that is unused
    # in the current custom_mapping.
    for keycode in range(MAX_KEYCODE, MIN_KEYCODE - 1, -1):
        # starting from the MAX_KEYCODE, find the first keycode that is
        # unused in both custom_mapping and system_mapping.
        if not (custom_mapping.has(keycode)):
            return keycode

    logger.error('All %s keycodes are mapped!', MAX_KEYCODE - MIN_KEYCODE)
    return None


class Mapping:
    """Contains and manages mappings.

    The keycode is always unique, multiple keycodes may map to the same
    character.
    """
    def __init__(self):
        # TODO this is a stupid data structure if there are two keys
        #  that should be unique individually. system_keycode and
        #  target_keycode. two _mapping objects maybe?
        self._mapping = {}
        self.changed = False

    def __iter__(self):
        """Iterate over tuples of unique keycodes and their character."""
        return iter(sorted(self._mapping.items()))

    def __len__(self):
        return len(self._mapping)

    def find_keycode(self, character, case=False):
        """For a given character, find the used keycodes in the mapping."""
        # TODO test
        if not case:
            character = character.lower()
        for keycode, (mapped_keycode, mapped_character) in self._mapping:
            # keycode is what the system would use for that key,
            # mapped_keycode is what we use instead by writing into /dev,
            # and mapped_character is what we expect to appear.
            # mapped_character might be multiple things, like "a, A"
            if not case:
                mapped_character = mapped_character.lower()
            if character in [c.strip() for c in mapped_character.split(',')]:
                return keycode, mapped_keycode

    def change(self, previous_keycode, new_keycode, character, target_keycode):
        """Replace the mapping of a keycode with a different one.

        Return True on success.

        Parameters
        ----------
        previous_keycode : int or None
            If None, will not remove any previous mapping. If you recently
            used 10 for new_keycode and want to overwrite that with 11,
            provide 5 here.
        new_keycode : int
            The source keycode, what the mouse would report without any
            modification.
        character : string or string[]
            If an array of strings, will put something like { [ a, A ] };
            into the symbols file.
        target_keycode : int or None
            Which keycode should be used for that key instead. If -1,
            will figure out a new one. This is for stuff that happens
            under the hood and the user won't see this unless they open
            config files. If None, will only map new_keycode to character
            without any in-between step.
        """
        try:
            new_keycode = int(new_keycode)
            if target_keycode is not None:
                target_keycode = int(target_keycode)
            if previous_keycode is not None:
                previous_keycode = int(previous_keycode)
        except ValueError:
            logger.error('Can only use numbers as keycodes')
            return False

        # TODO test
        if target_keycode == GENERATE:
            target_keycode = get_target_keycode()

        if new_keycode and character:
            self._mapping[new_keycode] = (target_keycode, str(character))
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

    def get_keycode(self, keycode):
        """Read the output keycode that is mapped to this input keycode."""
        return self._mapping.get(keycode, (None, None))[0]

    def get_character(self, keycode):
        """Read the character that is mapped to this keycode.

        Parameters
        ----------
        keycode : int
        """
        return self._mapping.get(keycode, (None, None))[1]

    def has(self, keycode):
        """Check if this keycode is going to be a line in the symbols file."""
        # TODO test
        if self._mapping.get(keycode) is not None:
            # the keycode that is disabled, because it is mapped to
            # something else
            return True

        for _, (target_keycode, _) in self._mapping.items():
            if target_keycode == keycode:
                # the keycode that is actually being mapped
                return True

        return False


# one mapping object for the whole application that holds all
# customizations
custom_mapping = Mapping()

# one mapping that represents the xmodmap output
system_mapping = Mapping()
