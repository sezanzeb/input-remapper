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
from typing import Tuple, Iterable, Union, Callable, Sequence, Optional

from evdev import ecodes

from inputremapper.input_event import (
    InputEvent,
    InputEventValidationType,
    USE_AS_ANALOG_VALUE,
)

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

        if len(validated_events) == 0:
            raise ValueError(f"failed to create EventCombination with {events = }")

        # mypy bug: https://github.com/python/mypy/issues/8957
        # https://github.com/python/mypy/issues/8541
        return super().__new__(cls, validated_events)  # type: ignore

    def __str__(self):
        return " + ".join(event.description(exclude_threshold=True) for event in self)

    def __repr__(self):
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

    def is_problematic(self) -> bool:
        """Is this combination going to work properly on all systems?"""
        if len(self) <= 1:
            return False

        for event in self:
            if event.type != ecodes.EV_KEY:
                continue

            if event.code in DIFFICULT_COMBINATIONS:
                return True

        return False

    def has_input_axis(self) -> bool:
        """Check if there is any analog event in self."""
        return False in (event.is_key_event for event in self)

    def find_analog_input_event(
        self, type_: Optional[int] = None
    ) -> Optional[InputEvent]:
        """Return the first event that is configured with "Use as analog"."""
        # TODO test
        for event in self:
            if event.value == USE_AS_ANALOG_VALUE:
                if type_ is not None and event.type != type_:
                    continue

                return event

        return None

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

    def json_key(self) -> str:
        """Get a representation of the input that works as key in a json object."""
        return "+".join([event.json_key() for event in self])

    def beautify(self) -> str:
        """Get a human readable string representation."""
        if self == EventCombination.empty_combination():
            return "empty_combination"
        return " + ".join(event.description(exclude_threshold=True) for event in self)
