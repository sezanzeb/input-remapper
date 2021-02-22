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


"""A button or a key combination."""


import itertools

from evdev import ecodes


def verify(key):
    """Check if the key is an int 3-tuple of type, code, value"""
    if not isinstance(key, tuple) or len(key) != 3:
        raise ValueError(f'Expected key to be a 3-tuple, but got {key}')
    if sum([not isinstance(value, int) for value in key]) != 0:
        raise ValueError(f'Can only use integers, but got {key}')


# having shift in combinations modifies the configured output,
# ctrl might not work at all
DIFFICULT_COMBINATIONS = [
    ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHTSHIFT,
    ecodes.KEY_LEFTCTRL, ecodes.KEY_RIGHTCTRL,
    ecodes.KEY_LEFTALT, ecodes.KEY_RIGHTALT
]


class Key:
    """Represents one or more pressed down keys.

    Can be used in hashmaps/dicts as key
    """
    def __init__(self, *keys):
        """
        Parameters
        ----------
        Takes an arbitrary number of tuples as arguments. Each one should
        be in the format of
            0: type, one of evdev.events, taken from the original source
            event. Everything will be mapped to EV_KEY.
            1: The source keycode, what the mouse would report without any
            modification.
            2. The value. 1 (down), 0 (up) or any
            other value that the device reports. Gamepads use a continuous
            space of values for joysticks and triggers.

        or Key objects, which will flatten all of them into one combination
        """
        if len(keys) == 0:
            raise ValueError('At least one key is required')

        if isinstance(keys[0], int):
            # type, code, value was provided instead of a tuple
            keys = (keys,)

        # multiple objects of Key get flattened into one tuple
        flattened = ()
        for key in keys:
            if isinstance(key, Key):
                flattened += key.keys  # pylint: disable=no-member
            else:
                flattened += (key,)
        keys = flattened

        for key in keys:
            verify(key)

        self.keys = tuple(keys)
        self.release = (*self.keys[-1][:2], 0)

    def __iter__(self):
        return iter(self.keys)

    def __getitem__(self, item):
        return self.keys[item]

    def __len__(self):
        """Get the number of pressed down kes."""
        return len(self.keys)

    def __str__(self):
        return f'Key{str(self.keys)}'

    def __repr__(self):
        # used in the AssertionError output of tests
        return self.__str__()

    def __hash__(self):
        if len(self.keys) == 1:
            return hash(self.keys[0])

        return hash(self.keys)

    def __eq__(self, other):
        if isinstance(other, tuple):
            if isinstance(other[0], tuple):
                # a combination ((1, 5, 1), (1, 3, 1))
                return self.keys == other

            # otherwise, self needs to represent a single key as well
            return len(self.keys) == 1 and self.keys[0] == other

        if not isinstance(other, Key):
            return False

        # compare two instances of Key
        return self.keys == other.keys

    def is_problematic(self):
        """Is this combination going to work properly on all systems?"""
        if len(self.keys) <= 1:
            return False

        for sub_key in self.keys:
            if sub_key[0] != ecodes.EV_KEY:
                continue

            if sub_key[1] in DIFFICULT_COMBINATIONS:
                return True

        return False

    def get_permutations(self):
        """Get a list of Key objects representing all possible permutations.

        combining a + b + c should have the same result as b + a + c.
        Only the last key remains the same in the returned result.
        """
        if len(self.keys) <= 2:
            return [self]

        permutations = []
        for permutation in itertools.permutations(self.keys[:-1]):
            permutations.append(Key(*permutation, self.keys[-1]))

        return permutations
