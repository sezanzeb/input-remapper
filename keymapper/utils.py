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


"""Utility functions."""


import math

import evdev
from evdev.ecodes import EV_KEY, EV_ABS, ABS_X, ABS_Y, ABS_RX, ABS_RY, \
    EV_REL, REL_WHEEL, REL_HWHEEL

from keymapper.logger import logger
from keymapper.config import BUTTONS


# other events for ABS include buttons
JOYSTICK = [
    evdev.ecodes.ABS_X,
    evdev.ecodes.ABS_Y,
    evdev.ecodes.ABS_RX,
    evdev.ecodes.ABS_RY,
]


# drawing table stylus movements
STYLUS = [
    (EV_ABS, evdev.ecodes.ABS_DISTANCE),
    (EV_ABS, evdev.ecodes.ABS_TILT_X),
    (EV_ABS, evdev.ecodes.ABS_TILT_Y),
    (EV_KEY, evdev.ecodes.BTN_DIGI),
    (EV_ABS, evdev.ecodes.ABS_PRESSURE)
]


# a third of a quarter circle, so that each quarter is divided in 3 areas:
# up, left and up-left. That makes up/down/left/right larger than the
# overlapping sections though, maybe it should be 8 equal areas though, idk
JOYSTICK_BUTTON_THRESHOLD = math.sin((math.pi / 2) / 3 * 1)


def sign(value):
    """Return -1, 0 or 1 depending on the input value."""
    if value > 0:
        return 1

    if value < 0:
        return -1

    return 0


def normalize_value(event, max_abs):
    """Fit the event value to one of 0, 1 or -1."""
    if event.type == EV_ABS and event.code in JOYSTICK:
        if max_abs is None:
            logger.error(
                'Got %s, but max_abs is %s',
                (event.type, event.code, event.value), max_abs
            )
            return event.value

        threshold = max_abs * JOYSTICK_BUTTON_THRESHOLD
        triggered = abs(event.value) > threshold
        return sign(event.value) if triggered else 0

    return sign(event.value)


def is_wheel(event):
    """Check if this is a wheel event."""
    return event.type == EV_REL and event.code in [REL_WHEEL, REL_HWHEEL]


def will_report_key_up(event):
    """Check if the key is expected to report a down event as well."""
    return not is_wheel(event)


def should_map_event_as_btn(event, mapping, gamepad):
    """Does this event describe a button.

    If it does, this function will make sure its value is one of [-1, 0, 1],
    so that it matches the possible values in a mapping object if needed.

    If a new kind of event should be mappable to buttons, this is the place
    to add it.

    Especially important for gamepad events, some of the buttons
    require special rules.

    Parameters
    ----------
    event : evdev.InputEvent
    mapping : Mapping
    gamepad : bool
        If the device is treated as gamepad
    """
    if (event.type, event.code) in STYLUS:
        return False

    is_mousepad = event.type == EV_ABS and 47 <= event.code <= 61
    if is_mousepad:
        return False

    if event.type == EV_ABS:
        if event.code == evdev.ecodes.ABS_MISC:
            # what is that even supposed to be.
            # the intuos 5 spams those with every event
            return False

        if event.code in JOYSTICK:
            if not gamepad:
                return False

            l_purpose = mapping.get('gamepad.joystick.left_purpose')
            r_purpose = mapping.get('gamepad.joystick.right_purpose')

            if event.code in [ABS_X, ABS_Y] and l_purpose == BUTTONS:
                return True

            if event.code in [ABS_RX, ABS_RY] and r_purpose == BUTTONS:
                return True
        else:
            # for non-joystick buttons just always offer mapping them to
            # buttons
            return True

    if is_wheel(event):
        return True

    if event.type == EV_KEY:
        # usually all EV_KEY events are allright, except for
        if event.code == evdev.ecodes.BTN_TOUCH:
            return False

        return True

    return False


def get_max_abs(device):
    """Figure out the maximum value of EV_ABS events of that device.

    Like joystick movements or triggers.
    """
    # since input_device.absinfo(EV_ABS).max is too new for (some?) ubuntus,
    # figure out the max value via the capabilities
    capabilities = device.capabilities(absinfo=True)

    if EV_ABS not in capabilities:
        return None

    absinfos = [
        entry[1] for entry in
        capabilities[EV_ABS]
        if isinstance(entry, tuple) and isinstance(entry[1], evdev.AbsInfo)
    ]

    if len(absinfos) == 0:
        logger.error('Failed to get max abs of "%s"')
        return None

    max_abs = absinfos[0].max

    return max_abs
