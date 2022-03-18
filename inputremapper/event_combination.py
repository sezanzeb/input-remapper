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

import inspect
import itertools

from typing import Tuple, Iterable

import evdev
from evdev import ecodes

from inputremapper.logger import logger
from inputremapper.configs.system_mapping import system_mapping
from inputremapper.input_event import InputEvent
from inputremapper.exceptions import InputEventCreationError

# having shift in combinations modifies the configured output,
# ctrl might not work at all
DIFFICULT_COMBINATIONS = [
    ecodes.KEY_LEFTSHIFT,
    ecodes.KEY_RIGHTSHIFT,
    ecodes.KEY_LEFTCTRL,
    ecodes.KEY_RIGHTCTRL,
    ecodes.KEY_LEFTALT,
    ecodes.KEY_RIGHTALT,
]


class EventCombination(Tuple[InputEvent]):
    """one or multiple InputEvent objects for use as an unique identifier for mappings"""

    # tuple is immutable, therefore we need to override __new__()
    # https://jfine-python-classes.readthedocs.io/en/latest/subclass-tuple.html
    def __new__(cls, *init_args) -> EventCombination:
        pydantic_internal = False
        events = []
        if inspect.isgenerator(init_args[0]):  # for some reason isinstance() does not work
            # pydantic might call this with a generator which yields input events
            for event in init_args[0]:
                if isinstance(event, InputEvent):
                    events.append(event)
                    pydantic_internal = True
        if pydantic_internal:
            return super().__new__(cls, events)

        for init_arg in init_args:
            events.append(InputEvent.validate(init_arg))

        return super().__new__(cls, events)

    def __str__(self):
        #  only used in tests and logging
        return f"<EventCombination {', '.join([str(e.event_tuple) for e in self])}>"

    @classmethod
    def __get_validators__(cls):
        """used by pydantic to create EventCombination objects"""
        yield cls.validate

    @classmethod
    def validate(cls, init_arg) -> EventCombination:
        """try all the different methods, and raise an error if none succeed"""
        if isinstance(init_arg, EventCombination):
            return init_arg

        combi = None
        for constructor in [cls.from_string, cls.from_events]:
            try:
                combi = constructor(init_arg)
                break
            except ValueError:
                pass

        if combi:
            return combi
        raise ValueError(f"failed to create EventCombination with {init_arg = }")

    @classmethod
    def from_string(cls, init_string: str) -> EventCombination:
        """create a EventCombination form a string like '1,2,3+4,5,6'"""
        try:
            init_args = init_string.split("+")
            return cls(*init_args)
        except (ValueError, AttributeError):
            raise ValueError(f"failed to create EventCombination from {init_string = }")

    @classmethod
    def from_events(
            cls,
            init_events: Iterable[InputEvent | evdev.InputEvent]
    ) -> EventCombination:
        """create a EventCombination from an iterable of InputEvents"""
        try:
            return cls(*init_events)
        except ValueError:
            raise ValueError(f"failed to create EventCombination form {init_events = }")

    def contains_type_and_code(self, type, code) -> bool:
        """if a InputEvent contains the type and code"""
        for event in self:
            if event.type_and_code == (type, code):
                return True
        return False

    def is_problematic(self):
        """Is this combination going to work properly on all systems?"""
        if len(self) <= 1:
            return False

        for event in self:
            if event.type != ecodes.EV_KEY:
                continue

            if event.code in DIFFICULT_COMBINATIONS:
                return True

        return False

    def get_permutations(self):
        """Get a list of EventCombination objects representing all possible permutations.

        combining a + b + c should have the same result as b + a + c.
        Only the last combination remains the same in the returned result.
        """
        if len(self) <= 2:
            return [self]

        permutations = []
        for permutation in itertools.permutations(self[:-1]):
            permutations.append(EventCombination(*permutation, self[-1]))

        return permutations

    def json_str(self) -> str:
        return "+".join([event.json_str() for event in self])

    def beautify(self) -> str:
        """Get a human readable string representation."""
        result = []

        for event in self:

            if event.type not in ecodes.bytype:
                logger.error("Unknown type for %s", event)
                result.append(str(event.code))
                continue

            if event.code not in ecodes.bytype[event.type]:
                logger.error("Unknown combination code for %s", event)
                result.append(str(event.code))
                continue

            key_name = None

            # first try to find the name in xmodmap to not display wrong
            # names due to the keyboard layout
            if event.type == ecodes.EV_KEY:
                key_name = system_mapping.get_name(event.code)

            if key_name is None:
                # if no result, look in the linux combination constants. On a german
                # keyboard for example z and y are switched, which will therefore
                # cause the wrong letter to be displayed.
                key_name = ecodes.bytype[event.type][event.code]
                if isinstance(key_name, list):
                    key_name = key_name[0]

            if event.type != ecodes.EV_KEY:
                direction = {
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
                }.get((event.code, event.value))
                if direction is not None:
                    key_name += f" {direction}"

            key_name = key_name.replace("ABS_Z", "Trigger Left")
            key_name = key_name.replace("ABS_RZ", "Trigger Right")

            key_name = key_name.replace("ABS_HAT0X", "DPad")
            key_name = key_name.replace("ABS_HAT0Y", "DPad")
            key_name = key_name.replace("ABS_HAT1X", "DPad 2")
            key_name = key_name.replace("ABS_HAT1Y", "DPad 2")
            key_name = key_name.replace("ABS_HAT2X", "DPad 3")
            key_name = key_name.replace("ABS_HAT2Y", "DPad 3")

            key_name = key_name.replace("ABS_X", "Joystick")
            key_name = key_name.replace("ABS_Y", "Joystick")
            key_name = key_name.replace("ABS_RX", "Joystick 2")
            key_name = key_name.replace("ABS_RY", "Joystick 2")

            key_name = key_name.replace("BTN_", "Button ")
            key_name = key_name.replace("KEY_", "")

            key_name = key_name.replace("REL_", "")
            key_name = key_name.replace("HWHEEL", "Wheel")
            key_name = key_name.replace("WHEEL", "Wheel")

            key_name = key_name.replace("_", " ")
            key_name = key_name.replace("  ", " ")

            result.append(key_name)

        return " + ".join(result)
