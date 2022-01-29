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


"""A button or a key combination."""


import itertools

import evdev
from evdev import ecodes

from inputremapper.configs.system_mapping import system_mapping
from inputremapper.logger import logger


def verify(key):
    """Check if the key is an int 3-tuple of type, code, value"""
    if not isinstance(key, tuple) or len(key) != 3:
        raise ValueError(f"Expected key to be a 3-tuple, but got {key}")
    if sum([not isinstance(value, int) for value in key]) != 0:
        raise ValueError(f"Can only use integers, but got {key}")


# having shift in combinations modifies the configured output,
# ctrl might not work at all
DIFFICULT_COMBINATIONS = [
    ecodes.KEY_LEFTSHIFT,
    ecodes.KEY_RIGHTSHIFT,
    ecodes.KEY_LEFTCTRL,
    ecodes.KEY_RIGHTCTRL,
    ecodes.KEY_LEFTALT,
    ecodes.KEY_RIGHTALT,
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
            raise ValueError("At least one key is required")

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

    @classmethod
    def btn_left(cls):
        """Construct a Key object representing a left click on a mouse."""
        return cls(ecodes.EV_KEY, ecodes.BTN_LEFT, 1)

    def __iter__(self):
        return iter(self.keys)

    def __getitem__(self, item):
        return self.keys[item]

    def __len__(self):
        """Get the number of pressed down kes."""
        return len(self.keys)

    def __str__(self):
        return f"Key{str(self.keys)}"

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

    def beautify(self):
        """Get a human readable string representation."""
        result = []

        for sub_key in self:
            if isinstance(sub_key[0], tuple):
                raise Exception("deprecated stuff")

            ev_type, code, value = sub_key

            if ev_type not in evdev.ecodes.bytype:
                logger.error("Unknown key type for %s", sub_key)
                result.append(str(code))
                continue

            if code not in evdev.ecodes.bytype[ev_type]:
                logger.error("Unknown key code for %s", sub_key)
                result.append(str(code))
                continue

            key_name = None

            # first try to find the name in xmodmap to not display wrong
            # names due to the keyboard layout
            if ev_type == evdev.ecodes.EV_KEY:
                key_name = system_mapping.get_name(code)

            if key_name is None:
                # if no result, look in the linux key constants. On a german
                # keyboard for example z and y are switched, which will therefore
                # cause the wrong letter to be displayed.
                key_name = evdev.ecodes.bytype[ev_type][code]
                if isinstance(key_name, list):
                    key_name = key_name[0]

            if ev_type != evdev.ecodes.EV_KEY:
                direction = {
                    # D-Pad
                    (evdev.ecodes.ABS_HAT0X, -1): "Left",
                    (evdev.ecodes.ABS_HAT0X, 1): "Right",
                    (evdev.ecodes.ABS_HAT0Y, -1): "Up",
                    (evdev.ecodes.ABS_HAT0Y, 1): "Down",
                    (evdev.ecodes.ABS_HAT1X, -1): "Left",
                    (evdev.ecodes.ABS_HAT1X, 1): "Right",
                    (evdev.ecodes.ABS_HAT1Y, -1): "Up",
                    (evdev.ecodes.ABS_HAT1Y, 1): "Down",
                    (evdev.ecodes.ABS_HAT2X, -1): "Left",
                    (evdev.ecodes.ABS_HAT2X, 1): "Right",
                    (evdev.ecodes.ABS_HAT2Y, -1): "Up",
                    (evdev.ecodes.ABS_HAT2Y, 1): "Down",
                    # joystick
                    (evdev.ecodes.ABS_X, 1): "Right",
                    (evdev.ecodes.ABS_X, -1): "Left",
                    (evdev.ecodes.ABS_Y, 1): "Down",
                    (evdev.ecodes.ABS_Y, -1): "Up",
                    (evdev.ecodes.ABS_RX, 1): "Right",
                    (evdev.ecodes.ABS_RX, -1): "Left",
                    (evdev.ecodes.ABS_RY, 1): "Down",
                    (evdev.ecodes.ABS_RY, -1): "Up",
                    # wheel
                    (evdev.ecodes.REL_WHEEL, -1): "Down",
                    (evdev.ecodes.REL_WHEEL, 1): "Up",
                    (evdev.ecodes.REL_HWHEEL, -1): "Left",
                    (evdev.ecodes.REL_HWHEEL, 1): "Right",
                }.get((code, value))
                if direction is not None:
                    key_name += f" {direction}"

            key_name = key_name.replace("ABS_Z", "Trigger Left")
            key_name = key_name.replace("ABS_RZ", "Trigger Right")

            key_name = key_name.replace("ABS_HAT0X", "DPad")
            key_name = key_name.replace("ABS_HAT0Y", "DPad")
            key_name = key_name.replace("ABS_HAT1X", "DPad 2")
            key_name = key_name.replace("ABS_HAT1Y", "DPad 2")
            key_name = key_name.replace("ABS_HAT2X", "DPad 3")
            key_name = key_name.replace("ABS_HAT2Y", "DPad 3")

            key_name = key_name.replace("ABS_X", "Joystick")
            key_name = key_name.replace("ABS_Y", "Joystick")
            key_name = key_name.replace("ABS_RX", "Joystick 2")
            key_name = key_name.replace("ABS_RY", "Joystick 2")

            key_name = key_name.replace("BTN_", "Button ")
            key_name = key_name.replace("KEY_", "")

            key_name = key_name.replace("REL_", "")
            key_name = key_name.replace("HWHEEL", "Wheel")
            key_name = key_name.replace("WHEEL", "Wheel")

            key_name = key_name.replace("_", " ")
            key_name = key_name.replace("  ", " ")

            result.append(key_name)

        return " + ".join(result)
