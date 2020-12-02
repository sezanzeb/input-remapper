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


"""Inject a keycode based on the mapping."""


import asyncio

from keymapper.logger import logger
from keymapper.state import system_mapping, KEYCODE_OFFSET


def handle_keycode(mapping, macros, event, uinput):
    """Write the mapped keycode."""
    input_keycode = event.code + KEYCODE_OFFSET
    character = mapping.get_character(input_keycode)

    if character is None:
        # unknown keycode, forward it
        target_keycode = input_keycode
    elif macros.get(input_keycode) is not None:
        if event.value == 0:
            return
        logger.spam(
            'got code:%s value:%s, maps to macro %s',
            event.code + KEYCODE_OFFSET,
            event.value,
            character
        )
        macro = macros.get(input_keycode)
        if macro is not None:
            asyncio.ensure_future(macro.run())
        return
    else:
        # TODO compile int-int mapping instead of going this route.
        #  I think that makes the reverse mapping obsolete.
        #  It already is actually.
        target_keycode = system_mapping.get(character)
        if target_keycode is None:
            logger.error(
                'Don\'t know what %s maps to',
                character
            )
            return

        logger.spam(
            'got code:%s value:%s, maps to code:%s char:%s',
            event.code + KEYCODE_OFFSET,
            event.value,
            target_keycode,
            character
        )

    uinput.write(event.type, target_keycode - KEYCODE_OFFSET, event.value)
    uinput.syn()
