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


"""Create some files and objects that are needed for the app to work."""


import os
import re
import stat

import evdev

from keymapper.mapping import Mapping
from keymapper.cli import parse_xmodmap, apply_symbols
from keymapper.logger import logger
from keymapper.paths import KEYCODES_PATH, SYMBOLS_PATH
from keymapper.data import get_data_path


# one mapping object for the whole application that holds all
# customizations, as shown in the UI
custom_mapping = Mapping()

# this mapping is for the custom key-mapper /dev device. The keycode
# injector injects those keys to trigger the wanted character
internal_mapping = Mapping()

system_mapping = Mapping()

capabilities = []

# permissions for files created in /usr
_PERMISSIONS = stat.S_IREAD | stat.S_IWRITE | stat.S_IRGRP | stat.S_IROTH


def create_identity_mapping(keycodes=None):
    """Because the concept of "reasonable symbolic names" [3] doesn't apply
    when mouse buttons are all over the place. Create an identity mapping
    to make generating "symbols" files easier. Keycode 10 -> "<10>"

    The identity mapping is provided to '-keycodes' of setxkbmap.
    """
    logger.debug2('Available keycodes: %s', keycodes)
    min_keycode = min(keycodes)
    max_keycode = max(keycodes)
    logger.debug(
        'Creating the identity mapping. min: %s, max: %s',
        min_keycode,
        max_keycode
    )

    xkb_keycodes = []
    if keycodes is None:
        keycodes = range(min_keycode, max_keycode + 1)

    for keycode in keycodes:
        xkb_keycodes.append(f'<{keycode}> = {keycode};')

    template_path = get_data_path('xkb_keycodes_template')
    with open(template_path, 'r') as template_file:
        template = template_file.read()

    result = template.format(
        minimum=min_keycode,
        maximum=max_keycode,
        xkb_keycodes='\n    '.join(xkb_keycodes)
    )

    if not os.path.exists(KEYCODES_PATH):
        logger.debug('Creating "%s"', KEYCODES_PATH)
        os.makedirs(os.path.dirname(KEYCODES_PATH), exist_ok=True)
        os.mknod(KEYCODES_PATH)
        os.chmod(KEYCODES_PATH, _PERMISSIONS)

    with open(KEYCODES_PATH, 'w') as f:
        f.write(result)


def generate_symbols(mapping):
    """Create config contents to be placed in /usr/share/X11/xkb/symbols.

    It's the mapping of the preset as expected by X. This function does not
    create the file.

    Parameters
    ----------
    mapping : Mapping
        If you need to create a symbols file for some other mapping you can
        pass it to this parameter. By default the custom mapping will be
        used that is also displayed in the user interface.
    """
    if len(mapping) == 0:
        raise ValueError('Mapping is empty')

    # If the symbols file contains key codes that are not present in
    # the keycodes file, THE WHOLE X SESSION WILL CRASH!
    if not os.path.exists(KEYCODES_PATH):
        raise FileNotFoundError('Expected the keycodes file to exist')

    with open(KEYCODES_PATH, 'r') as f:
        keycodes = re.findall(r'<.+?>', f.read())

    xkb_symbols = []
    for keycode, character in mapping:
        if f'<{keycode}>' not in keycodes:
            logger.error(f'Unknown code <{keycode}> for "{character}"')
            # don't append that one, otherwise X would crash when loading
            continue

        xkb_symbols.append(
            f'key <{keycode}> {{ [ {character} ] }}; '
        )

    if len(xkb_symbols) == 0:
        logger.error('Failed to populate xkb_symbols')
        return None

    template_path = get_data_path('xkb_symbols_template')
    with open(template_path, 'r') as template_file:
        template = template_file.read()

    result = template.format(
        name='key-mapper',
        xkb_symbols='\n    '.join(xkb_symbols)
    )

    return result


def find_all_used_capabilities():
    """Find all capabilities of all devices that are already in use."""
    base = '/dev/input'
    inputs = os.listdir(base)
    result = []
    for input in inputs:
        try:
            device = evdev.InputDevice(os.path.join(base, input))
            for codes in device.capabilities().values():
                for code in codes:
                    if not isinstance(code, int):
                        continue
                    code += 8
                    if code not in result:
                        result.append(code)
        except OSError:
            pass
    return result


find_all_used_capabilities()


def initialize():
    """Prepare all files and objects that are needed."""
    # this mapping represents the xmodmap output, which stays constant
    # TODO verify that this is the system default and not changed when I
    #  setxkbmap my mouse
    parse_xmodmap(system_mapping)

    # find keycodes that are unused in xmodmap.
    i = 8
    # used_codes = find_all_used_capabilities()
    while len(capabilities) < len(system_mapping):
        if system_mapping.get_character(i) is None:
            capabilities.append(i)
        # if i not in used_codes:
        #     capabilities.append(i)
        i += 1

    # basically copy the xmodmap system mapping into another one, but
    # with keycodes that don't conflict, so that I'm free to use them
    # whenever I want without worrying about my keyboards "1" and my
    # mouses "whatever" to clash.
    for i, (_, character) in enumerate(system_mapping):
        internal_mapping.change(
            previous_keycode=None,
            new_keycode=capabilities[i],
            character=character
        )

    """# now take all holes between 8 and the maximum keycode in internal_mapping
    # and fill them with none
    for i in range(8, capabilities[-1]):
        if i in capabilities:
            continue
        capabilities.append(i)
        internal_mapping.change(
            previous_keycode=None,
            new_keycode=i,
            character='none'
        )"""

    # assert len(system_mapping) == len(internal_mapping)

    logger.debug('Prepared the internal mapping')

    # Specify "keycode 300 belongs to mapping <300>", which is then used
    # to map keycode 300 to a character.
    create_identity_mapping(capabilities)

    # now put the internal_mapping into a symbols file, which is applied
    # on key-mappers own /dev input.
    with open(SYMBOLS_PATH, 'w') as f:
        contents = generate_symbols(internal_mapping)
        if contents is not None:
            f.write(contents)
        logger.debug('Wrote symbols file %s', SYMBOLS_PATH)
