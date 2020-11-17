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
MAX_KEYCODE = 255
MIN_KEYCODE = 8


def get_input_keycode(keycode):
    """Same as get_output_keycode, but vice versa."""
    return keycode - MIN_KEYCODE


def get_target_keycode(character):
    # see if any modifiers are inside
    if 'shift' in character.lower():
        # yes, now try to return what a normal keyboard would have for that
        # (for shift it would usually be 50)
        system_keycode = system_mapping.find_keycode(character)
        if custom_mapping.get_character(system_mapping) is not None:
            # already taken!


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
        return iter(sorted(self._mapping.items()))

    def __len__(self):
        return len(self._mapping)

    def find_keycode(self, character, case=False):
        """For a given character, find the used keycode in the mapping."""
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

    def change(self, previous_keycode, new_keycode, character):
        """Replace the mapping of a keycode with a different one.

        Return True on success.

        Parameters
        ----------
        previous_keycode : int or None
            If None, will not remove any previous mapping.
        new_keycode : int
            The source keycode, what the mouse would report without any
            modification.
        character : string or string[]
            If an array of strings, will put something like { [ a, A ] };
            into the symbols file.
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
            target_keycode = get_target_keycode(character)

            self._mapping[new_keycode] = (target_keycode, str(character))
            if new_keycode != previous_keycode:
                # clear previous mapping of that code, because the line
                # representing that one will now represent a different one.
                self.clear(previous_keycode)
            self.changed = True
            return True

        return False

    def write_from_keymapper_symbols(self, keycode, character):
        """Write something from a key-mapper symbols file into the mapping."""
        keycode = int(keycode)
        if keycode <= 255:
            logger.error(
                'Expected keycodes in key-mapper symbols to be > 255 ',
                f'but got {keycode} for "{character}"'
            )
        self._mapping[get_input_keycode(keycode)] = (keycode, character)

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


# one mapping object for the whole application that holds all
# customizations
custom_mapping = Mapping()

# one mapping that represents the xmodmap output
system_mapping = Mapping()
