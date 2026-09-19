# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2026 sezanzeb <4t1pzast9@mozmail.com>
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

from __future__ import annotations

from collections import defaultdict

from evdev.ecodes import EV_KEY, ABS_X, ABS_Y, EV_ABS

from inputremapper.configs.keyboard_layout import keyboard_layout
from inputremapper.injection.macros.argument import ArgumentConfig
from inputremapper.injection.macros.task import Task
from inputremapper.injection.global_uinputs import MIN_ABS, MAX_ABS


"""
TODO:
left_joystick
right_joystick
left_trigger
right_trigger
dpad
"""


class JoystickTaskBase(Task):
    """Move a joystick into a direction.

    This adds together with movements of the same joystick done by other keys,
    that are still behind held down."""

    # Overwrite this in inheriting classes
    x_code: int | None = ABS_X
    y_code: int | None = ABS_Y

    # For triggers and joysticks:
    # -5 to 5: 10
    # 0 to 5: 5
    abs_range = MAX_ABS - MIN_ABS
    min_abs = MIN_ABS
    max_abs = MAX_ABS
    # For anything else (dpads) overwrite this

    # Mutable, shared by all tasks in this process.
    state = defaultdict(int)

    # -1: min_abs
    # 0: center
    # 1: max_abs
    argument_configs = [
        ArgumentConfig(
            name="x",
            position=0,
            types=[int, float],
            default=0,
        ),
        ArgumentConfig(
            name="y",
            position=1,
            types=[int, float],
            default=0,
        ),
    ]

    def scale(self, arg_name: str) -> int:
        # 1  -> 1   -> 65536 - 32768 = 32768
        # 0  -> 0.5 -> 32768 - 32768 = 0
        # -1 -> 0   -> 0     - 32768 = -32768
        arg = self.get_argument(arg_name).get_value()
        value = int((arg + 1) / 2 * self.abs_range + self.min_abs)

    async def run(self, callback) -> None:
        x_code = self.x_code
        y_code = self.y_code

        # If a is mapped to left, and d to right, and both keys are pressed together,
        # it should result in an abs_x value of 0 (depending )

        if x_code is not None:
            self.state[self.x_code] += self.scale("x")
            callback(EV_ABS, x_code, self.state[self.x_code])

        if y_code is not None:
            self.state[self.x_code] += self.scale("y")
            callback(EV_ABS, y_code, self.state[self.y_code])

        await self._trigger_release_event.wait()

        if x_code is not None:
            self.state[self.x_code] -= self.scale("x")
            callback(EV_ABS, x_code, self.state[self.x_code])

        if y_code is not None:
            self.state[self.x_code] -= self.scale("y")
            callback(EV_ABS, y_code, self.state[self.y_code])


class DPadTask(JoystickTaskBase):
    x_code = HAT0X
    y_code = HAT0Y
    min_abs = -1
    max_abs = 1


class DPad2Task(JoystickTaskBase):
    x_code = HAT1X
    y_code = HAT1Y
    min_abs = -1
    max_abs = 1


class DPad3Task(JoystickTaskBase):
    x_code = HAT2X
    y_code = HAT2Y
    min_abs = -1
    max_abs = 1


class LeftJoystickTask(JoystickTaskBase):
    x_code = ABS_X
    y_code = ABS_Y


class RightJoystickTask(JoystickTaskBase):
    x_code = ABS_RX
    y_code = ABS_RY


class LeftTriggerTask(JoystickTaskBase):
    x_code = ABS_Z
    y_code = None


class RightTriggerTask(JoystickTaskBase):
    x_code = ABS_RZ
    y_code = None
