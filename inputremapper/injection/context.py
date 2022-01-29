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


"""Stores injection-process wide information."""

from inputremapper.logger import logger
from inputremapper.injection.macros.parse import parse, is_this_a_macro
from inputremapper.configs.system_mapping import system_mapping
from inputremapper.configs.global_config import NONE, MOUSE, WHEEL, BUTTONS


class Context:
    """Stores injection-process wide information.

    In some ways this is a wrapper for the preset that derives some
    information that is specifically important to the injection.

    The information in the context does not change during the injection.

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
    preset : Preset
        The preset that is the source of key_to_code and macros,
        only used to query config values.
    key_to_code : dict
        Preset of ((type, code, value),) to linux-keycode
        or multiple of those like ((...), (...), ...) for combinations.
        Combinations need to be present in every possible valid ordering.
        e.g. shift + alt + a and alt + shift + a.
        This is needed to query keycodes more efficiently without having
        to search preset each time.
    macros : dict
        Preset of ((type, code, value),) to Macro objects.
        Combinations work similar as in key_to_code
    """

    def __init__(self, preset):
        self.preset = preset

        # avoid searching through the mapping at runtime,
        # might be a bit expensive
        self.key_to_code = self._map_keys_to_codes()
        self.macros = self._parse_macros()

        self.left_purpose = None
        self.right_purpose = None
        self.update_purposes()

    def update_purposes(self):
        """Read joystick purposes from the configuration.

        For efficiency, so that the config doesn't have to be read during
        runtime repeatedly.
        """
        self.left_purpose = self.preset.get("gamepad.joystick.left_purpose")
        self.right_purpose = self.preset.get("gamepad.joystick.right_purpose")

    def _parse_macros(self):
        """To quickly get the target macro during operation."""
        logger.debug("Parsing macros")
        macros = {}
        for key, output in self.preset:
            if is_this_a_macro(output[0]):
                macro = parse(output[0], self)
                if macro is None:
                    continue

                for permutation in key.get_permutations():
                    macros[permutation.keys] = (macro, output[1])

        if len(macros) == 0:
            logger.debug("No macros configured")

        return macros

    def _map_keys_to_codes(self):
        """To quickly get target keycodes during operation.

        Returns a mapping of one or more 3-tuples to 2-tuples of (int, target_uinput).
        Examples:
            ((1, 2, 1),): (3, "keyboard")
            ((1, 5, 1), (1, 4, 1)): (4, "gamepad")
        """
        key_to_code = {}
        for key, output in self.preset:
            if is_this_a_macro(output[0]):
                continue

            target_code = system_mapping.get(output[0])
            if target_code is None:
                logger.error('Don\'t know what "%s" is', output[0])
                continue

            for permutation in key.get_permutations():
                if permutation.keys[-1][-1] not in [-1, 1]:
                    logger.error(
                        "Expected values to be -1 or 1 at this point: %s",
                        permutation.keys,
                    )
                key_to_code[permutation.keys] = (target_code, output[1])

        return key_to_code

    def is_mapped(self, combination):
        """Check if this combination is used for macros or mappings.

        Parameters
        ----------
        combination : tuple of tuple of int
            One or more 3-tuples of type, code, action,
            for example ((EV_KEY, KEY_A, 1), (EV_ABS, ABS_X, -1))
            or ((EV_KEY, KEY_B, 1),)
        """
        return combination in self.macros or combination in self.key_to_code

    def maps_joystick(self):
        """If at least one of the joysticks will serve a special purpose."""
        return (self.left_purpose, self.right_purpose) != (NONE, NONE)

    def joystick_as_mouse(self):
        """If at least one joystick maps to an EV_REL capability."""
        purposes = (self.left_purpose, self.right_purpose)
        return MOUSE in purposes or WHEEL in purposes

    def joystick_as_dpad(self):
        """If at least one joystick may be mapped to keys."""
        purposes = (self.left_purpose, self.right_purpose)
        return BUTTONS in purposes

    def writes_keys(self):
        """Check if anything is being mapped to keys."""
        return len(self.macros) > 0 and len(self.key_to_code) > 0