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


"""Keeps mapping joystick to mouse movements."""


import asyncio
import time

import evdev
from evdev.ecodes import EV_ABS, EV_REL, REL_X, REL_Y, REL_WHEEL, REL_HWHEEL

from keymapper.logger import logger
from keymapper.config import config


# other events for ABS include buttons
JOYSTICK = [
    evdev.ecodes.ABS_X,
    evdev.ecodes.ABS_Y,
    evdev.ecodes.ABS_RX,
    evdev.ecodes.ABS_RY,
]

# miniscule movements on the joystick should not trigger a mouse wheel event
WHEEL_THRESHOLD = 0.3


def _write(device, ev_type, keycode, value):
    """Inject."""
    device.write(ev_type, keycode, value)
    device.syn()


def accumulate(pending, current):
    """Since devices can't do float values, stuff has to be accumulated.

    If pending is 0.6 and current is 0.5, return 0.1 and 1.
    Because 1 may move 1px, and 0.1px is rememberd for the next value in
    pending.
    """
    pending += current
    current = int(pending)
    pending -= current
    return pending, current


async def ev_abs_mapper(abs_state, input_device, keymapper_device):
    """Keep writing mouse movements based on the gamepad stick position.

    Parameters
    ----------
    abs_state : [int, int]
        array to read the current abs values from. Like a pointer.
    input_device : evdev.InputDevice
    keymapper_device : evdev.UInput
    """
    # events only take ints, so a movement of 0.3 needs to add
    # up to 1.2 to affect the cursor.
    #
    pending_x_rel = 0
    pending_y_rel = 0
    pending_rx_rel = 0
    pending_ry_rel = 0

    logger.info('Mapping gamepad to mouse movements')
    max_value = input_device.absinfo(EV_ABS).max
    max_speed = ((max_value ** 2) * 2) ** 0.5

    pointer_speed = config.get('gamepad.joystick.pointer_speed')
    non_linearity = config.get('gamepad.joystick.non_linearity')

    while True:
        start = time.time()
        abs_x, abs_y, abs_rx, abs_ry = abs_state

        if non_linearity != 1:
            # to make small movements smaller for more precision
            speed = (abs_x ** 2 + abs_y ** 2) ** 0.5
            factor = (speed / max_speed) ** non_linearity
        else:
            factor = 1

        # mouse movements
        rel_x = abs_x * factor * pointer_speed / max_value
        rel_y = abs_y * factor * pointer_speed / max_value
        pending_x_rel, rel_x = accumulate(pending_x_rel, rel_x)
        pending_y_rel, rel_y = accumulate(pending_y_rel, rel_y)
        if rel_x != 0:
            _write(keymapper_device, EV_REL, REL_X, rel_x)
        if rel_y != 0:
            _write(keymapper_device, EV_REL, REL_Y, rel_y)

        # wheel movements
        float_rel_rx = abs_rx / max_value
        pending_rx_rel, rel_rx = accumulate(pending_rx_rel, float_rel_rx)
        if abs(float_rel_rx) > WHEEL_THRESHOLD:
            _write(keymapper_device, EV_REL, REL_HWHEEL, -rel_rx)

        float_rel_ry = abs_ry / max_value
        pending_ry_rel, rel_ry = accumulate(pending_ry_rel, float_rel_ry)
        if abs(float_rel_ry) > WHEEL_THRESHOLD:
            _write(keymapper_device, EV_REL, REL_WHEEL, -rel_ry)

        # try to do this as close to 60hz as possible
        time_taken = time.time() - start
        await asyncio.sleep(max(0.0, (1 / 60) - time_taken))
