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
from evdev.ecodes import EV_KEY, EV_ABS, ABS_MISC

from keymapper.logger import logger
from keymapper.dev.ev_abs_mapper import JOYSTICK


# maps mouse buttons to macro instances that have been executed. They may
# still be running or already be done.
active_macros = {}


def should_map_event_as_btn(ev_type, code):
    """Does this event describe a button.

    Especially important for gamepad events, some of the buttons
    require special rules.

    Parameters
    ----------
    ev_type : int
        one of evdev.events
    code : int
        linux keycode
    """
    if ev_type == EV_KEY:
        return True

    if ev_type == EV_ABS and code not in JOYSTICK:
        return True

    return False


def is_key_down(event):
    """Is this event a key press."""
    if event.type == EV_KEY:
        # might be 2 for hold
        return event.value == 1

    # for all other event types, just fire for anything that is not 0
    return event.value != 0


def is_key_up(event):
    """Is this event a key release."""
    return event.value == 0


def handle_keycode(code_to_code, macros, event, uinput):
    """Write the mapped keycode or forward unmapped ones.

    Parameters
    ----------
    code_to_code : dict
        mapping of linux-keycode to linux-keycode
    macros : dict
        mapping of linux-keycode to _Macro objects
    event : evdev.InputEvent
    """
    if event.value == 2:
        # button-hold event. Linux seems to create them on its own, no need
        # to inject them.
        return

    input_keycode = event.code
    input_type = event.type

    if input_keycode in macros:
        if is_key_up(event):
            # Tell the macro for that keycode that the key is released and
            # let it decide what to with that information.
            macro = active_macros.get(input_keycode)
            if macro is not None and macro.holding:
                macro.release_key()

        if not is_key_down(event):
            return

        existing_macro = active_macros.get(input_keycode)
        if existing_macro is not None:
            # make sure that a duplicate key-down event won't make a
            # macro with a hold function run forever. there should always
            # be only one active.
            # Furthermore, don't stop and rerun the macro because gamepad
            # triggers report events all the time just by releasing the key.
            if existing_macro.running:
                return

        macro = macros[input_keycode]
        active_macros[input_keycode] = macro
        macro.press_key()
        logger.spam(
            'got code:%s value:%s, maps to macro %s',
            input_keycode,
            event.value,
            macro.code
        )
        asyncio.ensure_future(macro.run())
        return

    if input_keycode in code_to_code:
        target_keycode = code_to_code[input_keycode]
        target_type = EV_KEY
        logger.spam(
            'got code:%s value:%s event:%s, maps to EV_KEY:%s',
            input_keycode,
            event.value,
            evdev.ecodes.EV[event.type],
            target_keycode
        )
    else:
        logger.spam(
            'got unmapped code:%s value:%s',
            input_keycode,
            event.value,
        )
        target_keycode = input_keycode
        target_type = input_type

    uinput.write(target_type, target_keycode, event.value)
    uinput.syn()
