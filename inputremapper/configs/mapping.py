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
import enum
from evdev.ecodes import EV_KEY, EV_ABS, EV_REL
from pydantic import (
    BaseModel,
    PositiveInt,
    confloat,
    root_validator,
    validator,
    ValidationError,
    PositiveFloat,
    VERSION,
)
from typing import Optional, Callable, Tuple, Dict, Union

import pkg_resources

from inputremapper.event_combination import EventCombination
from inputremapper.configs.system_mapping import system_mapping
from inputremapper.exceptions import MacroParsingError
from inputremapper.injection.macros.parse import is_this_a_macro, parse
from inputremapper.input_event import EventActions

pydantic_version = pkg_resources.parse_version(str(VERSION))


# TODO: in python 3.11 inherit enum.StrEnum
class KnownUinput(str, enum.Enum):
    keyboard = "keyboard"
    mouse = "mouse"
    gamepad = "gamepad"


CombinationChangedCallback = Optional[
    Callable[[EventCombination, EventCombination], None]
]


class Mapping(BaseModel):
    """
    holds all the data for mapping an
    input action to an output action
    """

    # TODO: remove pydantic VERSION check as soon as we no longer support Ubuntu 20.04 and with it the ainchant pydantic 1.2
    if pydantic_version < pkg_resources.parse_version("1.7.1"):
        __slots__ = ("_combination_changed",)

    # Required attributes
    event_combination: EventCombination  # The InputEvent or InputEvent combination which is mapped
    target_uinput: KnownUinput  # The UInput to which the mapped event will be sent

    # Either `output_symbol` or `output_type` and `output_code` is required
    output_symbol: Optional[str] = None  # The symbol or macro string if applicable
    output_type: Optional[int] = None  # The event type of the mapped event
    output_code: Optional[int] = None  # The event code of the mapped event

    # macro settings
    macro_key_sleep_ms: PositiveInt = 20

    # Optional attributes for mapping Axis to Axis
    deadzone: confloat(ge=0, le=1) = 0.1  # The deadzone of the input axis
    gain: float = 1.0  # The scale factor for the transformation
    expo: confloat(ge=-1, le=1) = 0  # The expo factor for the transformation

    # when mapping to relative axis
    rate: PositiveInt = 60  # The frequency [Hz] at which EV_REL events get generated
    # the base speed of the relative axis, compounds with the gain
    rel_speed: PositiveInt = 100

    # when mapping from relative axis:
    # the absolute value at which a EV_REL axis is considered at its maximum
    rel_input_cutoff: PositiveInt = 100
    # the time until a relative axis is considered stationary if no new events arrive
    release_timeout: PositiveFloat = 0.05

    # callback which gets called if the event_combination is updated
    if pydantic_version >= pkg_resources.parse_version("1.7.1"):
        _combination_changed: CombinationChangedCallback = None
    else:

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            object.__setattr__(self, "_combination_changed", None)

    def __setattr__(self, key, value):
        """
        call the combination changed callback
        if we are about to update the event_combination
        """
        if key != "event_combination" or self._combination_changed is None:
            if (
                key == "_combination_changed"
                and pydantic_version < pkg_resources.parse_version("1.7.1")
            ):
                object.__setattr__(self, "_combination_changed", value)
                return
            super(Mapping, self).__setattr__(key, value)
            return

        # the new combination is not yet validated
        try:
            new_combi = EventCombination.validate(value)
        except ValueError:
            raise ValidationError(
                f"failed to Validate {value} as EventCombination", Mapping
            )

        if new_combi == self.event_combination:
            return

        # raises a keyError if the combination or a permutation is already mapped
        self._combination_changed(new_combi, self.event_combination)
        super(Mapping, self).__setattr__(key, value)

    def __str__(self):
        return str(self.dict(exclude_defaults=True))

    if pydantic_version < pkg_resources.parse_version("1.7.1"):
        def copy(self, *args, **kwargs) -> Mapping:
            copy = super(Mapping, self).copy(*args, **kwargs)
            object.__setattr__(copy, "_combination_changed", self._combination_changed)
            return copy

    def set_combination_changed_callback(self, callback: CombinationChangedCallback):
        self._combination_changed = callback

    def remove_combination_changed_callback(self):
        self._combination_changed = None

    def get_output_type_code(self) -> Optional[Tuple[int, int]]:
        """
        returns the output_type and output_code if set,
        otherwise looks the output_symbol up in the system_mapping
        return None for unknown symbols and macros
        """
        if self.output_code and self.output_type:
            return self.output_type, self.output_code
        if not is_this_a_macro(self.output_symbol):
            return EV_KEY, system_mapping.get(self.output_symbol)

    @staticmethod
    def is_valid() -> bool:
        """if the mapping is valid"""
        return True

    @validator("output_symbol", pre=True)
    def validate_symbol(cls, symbol):
        if not symbol:
            return None

        if is_this_a_macro(symbol):
            try:
                parse(symbol)  # raises MacroParsingError
                return symbol
            except MacroParsingError as e:
                raise ValueError(
                    e
                )  # pydantic only catches ValueError, TypeError, and AssertionError

        if system_mapping.get(symbol) is not None:
            return symbol
        raise ValueError(
            f"the output_symbol '{symbol}' is not a macro and not a valid keycode-name"
        )

    @validator("event_combination")
    def only_one_analog_input(cls, combination) -> EventCombination:
        """
        check that the event_combination specifies a maximum of one
        analog to analog mapping
        """

        # any event with a value of 0  is considered an analog input (even key events)
        # any event with a non-zero value is considered a binary input
        analog_events = [event for event in combination if event.value == 0]
        if len(analog_events) > 1:
            raise ValueError(
                f"cannot map a combination of multiple analog inputs: {analog_events}"
                f"add trigger points (event.value != 0) to map as a button"
            )

        return combination

    @validator("event_combination")
    def trigger_point_in_range(cls, combination) -> EventCombination:
        """
        check if the trigger point for mapping analog axis to buttons is valid
        """
        for event in combination:
            if event.type == EV_ABS and abs(event.value) >= 100:
                raise ValueError(
                    f"{event = } maps a absolute axis to a button, "
                    f"but the trigger point (event.value) is not between -100[%] and 100[%]"
                )
        return combination

    @validator("event_combination")
    def set_event_actions(cls, combination):
        """sets the correct action for each event"""
        new_combination = []
        for event in combination:
            if event.value != 0:
                event = event.modify(action=EventActions.as_key)
            new_combination.append(event)
        return EventCombination.from_events(new_combination)

    @root_validator
    def contains_output(cls, values):
        o_symbol = values.get("output_symbol")
        o_type = values.get("output_type")
        o_code = values.get("output_code")
        if o_symbol is None and (o_type is None or o_code is None):
            raise ValueError(
                "missing Argument: Mapping must either contain "
                "`output_symbol` or `output_type` and `output_code`"
            )
        return values

    @root_validator
    def validate_output_integrity(cls, values):
        symbol = values.get("output_symbol")
        type_ = values.get("output_type")
        code = values.get("output_code")
        if symbol is None:
            return values  # type and code can be anything

        if type_ is None and code is None:
            return values  # we have a symbol: no type and code is fine

        if is_this_a_macro(symbol):  # disallow output type and code for macros
            if type_ is not None or code is not None:
                raise ValueError(
                    f"output_symbol is a macro: output_type and output_code must be None"
                )

        if code is not None and code != system_mapping.get(symbol) or type_ != EV_KEY:
            raise ValueError(
                f"output_symbol and output_code mismatch: "
                f"output macro is {symbol} --> {system_mapping.get(symbol)} "
                f"but output_code is {code} --> {system_mapping.get_name(code)} "
            )
        return values

    @root_validator
    def output_axis_given(cls, values):
        """validate that an output type is an axis if we have an input axis"""
        combination = values.get("event_combination")
        output_type = values.get("output_type")
        event_values = [event.value for event in combination]
        if 0 not in event_values:
            return values

        if output_type not in (EV_ABS, EV_REL):
            raise ValueError(
                f"the {combination = } specifies a input axis, "
                f"but the {output_type = } is not an axis "
            )

        return values

    class Config:
        validate_assignment = True
        use_enum_values = True
        underscore_attrs_are_private = True

        json_encoders = {EventCombination: lambda v: v.json_str()}


class UIMapping(Mapping):
    """
    The UI Mapping adds the ability to create Invalid Mapping objects.
    For use in the frontend, where invalid data is allowed during creation of the mapping

    Invalid assignments are cached and revalidation is attempted as soon as the mapping changes
    """

    _cache: Dict[str, any]  # the invalid mapping data
    _last_error: Optional[ValidationError]  # the last validation error

    # all attributes that __setattr__ will not forward to super() or _cache
    ATTRIBUTES = ("_cache", "_last_error")

    def __init__(self, **data):
        object.__setattr__(self, "_last_error", None)
        super().__init__(
            event_combination="99,99,99",
            target_uinput="keyboard",
            output_symbol="KEY_A",
        )
        cache = {
            "event_combination": None,
            "target_uinput": None,
            "output_symbol": None,
        }
        cache.update(**data)
        object.__setattr__(self, "_cache", cache)
        self._validate()

    def __setattr__(self, key, value):
        if key in self.ATTRIBUTES:
            object.__setattr__(self, key, value)
            return

        try:
            super(UIMapping, self).__setattr__(key, value)
            if key in self._cache:
                del self._cache[key]

        except ValidationError as error:
            # cache the value
            self._last_error = error
            self._cache[key] = value

        # retry the validation
        self._validate()

    def __getattribute__(self, item):
        # intercept any getattribute and prioritize attributes from the cache
        try:
            return object.__getattribute__(self, "_cache")[item]
        except (KeyError, AttributeError):
            pass

        return object.__getattribute__(self, item)

    def is_valid(self) -> bool:
        """if the mapping is valid"""
        return len(self._cache) == 0

    def dict(self, *args, **kwargs):
        """dict will include the invalid data"""
        dict_ = super(UIMapping, self).dict(*args, **kwargs)
        # combine all valid values with the invalid ones
        dict_.update(**self._cache)
        if "ATTRIBUTES" in dict_:
            # remove so that super().__eq__ succeeds
            # for comparing Mapping with UIMapping
            del dict_["ATTRIBUTES"]

        if pydantic_version < pkg_resources.parse_version("1.7.1"):
            if "_last_error" in dict_.keys():
                del dict_["_last_error"]
                del dict_["_cache"]

        return dict_

    def get_error(self) -> Optional[ValidationError]:
        """the validation error or None"""
        return self._last_error

    def _validate(self) -> None:
        """try to validate the mapping"""
        if self.is_valid():
            return

        # preserve the combination_changed callback
        callback = self._combination_changed
        try:
            super(UIMapping, self).__init__(**self.dict(exclude_defaults=True))
            self._cache = {}
            self._last_error = None
            self.set_combination_changed_callback(callback)
            return
        except ValidationError as error:
            self._last_error = error

        if (
            "event_combination" in self._cache.keys()
            and self._cache["event_combination"]
        ):
            # the event_combination needs to be valid
            self._cache["event_combination"] = EventCombination.validate(
                self._cache["event_combination"]
            )
