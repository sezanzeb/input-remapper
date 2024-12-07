# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2024 sezanzeb <b8x45ygc9@mozmail.com>
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
from typing import Tuple, Optional, Hashable, Literal

import evdev
from evdev import ecodes

from inputremapper.utils import get_evdev_constant_name, DeviceHash


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
    """Events that are generated during runtime.

    Is a drop-in replacement for evdev.InputEvent
    """

    sec: int
    usec: int
    type: int
    code: int
    value: int
    actions: Tuple[EventActions, ...] = ()
    origin_hash: Optional[DeviceHash] = None

    def __eq__(self, other: InputEvent | evdev.InputEvent | Tuple[int, int, int]):
        # useful in tests
        if isinstance(other, InputEvent) or isinstance(other, evdev.InputEvent):
            return self.event_tuple == (other.type, other.code, other.value)
        if isinstance(other, tuple):
            return self.event_tuple == other
        raise TypeError(f"cannot compare {type(other)} with InputEvent")

    @staticmethod
    def validate_event(event):
        """Test if the event is valid."""
        if not isinstance(event.type, int):
            raise TypeError(f"Expected type to be an int, but got {event.type}")

        if not isinstance(event.code, int):
            raise TypeError(f"Expected code to be an int, but got {event.code}")

        if not isinstance(event.value, int):
            # this happened to me because I screwed stuff up
            raise TypeError(f"Expected value to be an int, but got {event.value}")

        return event

    @property
    def input_match_hash(self) -> Hashable:
        """a Hashable object which is intended to match the InputEvent with a
        InputConfig.
        """
        return self.type, self.code, self.origin_hash

    @classmethod
    def from_event(
        cls,
        event: evdev.InputEvent,
        origin_hash: Optional[DeviceHash] = None,
    ) -> InputEvent:
        """Create a InputEvent from another InputEvent or evdev.InputEvent."""
        try:
            return cls(
                event.sec,
                event.usec,
                event.type,
                event.code,
                event.value,
                origin_hash=origin_hash,
            )
        except AttributeError as exception:
            raise TypeError(
                f"Failed to create InputEvent from {event = }"
            ) from exception

    @classmethod
    def from_tuple(
        cls,
        event_tuple: Tuple[int, int, int],
        origin_hash: Optional[DeviceHash] = None,
    ) -> InputEvent:
        """Create a InputEvent from a (type, code, value) tuple."""
        # use this as rarely as possible. Construct objects early on and pass them
        # around instead of passing around integers
        if len(event_tuple) != 3:
            raise TypeError(
                f"failed to create InputEvent {event_tuple = } must have length 3"
            )

        return cls.validate_event(
            cls(
                0,
                0,
                int(event_tuple[0]),
                int(event_tuple[1]),
                int(event_tuple[2]),
                origin_hash=origin_hash,
            )
        )

    @classmethod
    def abs(cls, code: int, value: int, origin_hash: Optional[DeviceHash] = None):
        """Create an abs event, like joystick movements."""
        return cls.validate_event(
            cls(
                0,
                0,
                ecodes.EV_ABS,
                code,
                value,
                origin_hash=origin_hash,
            )
        )

    @classmethod
    def rel(cls, code: int, value: int, origin_hash: Optional[str] = None):
        """Create a rel event, like mouse movements."""
        return cls.validate_event(
            cls(
                0,
                0,
                ecodes.EV_REL,
                code,
                value,
                origin_hash=origin_hash,
            )
        )

    @classmethod
    def key(cls, code: int, value: Literal[0, 1], origin_hash: Optional[str] = None):
        """Create a key event, like keyboard keys or gamepad buttons.

        A value of 1 means "press", a value of 0 means "release".
        """
        return cls.validate_event(
            cls(
                0,
                0,
                ecodes.EV_KEY,
                code,
                value,
                origin_hash=origin_hash,
            )
        )

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
        name = get_evdev_constant_name(self.type, self.code)
        return f"InputEvent for {self.event_tuple} {name}"

    def __repr__(self):
        return f"<{str(self)} at {hex(id(self))}>"

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
        actions: Optional[Tuple[EventActions, ...]] = None,
        origin_hash: Optional[str] = None,
    ) -> InputEvent:
        """Return a new modified event."""
        return InputEvent(
            sec if sec is not None else self.sec,
            usec if usec is not None else self.usec,
            type_ if type_ is not None else self.type,
            code if code is not None else self.code,
            value if value is not None else self.value,
            actions if actions is not None else self.actions,
            origin_hash=origin_hash if origin_hash is not None else self.origin_hash,
        )
