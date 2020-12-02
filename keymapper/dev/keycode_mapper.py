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

import evdev

from keymapper.logger import logger
from keymapper.state import KEYCODE_OFFSET


def should_map_event_as_btn(event):
    """Does this event describe a button.

    Especially important for gamepad events, some of the buttons
    require special rules.

    Parameters
    ----------
    event : evdev.events.InputEvent
    """
    # TODO test
    if event.type == evdev.events.EV_KEY:
        return True

    if event.type == evdev.events.EV_ABS and event.code > 5:
        # 1 - 5 seem to be joystick events
        return True

    return False


def handle_keycode(code_code_mapping, macros, event, uinput):
    """Write the mapped keycode or forward unmapped ones.

    Parameters
    ----------
    code_code_mapping : dict
        mapping of linux-keycode to linux-keycode. No need to substract
        anything before writing to the device.
    macros : dict
        mapping of linux-keycode to _Macro objects
    """
    if event.value == 2:
        # button-hold event
        return

    input_keycode = event.code

    # for logging purposes. It should log the same keycode as xev and gtk,
    # which is also displayed in the UI.
    xkb_keycode = input_keycode + KEYCODE_OFFSET

    if input_keycode in macros:
        if event.value != 1:
            # only key-down events trigger macros
            return

        macro = macros[input_keycode]
        logger.spam(
            'got code:%s value:%s, maps to macro %s',
            xkb_keycode,
            event.value,
            macro.code
        )
        asyncio.ensure_future(macro.run())
        return

    if input_keycode in code_code_mapping:
        target_keycode = code_code_mapping[input_keycode]
        logger.spam(
            'got code:%s value:%s event:%s, maps to code:%s',
            xkb_keycode,
            event.value,
            evdev.ecodes.EV[event.type],
            target_keycode + KEYCODE_OFFSET
        )
    else:
        logger.spam(
            'got unmapped code:%s value:%s',
            xkb_keycode,
            event.value,
        )
        target_keycode = input_keycode

    print('write', event.type, target_keycode, event.value)
    uinput.write(event.type, target_keycode, event.value)
    uinput.syn()
