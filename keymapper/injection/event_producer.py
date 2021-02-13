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

from evdev.ecodes import EV_REL, REL_X, REL_Y, REL_WHEEL, REL_HWHEEL, \
    EV_ABS, ABS_X, ABS_Y, ABS_RX, ABS_RY

from keymapper.logger import logger
from keymapper.config import MOUSE, WHEEL
from keymapper import utils

# miniscule movements on the joystick should not trigger a mouse wheel event
WHEEL_THRESHOLD = 0.15


def abs_max(value_1, value_2):
    """Get the value with the higher abs value."""
    if abs(value_1) > abs(value_2):
        return value_1
    return value_2


class EventProducer:
    """Keeps producing events at 60hz if needed.

    Can debounce arbitrary functions. Maps joysticks to mouse movements.

    This class does not handle injecting macro stuff over time, that is done
    by the keycode_mapper.
    """
    def __init__(self, context):
        """Construct the event producer without it doing anything yet."""
        self.context = context

        self.mouse_uinput = None
        self.max_abs = None
        # events only take ints, so a movement of 0.3 needs to add
        # up to 1.2 to affect the cursor, with 0.2 remaining
        self.pending_rel = {REL_X: 0, REL_Y: 0, REL_WHEEL: 0, REL_HWHEEL: 0}
        # the last known position of the joystick
        self.abs_state = {ABS_X: 0, ABS_Y: 0, ABS_RX: 0, ABS_RY: 0}

        self.debounces = {}

    def notify(self, event):
        """Tell the EventProducer about the newest ABS event.

        Afterwards, it can continue moving the mouse pointer in the
        correct direction.
        """
        if event.type == EV_ABS and event.code in self.abs_state:
            self.abs_state[event.code] = event.value

    def _write(self, device, ev_type, keycode, value):
        """Inject."""
        # if the mouse won't move even though correct stuff is written here,
        # the capabilities are probably wrong
        try:
            device.write(ev_type, keycode, value)
            device.syn()
        except OverflowError:
            # screwed up the calculation of mouse movements
            logger.error('OverflowError (%s, %s, %s)', ev_type, keycode, value)

    def debounce(self, debounce_id, func, args, ticks):
        """Debounce a function call.

        Parameters
        ----------
        debounce_id : hashable
            If this function is called with the same debounce_id again,
            the previous debouncing is overwritten, and there fore restarted.
        func : function
        args : tuple
        ticks : int
            After ticks * 1 / 60 seconds the function will be executed,
            unless debounce is called again with the same debounce_id
        """
        self.debounces[debounce_id] = [func, args, ticks]

    def accumulate(self, code, input_value):
        """Since devices can't do float values, stuff has to be accumulated.

        If pending is 0.6 and input_value is 0.5, return 0.1 and 1.
        Because it should move 1px, and 0.1px is rememberd for the next value
        in pending.
        """
        self.pending_rel[code] += input_value
        output_value = int(self.pending_rel[code])
        self.pending_rel[code] -= output_value
        return output_value

    def set_mouse_uinput(self, uinput):
        """Set where to write mouse movements to."""
        logger.debug('Going to inject mouse movements to "%s"', uinput.name)
        self.mouse_uinput = uinput

    def set_max_abs_from(self, device):
        """Update the maximum value joysticks will report.

        This information is needed for abs -> rel mapping.
        """
        if device is None:
            # I don't think this ever happened
            logger.error('Expected device to not be None')
            return

        max_abs = utils.get_max_abs(device)
        if max_abs in [0, 1, None]:
            # max_abs of joysticks is usually a much higher number
            return

        self.max_abs = max_abs
        logger.debug('Max abs of "%s": %s', device.name, max_abs)

    def get_abs_values(self):
        """Get the raw values for wheel and mouse movement.

        If two joysticks have the same purpose, the one that reports higher
        absolute values takes over the control.
        """
        mouse_x, mouse_y, wheel_x, wheel_y = 0, 0, 0, 0

        if self.context.left_purpose == MOUSE:
            mouse_x = abs_max(mouse_x, self.abs_state[ABS_X])
            mouse_y = abs_max(mouse_y, self.abs_state[ABS_Y])

        if self.context.left_purpose == WHEEL:
            wheel_x = abs_max(wheel_x, self.abs_state[ABS_X])
            wheel_y = abs_max(wheel_y, self.abs_state[ABS_Y])

        if self.context.right_purpose == MOUSE:
            mouse_x = abs_max(mouse_x, self.abs_state[ABS_RX])
            mouse_y = abs_max(mouse_y, self.abs_state[ABS_RY])

        if self.context.right_purpose == WHEEL:
            wheel_x = abs_max(wheel_x, self.abs_state[ABS_RX])
            wheel_y = abs_max(wheel_y, self.abs_state[ABS_RY])

        return mouse_x, mouse_y, wheel_x, wheel_y

    def is_handled(self, event):
        """Check if the event is something this will take care of."""
        if event.type != EV_ABS or event.code not in utils.JOYSTICK:
            return False

        if self.max_abs is None:
            return False

        purposes = [MOUSE, WHEEL]
        left_purpose = self.context.left_purpose
        right_purpose = self.context.right_purpose

        if event.code in (ABS_X, ABS_Y) and left_purpose in purposes:
            return True

        if event.code in (ABS_RX, ABS_RY) and right_purpose in purposes:
            return True

        return False

    async def run(self):
        """Keep writing mouse movements based on the gamepad stick position.

        Even if no new input event arrived because the joystick remained at
        its position, this will keep injecting the mouse movement events.
        """
        max_abs = self.max_abs
        mapping = self.context.mapping
        pointer_speed = mapping.get('gamepad.joystick.pointer_speed')
        non_linearity = mapping.get('gamepad.joystick.non_linearity')
        x_scroll_speed = mapping.get('gamepad.joystick.x_scroll_speed')
        y_scroll_speed = mapping.get('gamepad.joystick.y_scroll_speed')

        if max_abs is not None:
            logger.info(
                'Left joystick as %s, right joystick as %s',
                self.context.left_purpose,
                self.context.right_purpose
            )

        start = time.time()
        while True:
            # production loop. try to do this as close to 60hz as possible
            time_taken = time.time() - start
            await asyncio.sleep(max(0.0, (1 / 60) - time_taken))
            start = time.time()

            """handling debounces"""

            for debounce in self.debounces.values():
                if debounce[2] == -1:
                    # has already been triggered
                    continue
                if debounce[2] == 0:
                    debounce[0](*debounce[1])
                    debounce[2] = -1
                else:
                    debounce[2] -= 1

            """mouse movement production"""

            if max_abs is None:
                # no ev_abs events will be mapped to ev_rel
                continue

            max_speed = ((max_abs ** 2) * 2) ** 0.5

            abs_values = self.get_abs_values()

            if len([val for val in abs_values if val > max_abs]) > 0:
                logger.error(
                    'Inconsistent values: %s, max_abs: %s',
                    abs_values, max_abs
                )
                return

            mouse_x, mouse_y, wheel_x, wheel_y = abs_values

            # mouse movements
            if abs(mouse_x) > 0 or abs(mouse_y) > 0:
                if non_linearity != 1:
                    # to make small movements smaller for more precision
                    speed = (mouse_x ** 2 + mouse_y ** 2) ** 0.5
                    factor = (speed / max_speed) ** non_linearity
                else:
                    factor = 1

                rel_x = (mouse_x / max_abs) * factor * pointer_speed
                rel_y = (mouse_y / max_abs) * factor * pointer_speed
                rel_x = self.accumulate(REL_X, rel_x)
                rel_y = self.accumulate(REL_Y, rel_y)
                if rel_x != 0:
                    self._write(self.mouse_uinput, EV_REL, REL_X, rel_x)
                if rel_y != 0:
                    self._write(self.mouse_uinput, EV_REL, REL_Y, rel_y)

            # wheel movements
            if abs(wheel_x) > 0:
                change = wheel_x * x_scroll_speed / max_abs
                value = self.accumulate(REL_WHEEL, change)
                if abs(change) > WHEEL_THRESHOLD * x_scroll_speed:
                    self._write(self.mouse_uinput, EV_REL, REL_HWHEEL, value)

            if abs(wheel_y) > 0:
                change = wheel_y * y_scroll_speed / max_abs
                value = self.accumulate(REL_HWHEEL, change)
                if abs(change) > WHEEL_THRESHOLD * y_scroll_speed:
                    self._write(self.mouse_uinput, EV_REL, REL_WHEEL, -value)
