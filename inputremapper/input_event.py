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
from __future__ import annotations

import evdev

from dataclasses import dataclass
from typing import Tuple

from inputremapper.exceptions import InputEventCreationError


@dataclass(
    frozen=True
)  # Todo: add slots=True as soon as python 3.10 is in common distros
class InputEvent:
    """
    the evnet used by inputremapper

    as a drop in replacement for evdev.InputEvent
    """

    sec: int
    usec: int
    type: int
    code: int
    value: int

    def __hash__(self):
        return hash((self.type, self.code, self.value))

    def __eq__(self, other):
        if isinstance(other, InputEvent) or isinstance(other, evdev.InputEvent):
            return self.event_tuple == (other.type, other.code, other.value)
        if isinstance(other, tuple):
            return self.event_tuple == other
        return False

    @classmethod
    def __get_validators__(cls):
        """used by pydantic and EventCombination to create InputEvent objects"""
        yield cls.from_event
        yield cls.from_tuple
        yield cls.from_string

    @classmethod
    def from_event(cls, event: evdev.InputEvent) -> InputEvent:
        """create a InputEvent from another InputEvent or evdev.InputEvent"""
        try:
            return cls(event.sec, event.usec, event.type, event.code, event.value)
        except AttributeError:
            raise InputEventCreationError(
                f"failed to create InputEvent from {event = }"
            )

    @classmethod
    def from_string(cls, string: str) -> InputEvent:
        """create a InputEvent from a string like 'type, code, value'"""
        try:
            t, c, v = string.split(",")
            return cls(0, 0, int(t), int(c), int(v))
        except (ValueError, AttributeError):
            raise InputEventCreationError(
                f"failed to create InputEvent from {string = !r}"
            )

    @classmethod
    def from_tuple(cls, event_tuple: Tuple[int, int, int]) -> InputEvent:
        """create a InputEvent from a (type, code, value) tuple"""
        try:
            if len(event_tuple) != 3:
                raise InputEventCreationError(
                    f"failed to create InputEvent {event_tuple = }"
                    f" must have length 3"
                )
            return cls(
                0, 0, int(event_tuple[0]), int(event_tuple[1]), int(event_tuple[2])
            )
        except ValueError:
            raise InputEventCreationError(
                f"failed to create InputEvent from {event_tuple = }"
            )
        except TypeError:
            raise InputEventCreationError(
                f"failed to create InputEvent from {type(event_tuple) = }"
            )

    @classmethod
    def btn_left(cls):
        return cls(0, 0, evdev.ecodes.EV_KEY, evdev.ecodes.BTN_LEFT, 1)

    @property
    def type_and_code(self) -> Tuple[int, int]:
        """event type, code"""
        return self.type, self.code

    @property
    def event_tuple(self) -> Tuple[int, int, int]:
        """event type, code, value"""
        return self.type, self.code, self.value

    def __str__(self):
        if self.type == evdev.ecodes.EV_KEY:
            key_name = evdev.ecodes.bytype[self.type].get(self.code, "unknown")
            action = "down" if self.value == 1 else "up"
            return f"<InputEvent {key_name} ({self.code}) {action}>"

        return f"<InputEvent {self.event_tuple}>"

    def timestamp(self):
        """Return the unix timestamp of when the event was seen."""
        return self.sec + self.usec / 1000000

    def modify(
        self,
        sec: int = None,
        usec: int = None,
        type: int = None,
        code: int = None,
        value: int = None,
    ) -> InputEvent:
        """return a new modified event"""
        return InputEvent(
            sec if sec is not None else self.sec,
            usec if usec is not None else self.usec,
            type if type is not None else self.type,
            code if code is not None else self.code,
            value if value is not None else self.value,
        )

    def json_str(self) -> str:
        return ",".join([str(self.type), str(self.code), str(self.value)])
