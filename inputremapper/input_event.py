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

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Tuple, Union, Sequence, Callable, Optional, Any

import evdev
from evdev import ecodes

from inputremapper.configs.system_mapping import system_mapping
from inputremapper.exceptions import InputEventCreationError
from inputremapper.gui.messages.message_broker import MessageType
from inputremapper.logger import logger

InputEventValidationType = Union[
    str,
    Tuple[int, int, int],
    evdev.InputEvent,
]


# if "Use as analog" is set in the advanced mapping editor, the value will be set to 0
USE_AS_ANALOG_VALUE = 0


class EventActions(enum.Enum):
    """Additional information an InputEvent can send through the event pipeline."""

    as_key = enum.auto()  # treat this event as a key event
    recenter = enum.auto()  # recenter the axis when receiving this
    none = enum.auto()

    # used in combination with as_key, for originally abs or rel events
    positive_trigger = enum.auto()  # original event was positive direction
    negative_trigger = enum.auto()  # original event was negative direction


# Todo: add slots=True as soon as python 3.10 is in common distros
@dataclass(frozen=True)
class InputEvent:
    """The evnet used by inputremapper

    as a drop in replacement for evdev.InputEvent
    """

    message_type = MessageType.selected_event

    sec: int
    usec: int
    type: int
    code: int
    value: int
    actions: Tuple[EventActions, ...] = ()

    def __hash__(self):
        return hash((self.type, self.code, self.value))

    def __eq__(self, other: Any):
        if isinstance(other, InputEvent) or isinstance(other, evdev.InputEvent):
            return self.event_tuple == (other.type, other.code, other.value)
        if isinstance(other, tuple):
            return self.event_tuple == other
        return False

    @classmethod
    def __get_validators__(cls):
        """Used by pydantic and EventCombination to create InputEvent objects."""
        yield cls.validate

    @classmethod
    def validate(cls, init_arg: InputEventValidationType) -> InputEvent:
        """Try all the different methods, and raise an error if none succeed."""
        if isinstance(init_arg, InputEvent):
            return init_arg

        event = None
        validators: Sequence[Callable[..., InputEvent]] = (
            cls.from_event,
            cls.from_string,
            cls.from_tuple,
        )
        for validator in validators:
            try:
                event = validator(init_arg)
                break
            except InputEventCreationError:
                pass

        if event:
            return event

        raise ValueError(f"failed to create InputEvent with {init_arg = }")

    @classmethod
    def from_event(cls, event: evdev.InputEvent) -> InputEvent:
        """Create a InputEvent from another InputEvent or evdev.InputEvent."""
        try:
            return cls(event.sec, event.usec, event.type, event.code, event.value)
        except AttributeError as exception:
            raise InputEventCreationError(
                f"Failed to create InputEvent from {event = }"
            ) from exception

    @classmethod
    def from_string(cls, string: str) -> InputEvent:
        """Create a InputEvent from a string like 'type, code, value'."""
        try:
            t, c, v = string.split(",")
            return cls(0, 0, int(t), int(c), int(v))
        except (ValueError, AttributeError):
            raise InputEventCreationError(
                f"Failed to create InputEvent from {string = !r}"
            )

    @classmethod
    def from_tuple(cls, event_tuple: Tuple[int, int, int]) -> InputEvent:
        """Create a InputEvent from a (type, code, value) tuple."""
        try:
            if len(event_tuple) != 3:
                raise InputEventCreationError(
                    f"failed to create InputEvent {event_tuple = }"
                    f" must have length 3"
                )
            return cls(
                0,
                0,
                int(event_tuple[0]),
                int(event_tuple[1]),
                int(event_tuple[2]),
            )
        except ValueError as exception:
            raise InputEventCreationError(
                f"Failed to create InputEvent from {event_tuple = }"
            ) from exception
        except TypeError as exception:
            raise InputEventCreationError(
                f"Failed to create InputEvent from {type(event_tuple) = }"
            ) from exception

    @classmethod
    def btn_left(cls):
        return cls(0, 0, evdev.ecodes.EV_KEY, evdev.ecodes.BTN_LEFT, 1)

    @property
    def type_and_code(self) -> Tuple[int, int]:
        """Event type, code."""
        return self.type, self.code

    @property
    def event_tuple(self) -> Tuple[int, int, int]:
        """Event type, code, value."""
        return self.type, self.code, self.value

    @property
    def is_key_event(self) -> bool:
        """Whether this is interpreted as a key event."""
        return self.type == evdev.ecodes.EV_KEY or EventActions.as_key in self.actions

    @property
    def is_wheel_event(self) -> bool:
        """Whether this is interpreted as a key event."""
        return self.type == evdev.ecodes.EV_REL and self.code in [
            ecodes.REL_WHEEL,
            ecodes.REL_HWHEEL,
        ]

    @property
    def is_wheel_hi_res_event(self) -> bool:
        """Whether this is interpreted as a key event."""
        return self.type == evdev.ecodes.EV_REL and self.code in [
            ecodes.REL_WHEEL_HI_RES,
            ecodes.REL_HWHEEL_HI_RES,
        ]

    def __str__(self):
        return f"InputEvent{self.event_tuple}"

    def description(self, exclude_threshold=False, exclude_direction=False) -> str:
        """Get a human-readable description of the event."""
        return (
            f"{self.get_name()} "
            f"{self.get_direction() if not exclude_direction else ''} "
            f"{self.get_threshold() if not exclude_threshold else ''}".strip()
        )

    def timestamp(self):
        """Return the unix timestamp of when the event was seen."""
        return self.sec + self.usec / 1000000

    def modify(
        self,
        sec: Optional[int] = None,
        usec: Optional[int] = None,
        type_: Optional[int] = None,
        code: Optional[int] = None,
        value: Optional[int] = None,
        actions: Tuple[EventActions, ...] = None,
    ) -> InputEvent:
        """Return a new modified event."""
        return InputEvent(
            sec if sec is not None else self.sec,
            usec if usec is not None else self.usec,
            type_ if type_ is not None else self.type,
            code if code is not None else self.code,
            value if value is not None else self.value,
            actions if actions is not None else self.actions,
        )

    def json_key(self) -> str:
        return ",".join([str(self.type), str(self.code), str(self.value)])

    def get_name(self) -> Optional[str]:
        """Human-readable name."""
        if self.type not in ecodes.bytype:
            logger.warning("Unknown type for %s", self)
            return f"unknown {self.type, self.code}"

        if self.code not in ecodes.bytype[self.type]:
            logger.warning("Unknown code for %s", self)
            return f"unknown {self.type, self.code}"

        key_name = None

        # first try to find the name in xmodmap to not display wrong
        # names due to the keyboard layout
        if self.type == ecodes.EV_KEY:
            key_name = system_mapping.get_name(self.code)

        if key_name is None:
            # if no result, look in the linux combination constants. On a german
            # keyboard for example z and y are switched, which will therefore
            # cause the wrong letter to be displayed.
            key_name = ecodes.bytype[self.type][self.code]
            if isinstance(key_name, list):
                key_name = key_name[0]

        key_name = key_name.replace("ABS_Z", "Trigger Left")
        key_name = key_name.replace("ABS_RZ", "Trigger Right")

        key_name = key_name.replace("ABS_HAT0X", "DPad-X")
        key_name = key_name.replace("ABS_HAT0Y", "DPad-Y")
        key_name = key_name.replace("ABS_HAT1X", "DPad-2-X")
        key_name = key_name.replace("ABS_HAT1Y", "DPad-2-Y")
        key_name = key_name.replace("ABS_HAT2X", "DPad-3-X")
        key_name = key_name.replace("ABS_HAT2Y", "DPad-3-Y")

        key_name = key_name.replace("ABS_X", "Joystick-X")
        key_name = key_name.replace("ABS_Y", "Joystick-Y")
        key_name = key_name.replace("ABS_RX", "Joystick-RX")
        key_name = key_name.replace("ABS_RY", "Joystick-RY")

        key_name = key_name.replace("BTN_", "Button ")
        key_name = key_name.replace("KEY_", "")

        key_name = key_name.replace("REL_", "")
        key_name = key_name.replace("HWHEEL", "Wheel")
        key_name = key_name.replace("WHEEL", "Wheel")

        key_name = key_name.replace("_", " ")
        key_name = key_name.replace("  ", " ")
        return key_name

    def get_direction(self) -> str:
        if self.type == ecodes.EV_KEY:
            return ""

        try:
            event = self.modify(value=self.value // abs(self.value))
        except ZeroDivisionError:
            return ""

        return {
            # D-Pad
            (ecodes.ABS_HAT0X, -1): "Left",
            (ecodes.ABS_HAT0X, 1): "Right",
            (ecodes.ABS_HAT0Y, -1): "Up",
            (ecodes.ABS_HAT0Y, 1): "Down",
            (ecodes.ABS_HAT1X, -1): "Left",
            (ecodes.ABS_HAT1X, 1): "Right",
            (ecodes.ABS_HAT1Y, -1): "Up",
            (ecodes.ABS_HAT1Y, 1): "Down",
            (ecodes.ABS_HAT2X, -1): "Left",
            (ecodes.ABS_HAT2X, 1): "Right",
            (ecodes.ABS_HAT2Y, -1): "Up",
            (ecodes.ABS_HAT2Y, 1): "Down",
            # joystick
            (ecodes.ABS_X, 1): "Right",
            (ecodes.ABS_X, -1): "Left",
            (ecodes.ABS_Y, 1): "Down",
            (ecodes.ABS_Y, -1): "Up",
            (ecodes.ABS_RX, 1): "Right",
            (ecodes.ABS_RX, -1): "Left",
            (ecodes.ABS_RY, 1): "Down",
            (ecodes.ABS_RY, -1): "Up",
            # wheel
            (ecodes.REL_WHEEL, -1): "Down",
            (ecodes.REL_WHEEL, 1): "Up",
            (ecodes.REL_HWHEEL, -1): "Left",
            (ecodes.REL_HWHEEL, 1): "Right",
        }.get((event.code, event.value)) or ("+" if event.value > 0 else "-")

    def get_threshold(self) -> str:
        if self.value == 0:
            return ""
        return {
            ecodes.EV_REL: f"{abs(self.value)}",
            ecodes.EV_ABS: f"{abs(self.value)}%",
        }.get(self.type) or ""
