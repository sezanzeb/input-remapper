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


"""Keeps mapping joystick to mouse movements."""


import asyncio
import time

from evdev.ecodes import (
    EV_REL,
    REL_X,
    REL_Y,
    REL_WHEEL,
    REL_HWHEEL,
    EV_ABS,
    ABS_X,
    ABS_Y,
    ABS_RX,
    ABS_RY,
)

from inputremapper.logger import logger
from inputremapper.config import MOUSE, WHEEL
from inputremapper import utils
from inputremapper.injection.consumers.consumer import Consumer
from inputremapper.groups import classify, GAMEPAD

# miniscule movements on the joystick should not trigger a mouse wheel event
WHEEL_THRESHOLD = 0.15


def abs_max(value_1, value_2):
    """Get the value with the higher abs value."""
    if abs(value_1) > abs(value_2):
        return value_1
    return value_2


class JoystickToMouse(Consumer):
    """Keeps producing events at 60hz if needed.

    Maps joysticks to mouse movements.

    This class does not handle injecting macro stuff over time, that is done
    by the keycode_mapper.
    """

    def __init__(self, *args, **kwargs):
        """Construct the event producer without it doing anything yet."""
        super().__init__(*args, **kwargs)

        self._abs_range = None
        self._set_abs_range_from(self.source)

        # events only take ints, so a movement of 0.3 needs to add
        # up to 1.2 to affect the cursor, with 0.2 remaining
        self.pending_rel = {REL_X: 0, REL_Y: 0, REL_WHEEL: 0, REL_HWHEEL: 0}
        # the last known position of the joystick
        self.abs_state = {ABS_X: 0, ABS_Y: 0, ABS_RX: 0, ABS_RY: 0}

    def is_enabled(self):
        gamepad = classify(self.source) == GAMEPAD
        return gamepad and self.context.joystick_as_mouse()

    def _write(self, ev_type, keycode, value):
        """Inject."""
        # if the mouse won't move even though correct stuff is written here,
        # the capabilities are probably wrong
        try:
            self.context.uinput.write(ev_type, keycode, value)
            self.context.uinput.syn()
        except OverflowError:
            # screwed up the calculation of mouse movements
            logger.error("OverflowError (%s, %s, %s)", ev_type, keycode, value)

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

    def _set_abs_range_from(self, device):
        """Update the min and max values joysticks will report.

        This information is needed for abs -> rel mapping.
        """
        if device is None:
            # I don't think this ever happened
            logger.error("Expected device to not be None")
            return

        abs_range = utils.get_abs_range(device)
        if abs_range is None:
            return

        if abs_range[1] in [0, 1, None]:
            # max abs_range of joysticks is usually a much higher number
            return

        self.set_abs_range(*abs_range)
        logger.debug('ABS range of "%s": %s', device.name, abs_range)

    def set_abs_range(self, min_abs, max_abs):
        """Update the min and max values joysticks will report.

        This information is needed for abs -> rel mapping.
        """
        self._abs_range = (min_abs, max_abs)

        # all joysticks in resting position by default
        center = (self._abs_range[1] + self._abs_range[0]) / 2
        self.abs_state = {ABS_X: center, ABS_Y: center, ABS_RX: center, ABS_RY: center}

    def get_abs_values(self):
        """Get the raw values for wheel and mouse movement.

        Returned values center around 0 and are normalized into -1 and 1.

        If two joysticks have the same purpose, the one that reports higher
        absolute values takes over the control.
        """
        # center is the value of the resting position
        center = (self._abs_range[1] + self._abs_range[0]) / 2
        # normalizer is the maximum possible value after centering
        normalizer = (self._abs_range[1] - self._abs_range[0]) / 2

        mouse_x = 0
        mouse_y = 0
        wheel_x = 0
        wheel_y = 0

        def standardize(value):
            return (value - center) / normalizer

        if self.context.left_purpose == MOUSE:
            mouse_x = abs_max(mouse_x, standardize(self.abs_state[ABS_X]))
            mouse_y = abs_max(mouse_y, standardize(self.abs_state[ABS_Y]))

        if self.context.left_purpose == WHEEL:
            wheel_x = abs_max(wheel_x, standardize(self.abs_state[ABS_X]))
            wheel_y = abs_max(wheel_y, standardize(self.abs_state[ABS_Y]))

        if self.context.right_purpose == MOUSE:
            mouse_x = abs_max(mouse_x, standardize(self.abs_state[ABS_RX]))
            mouse_y = abs_max(mouse_y, standardize(self.abs_state[ABS_RY]))

        if self.context.right_purpose == WHEEL:
            wheel_x = abs_max(wheel_x, standardize(self.abs_state[ABS_RX]))
            wheel_y = abs_max(wheel_y, standardize(self.abs_state[ABS_RY]))

        # Some joysticks report from 0 to 255 (EMV101),
        # others from -32768 to 32767 (X-Box 360 Pad)
        return mouse_x, mouse_y, wheel_x, wheel_y

    def is_handled(self, event):
        """Check if the event is something this will take care of."""
        if event.type != EV_ABS or event.code not in utils.JOYSTICK:
            return False

        if self._abs_range is None:
            return False

        purposes = [MOUSE, WHEEL]
        left_purpose = self.context.left_purpose
        right_purpose = self.context.right_purpose

        if event.code in (ABS_X, ABS_Y) and left_purpose in purposes:
            return True

        if event.code in (ABS_RX, ABS_RY) and right_purpose in purposes:
            return True

        return False

    async def notify(self, event):
        if event.type == EV_ABS and event.code in self.abs_state:
            self.abs_state[event.code] = event.value

    async def run(self):
        """Keep writing mouse movements based on the gamepad stick position.

        Even if no new input event arrived because the joystick remained at
        its position, this will keep injecting the mouse movement events.
        """
        abs_range = self._abs_range
        mapping = self.context.mapping
        pointer_speed = mapping.get("gamepad.joystick.pointer_speed")
        non_linearity = mapping.get("gamepad.joystick.non_linearity")
        x_scroll_speed = mapping.get("gamepad.joystick.x_scroll_speed")
        y_scroll_speed = mapping.get("gamepad.joystick.y_scroll_speed")
        max_speed = 2 ** 0.5  # for normalized abs event values

        if abs_range is not None:
            logger.info(
                "Left joystick as %s, right joystick as %s",
                self.context.left_purpose,
                self.context.right_purpose,
            )

        start = time.time()
        while True:
            # try to do this as close to 60hz as possible
            time_taken = time.time() - start
            await asyncio.sleep(max(0.0, (1 / 60) - time_taken))
            start = time.time()

            if abs_range is None:
                # no ev_abs events will be mapped to ev_rel
                continue

            abs_values = self.get_abs_values()

            if len([val for val in abs_values if not -1 <= val <= 1]) > 0:
                logger.error("Inconsistent values: %s", abs_values)
                continue

            mouse_x, mouse_y, wheel_x, wheel_y = abs_values

            # mouse movements
            if abs(mouse_x) > 0 or abs(mouse_y) > 0:
                if non_linearity != 1:
                    # to make small movements smaller for more precision
                    speed = (mouse_x ** 2 + mouse_y ** 2) ** 0.5  # pythagoras
                    factor = (speed / max_speed) ** non_linearity
                else:
                    factor = 1

                rel_x = mouse_x * factor * pointer_speed
                rel_y = mouse_y * factor * pointer_speed
                rel_x = self.accumulate(REL_X, rel_x)
                rel_y = self.accumulate(REL_Y, rel_y)
                if rel_x != 0:
                    self._write(EV_REL, REL_X, rel_x)
                if rel_y != 0:
                    self._write(EV_REL, REL_Y, rel_y)

            # wheel movements
            if abs(wheel_x) > 0:
                change = wheel_x * x_scroll_speed
                value = self.accumulate(REL_WHEEL, change)
                if abs(change) > WHEEL_THRESHOLD * x_scroll_speed:
                    self._write(EV_REL, REL_HWHEEL, value)

            if abs(wheel_y) > 0:
                change = wheel_y * y_scroll_speed
                value = self.accumulate(REL_HWHEEL, change)
                if abs(change) > WHEEL_THRESHOLD * y_scroll_speed:
                    self._write(EV_REL, REL_WHEEL, -value)
