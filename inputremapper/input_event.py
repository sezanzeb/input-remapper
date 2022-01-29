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
from dataclasses import dataclass
import evdev


@dataclass(frozen=True, slots=True)
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
        return (self.type, self.code, self.value) == (other.type, other.code, other.value)

    @classmethod
    def from_event(cls, event: evdev.InputEvent) -> InputEvent:
        """create a InputEvent from another InputEvent or evdev.InputEvent"""
        return cls(event.sec, event.usec, event.type, event.code, event.value)

    @classmethod
    def from_string(cls, string: str):
        """create a InputEvent from a string like 'type, code, value' """
        t, c, v = string.split(",")
        return cls(0, 0, int(t), int(c), int(v))

    @property
    def type_and_code(self):
        """event type, code"""
        return self.type, self.code

    @property
    def event_tuple(self):
        """event type, code, value"""
        return self.type, self.code, self.value

    def modify(self,
               sec: int = None,
               usec: int = None,
               type: int = None,
               code: int = None,
               value: int = None,
               ) -> InputEvent:
        """return modified event"""
        return InputEvent(
            sec or self.sec,
            usec or self.usec,
            type if type is not None else self.type,
            code if code is not None else self.code,
            value if value is not None else self.value,
        )