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


"""Utility functions."""


import math
import sys

import evdev
from evdev.ecodes import (
    EV_KEY,
    EV_ABS,
    ABS_X,
    ABS_Y,
    ABS_RX,
    ABS_RY,
    EV_REL,
    REL_WHEEL,
    REL_HWHEEL,
)

from inputremapper.logger import logger
from inputremapper.configs.global_config import BUTTONS


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
    (EV_ABS, evdev.ecodes.ABS_PRESSURE),
]


# a third of a quarter circle, so that each quarter is divided in 3 areas:
# up, left and up-left. That makes up/down/left/right larger than the
# overlapping sections though, maybe it should be 8 equal areas though, idk
JOYSTICK_BUTTON_THRESHOLD = math.sin((math.pi / 2) / 3 * 1)


PRESS = 1
# D-Pads and joysticks can have a second press event, which moves the knob to the
# opposite side, reporting a negative value
PRESS_NEGATIVE = -1
RELEASE = 0


def sign(value):
    """Return -1, 0 or 1 depending on the input value."""
    if value > 0:
        return 1

    if value < 0:
        return -1

    return 0


def classify_action(event, abs_range=None):
    """Fit the event value to one of PRESS, PRESS_NEGATIVE or RELEASE

    A joystick that is pushed to the very side will probably send a high value, whereas
    having it close to the middle might send values close to 0 with some noise. A value
    of 1 is usually noise or from touching the joystick very gently and considered in
    resting position.
    """
    if event.type == EV_ABS and event.code in JOYSTICK:
        if abs_range is None:
            logger.error(
                "Got %s, but abs_range is %s",
                (event.type, event.code, event.value),
                abs_range,
            )
            return event.value

        # center is the value of the resting position
        center = (abs_range[1] + abs_range[0]) / 2
        # normalizer is the maximum possible value after centering
        normalizer = (abs_range[1] - abs_range[0]) / 2

        threshold = normalizer * JOYSTICK_BUTTON_THRESHOLD
        triggered = abs(event.value - center) > threshold
        return sign(event.value - center) if triggered else 0

    # non-joystick abs events (triggers) usually start at 0 and go up to 255,
    # but anything that is > 0 was safe to be treated as pressed so far

    return sign(event.value)


def is_key_down(action):
    """Is this action a key press."""
    return action in [PRESS, PRESS_NEGATIVE]


def is_key_up(action):
    """Is this action a key release."""
    return action == RELEASE


def is_wheel(event):
    """Check if this is a wheel event."""
    return event.type == EV_REL and event.code in [REL_WHEEL, REL_HWHEEL]


def will_report_key_up(event):
    """Check if the key is expected to report a down event as well."""
    return not is_wheel(event)


def should_map_as_btn(event, preset, gamepad):
    """Does this event describe a button that is or can be mapped.

    If a new kind of event should be mappable to buttons, this is the place
    to add it.

    Especially important for gamepad events, some of the buttons
    require special rules.

    Parameters
    ----------
    event : evdev.InputEvent
    preset : Preset
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

            l_purpose = preset.get("gamepad.joystick.left_purpose")
            r_purpose = preset.get("gamepad.joystick.right_purpose")

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


def get_abs_range(device, code=ABS_X):
    """Figure out the max and min value of EV_ABS events of that device.

    Like joystick movements or triggers.
    """
    # since input_device.absinfo(EV_ABS).max is too new for (some?) ubuntus,
    # figure out the max value via the capabilities
    capabilities = device.capabilities(absinfo=True)

    if EV_ABS not in capabilities:
        return None

    absinfo = [
        entry[1]
        for entry in capabilities[EV_ABS]
        if (
            entry[0] == code
            and isinstance(entry, tuple)
            and isinstance(entry[1], evdev.AbsInfo)
        )
    ]

    if len(absinfo) == 0:
        logger.warning(
            'Failed to get ABS info of "%s" for key %d: %s', device, code, capabilities
        )
        return None

    absinfo = absinfo[0]
    return absinfo.min, absinfo.max


def get_max_abs(device, code=ABS_X):
    """Figure out the max value of EV_ABS events of that device.

    Like joystick movements or triggers.
    """
    abs_range = get_abs_range(device, code)
    return abs_range and abs_range[1]


def is_service():
    return sys.argv[0].endswith("input-remapper-service")
