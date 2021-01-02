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

from evdev.ecodes import EV_REL, REL_X, REL_Y, REL_WHEEL, REL_HWHEEL

from keymapper.logger import logger
from keymapper.config import MOUSE, WHEEL
from keymapper.dev.utils import get_max_abs


# miniscule movements on the joystick should not trigger a mouse wheel event
WHEEL_THRESHOLD = 0.15


def _write(device, ev_type, keycode, value):
    """Inject."""
    # if the mouse won't move even though correct stuff is written here, the
    # capabilities are probably wrong
    try:
        device.write(ev_type, keycode, value)
        device.syn()
    except OverflowError:
        logger.error('OverflowError (%s, %s, %s)', ev_type, keycode, value)
        pass


def accumulate(pending, current):
    """Since devices can't do float values, stuff has to be accumulated.

    If pending is 0.6 and current is 0.5, return 0.1 and 1.
    Because it should move 1px, and 0.1px is rememberd for the next value in
    pending.
    """
    pending += current
    current = int(pending)
    pending -= current
    return pending, current


def abs_max(value_1, value_2):
    """Get the value with the higher abs value."""
    if abs(value_1) > abs(value_2):
        return value_1
    return value_2


def get_values(abs_state, left_purpose, right_purpose):
    """Get the raw values for wheel and mouse movement.

    If two joysticks have the same purpose, the one that reports higher
    absolute values takes over the control.
    """
    mouse_x = 0
    mouse_y = 0
    wheel_x = 0
    wheel_y = 0

    if left_purpose == MOUSE:
        mouse_x = abs_max(mouse_x, abs_state[0])
        mouse_y = abs_max(mouse_y, abs_state[1])

    if left_purpose == WHEEL:
        wheel_x = abs_max(wheel_x, abs_state[0])
        wheel_y = abs_max(wheel_y, abs_state[1])

    if right_purpose == MOUSE:
        mouse_x = abs_max(mouse_x, abs_state[2])
        mouse_y = abs_max(mouse_y, abs_state[3])

    if right_purpose == WHEEL:
        wheel_x = abs_max(wheel_x, abs_state[2])
        wheel_y = abs_max(wheel_y, abs_state[3])

    return mouse_x, mouse_y, wheel_x, wheel_y


async def ev_abs_mapper(abs_state, input_device, keymapper_device, mapping):
    """Keep writing mouse movements based on the gamepad stick position.

    Even if no new input event arrived because the joystick remained at
    its position, this will keep injecting the mouse movement events.

    Parameters
    ----------
    abs_state : [int, int. int, int]
        array to read the current abs values from for events of codes
        ABS_X, ABS_Y, ABS_RX and ABS_RY
        Its contents will change while this function executes its loop from
        the outside.
    input_device : evdev.InputDevice
    keymapper_device : evdev.UInput
    mapping : Mapping
        the mapping object that configures the current injection
    """
    max_value = get_max_abs(input_device)

    if max_value in [0, 1, None]:
        # not something that was intended for this
        return

    logger.debug('Max abs of "%s": %s', input_device.name, max_value)

    max_speed = ((max_value ** 2) * 2) ** 0.5

    # events only take ints, so a movement of 0.3 needs to add
    # up to 1.2 to affect the cursor.
    pending_x_rel = 0
    pending_y_rel = 0
    pending_rx_rel = 0
    pending_ry_rel = 0

    pointer_speed = mapping.get('gamepad.joystick.pointer_speed')
    non_linearity = mapping.get('gamepad.joystick.non_linearity')
    left_purpose = mapping.get('gamepad.joystick.left_purpose')
    right_purpose = mapping.get('gamepad.joystick.right_purpose')
    x_scroll_speed = mapping.get('gamepad.joystick.x_scroll_speed')
    y_scroll_speed = mapping.get('gamepad.joystick.y_scroll_speed')

    logger.info(
        'Left joystick as %s, right joystick as %s',
        left_purpose,
        right_purpose
    )

    while True:
        start = time.time()
        mouse_x, mouse_y, wheel_x, wheel_y = get_values(
            abs_state,
            left_purpose,
            right_purpose
        )

        out_of_bounds = [
            val for val in [mouse_x, mouse_y, wheel_x, wheel_y]
            if val > max_value
        ]
        if len(out_of_bounds) > 0:
            logger.error(
                'Encountered inconsistent values: %s, max abs: %s',
                out_of_bounds,
                max_value
            )
            return

        # mouse movements
        if abs(mouse_x) > 0 or abs(mouse_y) > 0:
            if non_linearity != 1:
                # to make small movements smaller for more precision
                speed = (mouse_x ** 2 + mouse_y ** 2) ** 0.5
                factor = (speed / max_speed) ** non_linearity
            else:
                factor = 1

            rel_x = (mouse_x / max_value) * factor * pointer_speed
            rel_y = (mouse_y / max_value) * factor * pointer_speed
            pending_x_rel, rel_x = accumulate(pending_x_rel, rel_x)
            pending_y_rel, rel_y = accumulate(pending_y_rel, rel_y)
            if rel_x != 0:
                _write(keymapper_device, EV_REL, REL_X, rel_x)
            if rel_y != 0:
                _write(keymapper_device, EV_REL, REL_Y, rel_y)

        # wheel movements
        if abs(wheel_x) > 0:
            float_rel_rx = wheel_x * x_scroll_speed / max_value
            pending_rx_rel, rel_rx = accumulate(pending_rx_rel, float_rel_rx)
            if abs(float_rel_rx) > WHEEL_THRESHOLD * x_scroll_speed:
                _write(keymapper_device, EV_REL, REL_HWHEEL, rel_rx)

        if abs(wheel_y) > 0:
            float_rel_ry = wheel_y * y_scroll_speed / max_value
            pending_ry_rel, rel_ry = accumulate(pending_ry_rel, float_rel_ry)
            if abs(float_rel_ry) > WHEEL_THRESHOLD * y_scroll_speed:
                _write(keymapper_device, EV_REL, REL_WHEEL, -rel_ry)

        # try to do this as close to 60hz as possible
        time_taken = time.time() - start
        await asyncio.sleep(max(0.0, (1 / 60) - time_taken))
