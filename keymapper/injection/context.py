#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@hip70890b.de>
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


"""Stores injection-process wide information."""


from keymapper.logger import logger
from keymapper.injection.macros import parse, is_this_a_macro
from keymapper.state import system_mapping
from keymapper.config import NONE, MOUSE, WHEEL


class Context:
    """Stores injection-process wide information.

    In some ways this is a wrapper for the mapping that derives some
    information that is specifically important to the injection.

    One Context exists for each injection process, which is shared
    with all coroutines and used objects.

    Benefits of the context:
    - less redundant passing around of parameters
    - easier to add new process wide information without having to adjust
      all function calls in unittests
    - makes the injection class shorter and more specific to a certain task,
      which is actually spinning up the injection.

    Members
    -------
    mapping : Mapping
        the mapping that is the source of key_to_code and macros,
        only used to query config values.
    key_to_code : dict
        mapping of ((type, code, value),) to linux-keycode
        or multiple of those like ((...), (...), ...) for combinations
        combinations need to be present in every possible valid ordering.
        e.g. shift + alt + a and alt + shift + a.
        This is needed to query keycodes more efficiently without having
        to search mapping each time.
    macros : dict
        mapping of ((type, code, value),) to _Macro objects.
        Combinations work similar as in key_to_code
    """
    def __init__(self, mapping):
        self.mapping = mapping

        # avoid searching through the mapping at runtime,
        # might be a bit expensive
        self.key_to_code = self._map_keys_to_codes()
        self.macros = self._parse_macros()
        self.left_purpose = None
        self.right_purpose = None
        self.update_purposes()

    def update_purposes(self):
        """Read joystick purposes from the configuration."""
        self.left_purpose = self.mapping.get('gamepad.joystick.left_purpose')
        self.right_purpose = self.mapping.get('gamepad.joystick.right_purpose')

    def _parse_macros(self):
        """To quickly get the target macro during operation."""
        logger.debug('Parsing macros')
        macros = {}
        for key, output in self.mapping:
            if is_this_a_macro(output):
                macro = parse(output, self.mapping)
                if macro is None:
                    continue

                for permutation in key.get_permutations():
                    macros[permutation.keys] = macro

        if len(macros) == 0:
            logger.debug('No macros configured')

        return macros

    def _map_keys_to_codes(self):
        """To quickly get target keycodes during operation.

        Returns a mapping of one or more 3-tuples to ints.
        Examples:
            ((1, 2, 1),): 3
            ((1, 5, 1), (1, 4, 1)): 4
        """
        key_to_code = {}
        for key, output in self.mapping:
            if is_this_a_macro(output):
                continue

            target_code = system_mapping.get(output)
            if target_code is None:
                logger.error('Don\'t know what %s is', output)
                continue

            for permutation in key.get_permutations():
                if permutation.keys[-1][-1] not in [-1, 1]:
                    logger.error(
                        'Expected values to be -1 or 1 at this point: %s',
                        permutation.keys
                    )
                key_to_code[permutation.keys] = target_code

        return key_to_code

    def is_mapped(self, key):
        """Check if this key is used for macros or mappings.

        Parameters
        ----------
        key : ((int, int, int),)
            One or more 3-tuples of type, code, value
        """
        return key in self.macros or key in self.key_to_code

    def forwards_joystick(self):
        """If at least one of the joysticks remains a regular joystick."""
        return NONE in (self.left_purpose, self.right_purpose)

    def maps_joystick(self):
        """If at least one of the joysticks will serve a special purpose."""
        return (self.left_purpose, self.right_purpose) != (NONE, NONE)

    def joystick_as_mouse(self):
        """If at least one joystick maps to an EV_REL capability."""
        purposes = (self.left_purpose, self.right_purpose)
        return MOUSE in purposes or WHEEL in purposes

    def writes_keys(self):
        """Check if anything is being mapped to keys."""
        return len(self.macros) == 0 and len(self.key_to_code) == 0
