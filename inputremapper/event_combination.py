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

import itertools
from typing import Tuple, Iterable, Union, Callable, Sequence

from evdev import ecodes

from inputremapper.configs.system_mapping import system_mapping
from inputremapper.input_event import InputEvent, InputEventValidationType
from inputremapper.logger import logger

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


EventCombinationInitType = Union[
    InputEventValidationType,
    Iterable[InputEventValidationType],
]

EventCombinationValidatorType = Union[EventCombinationInitType, str]


class EventCombination(Tuple[InputEvent]):
    """One or multiple InputEvent objects for use as an unique identifier for mappings."""

    # tuple is immutable, therefore we need to override __new__()
    # https://jfine-python-classes.readthedocs.io/en/latest/subclass-tuple.html
    def __new__(cls, events: EventCombinationInitType) -> EventCombination:
        validated_events = []
        try:
            validated_events.append(InputEvent.validate(events))

        except ValueError:
            for event in events:
                validated_events.append(InputEvent.validate(event))

        # mypy bug: https://github.com/python/mypy/issues/8957
        # https://github.com/python/mypy/issues/8541
        return super().__new__(cls, validated_events)  # type: ignore

    def __str__(self):
        #  only used in tests and logging
        return f"<EventCombination {', '.join([str(e.event_tuple) for e in self])}>"

    @classmethod
    def __get_validators__(cls):
        """Used by pydantic to create EventCombination objects."""
        yield cls.validate

    @classmethod
    def validate(cls, init_arg: EventCombinationValidatorType) -> EventCombination:
        """Try all the different methods, and raise an error if none succeed."""
        if isinstance(init_arg, EventCombination):
            return init_arg

        combi = None
        validators: Sequence[Callable[..., EventCombination]] = (cls.from_string, cls)
        for validator in validators:
            try:
                combi = validator(init_arg)
                break
            except ValueError:
                pass

        if combi:
            return combi
        raise ValueError(f"failed to create EventCombination with {init_arg = }")

    @classmethod
    def from_string(cls, init_string: str) -> EventCombination:
        """Create a EventCombination form a string like '1,2,3+4,5,6'."""
        try:
            init_strs = init_string.split("+")
            return cls(init_strs)
        except AttributeError:
            raise ValueError(f"failed to create EventCombination from {init_string = }")

    @classmethod
    def empty_combination(cls) -> EventCombination:
        """a combination that has default invalid (to evdev) values useful for the
        UI to indicate that this combination is not set"""
        return cls("99,99,99")

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
            permutations.append(EventCombination((*permutation, self[-1])))

        return permutations

    def json_str(self) -> str:
        return "+".join([event.json_str() for event in self])

    def beautify(self) -> str:
        """Get a human readable string representation."""
        result = []

        if self == EventCombination.empty_combination():
            return "empty_combination"

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
