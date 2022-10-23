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
from typing import Optional, Callable, Tuple, TypeVar, Literal, Union

import evdev
import pkg_resources
from evdev.ecodes import (
    EV_KEY,
    EV_ABS,
    EV_REL,
    REL_WHEEL,
    REL_HWHEEL,
    REL_HWHEEL_HI_RES,
    REL_WHEEL_HI_RES,
)
from pydantic import (
    BaseModel,
    PositiveInt,
    confloat,
    conint,
    root_validator,
    validator,
    ValidationError,
    PositiveFloat,
    VERSION,
    BaseConfig,
)

from inputremapper.configs.system_mapping import system_mapping, DISABLE_NAME
from inputremapper.event_combination import EventCombination
from inputremapper.exceptions import MacroParsingError
from inputremapper.gui.gettext import _
from inputremapper.gui.messages.message_types import MessageType
from inputremapper.injection.macros.parse import is_this_a_macro, parse
from inputremapper.input_event import InputEvent, EventActions, USE_AS_ANALOG_VALUE

# TODO: remove pydantic VERSION check as soon as we no longer support
#  Ubuntu 20.04 and with it the ancient pydantic 1.2

needs_workaround = pkg_resources.parse_version(
    str(VERSION)
) < pkg_resources.parse_version("1.7.1")


EMPTY_MAPPING_NAME = _("Empty Mapping")


class KnownUinput(str, enum.Enum):
    keyboard = "keyboard"
    mouse = "mouse"
    gamepad = "gamepad"
    keyboard_mouse = "keyboard + mouse"


CombinationChangedCallback = Optional[
    Callable[[EventCombination, EventCombination], None]
]
MappingModel = TypeVar("MappingModel", bound="Mapping")


class Cfg(BaseConfig):
    validate_assignment = True
    use_enum_values = True
    underscore_attrs_are_private = True
    json_encoders = {EventCombination: lambda v: v.json_key()}


class ImmutableCfg(Cfg):
    allow_mutation = False


class UIMapping(BaseModel):
    """Holds all the data for mapping an input action to an output action.

    This mapping does not validate the structure of the mapping or macros, only basic
    values. It is meant to be used in the GUI where invalid mappings are expected.
    """

    if needs_workaround:
        __slots__ = ("_combination_changed",)

    # Required attributes
    # The InputEvent or InputEvent combination which is mapped
    event_combination: EventCombination = EventCombination.empty_combination()
    # The UInput to which the mapped event will be sent
    target_uinput: Optional[Union[str, KnownUinput]] = None

    # Either `output_symbol` or `output_type` and `output_code` is required
    output_symbol: Optional[str] = None  # The symbol or macro string if applicable
    output_type: Optional[int] = None  # The event type of the mapped event
    output_code: Optional[int] = None  # The event code of the mapped event

    name: Optional[str] = None
    mapping_type: Optional[Literal["key_macro", "analog"]] = None

    # if release events will be sent to the forwarded device as soon as a combination
    # triggers see also #229
    release_combination_keys: bool = True

    # macro settings
    macro_key_sleep_ms: conint(ge=0) = 0  # type: ignore

    # Optional attributes for mapping Axis to Axis
    # The deadzone of the input axis
    deadzone: confloat(ge=0, le=1) = 0.1  # type: ignore
    gain: float = 1.0  # The scale factor for the transformation
    # The expo factor for the transformation
    expo: confloat(ge=-1, le=1) = 0  # type: ignore

    # when mapping to relative axis

    # frequency in Hz for REL_X/Y event generation
    rel_xy_rate: PositiveInt = 60
    # frequency in Hz for REL_WHEEL and REL_WHEEL_HI_RES event generation
    rel_wheel_rate: PositiveInt = 60

    # the base speed of the relative axis, compounds with the gain.
    # values are observed normal output values in evtest
    rel_xy_speed: PositiveInt = 30
    rel_wheel_speed: PositiveInt = 1
    rel_wheel_hi_res_speed: PositiveInt = 120

    # when mapping from a relative axis:
    # the absolute value at which a EV_REL axis is considered at its maximum.
    # values are from evtest when moving the input quickly
    rel_xy_max_input: PositiveInt = 100
    rel_wheel_max_input: PositiveInt = 3
    rel_wheel_hi_res_max_input: PositiveInt = 360

    # the time until a relative axis is considered stationary if no new events arrive
    release_timeout: PositiveFloat = 0.05
    # don't release immediately when a relative axis drops below the speed threshold
    # instead wait until it dropped for loger than release_timeout below the threshold
    force_release_timeout: bool = False

    # callback which gets called if the event_combination is updated
    if not needs_workaround:
        _combination_changed: CombinationChangedCallback = None

    # use type: ignore, looks like a mypy bug related to:
    # https://github.com/samuelcolvin/pydantic/issues/2949
    def __init__(self, **kwargs):  # type: ignore
        super().__init__(**kwargs)
        if needs_workaround:
            object.__setattr__(self, "_combination_changed", None)

    def __setattr__(self, key, value):
        """Call the combination changed callback
        if we are about to update the event_combination
        """
        if key != "event_combination" or self._combination_changed is None:
            if key == "_combination_changed" and needs_workaround:
                object.__setattr__(self, "_combination_changed", value)
                return
            super(UIMapping, self).__setattr__(key, value)
            return

        # the new combination is not yet validated
        try:
            new_combi = EventCombination.validate(value)
        except ValueError:
            raise ValidationError(
                f"failed to Validate {value} as EventCombination", UIMapping
            )

        if new_combi == self.event_combination:
            return

        # raises a keyError if the combination or a permutation is already mapped
        self._combination_changed(new_combi, self.event_combination)
        super(UIMapping, self).__setattr__(key, value)

    def __str__(self):
        return str(
            self.dict(
                exclude_defaults=True, include={"event_combination", "target_uinput"}
            )
        )

    if needs_workaround:
        # https://github.com/samuelcolvin/pydantic/issues/1383
        def copy(self: MappingModel, *args, **kwargs) -> MappingModel:
            kwargs["deep"] = True
            copy = super(UIMapping, self).copy(*args, **kwargs)
            object.__setattr__(copy, "_combination_changed", self._combination_changed)
            return copy

    def format_name(self) -> str:
        """Get the custom-name or a readable representation of the combination."""
        if self.name:
            return self.name

        if (
            self.event_combination == EventCombination.empty_combination()
            or self.event_combination is None
        ):
            return EMPTY_MAPPING_NAME

        return self.event_combination.beautify()

    def has_input_defined(self) -> bool:
        """Whether this mapping defines an event-input."""
        return self.event_combination != EventCombination.empty_combination()

    def is_axis_mapping(self) -> bool:
        """whether this mapping specifies an output axis"""
        return self.output_type == EV_ABS or self.output_type == EV_REL

    def find_analog_input_event(
        self, type_: Optional[int] = None
    ) -> Optional[InputEvent]:
        """Return the first event that is configured with "Use as analog"."""
        for event in self.event_combination:
            if event.value == USE_AS_ANALOG_VALUE:
                if type_ is not None and event.type != type_:
                    continue

                return event

        return None

    def is_wheel_output(self) -> bool:
        return self.output_code in (
            REL_WHEEL,
            REL_HWHEEL,
        )

    def is_high_res_wheel_output(self) -> bool:
        return self.output_code in (
            REL_WHEEL_HI_RES,
            REL_HWHEEL_HI_RES,
        )

    def set_combination_changed_callback(self, callback: CombinationChangedCallback):
        self._combination_changed = callback

    def remove_combination_changed_callback(self):
        self._combination_changed = None

    def get_output_type_code(self) -> Optional[Tuple[int, int]]:
        """Returns the output_type and output_code if set,
        otherwise looks the output_symbol up in the system_mapping
        return None for unknown symbols and macros
        """
        if self.output_code and self.output_type:
            return self.output_type, self.output_code
        if not is_this_a_macro(self.output_symbol):
            return EV_KEY, system_mapping.get(self.output_symbol)
        return None

    def get_output_name_constant(self) -> bool:
        """Get the evdev name costant for the output."""
        return evdev.ecodes.bytype[self.output_type][self.output_code]

    def is_valid(self) -> bool:
        """If the mapping is valid."""
        return not self.get_error()

    def get_error(self) -> Optional[ValidationError]:
        """The validation error or None."""
        try:
            Mapping(**self.dict())
        except ValidationError as e:
            return e
        return None

    def get_bus_message(self) -> MappingData:
        """return an immutable copy for use in the message broker"""
        return MappingData(**self.dict())

    @root_validator
    def validate_mapping_type(cls, values):
        """overrides the mapping type if the output mapping type is obvious"""
        output_type = values.get("output_type")
        output_code = values.get("output_code")
        output_symbol = values.get("output_symbol")

        if output_type is not None and output_code is not None and not output_symbol:
            values["mapping_type"] = "analog"

        if output_type is None and output_code is None and output_symbol:
            values["mapping_type"] = "key_macro"

        return values

    Config = Cfg


class Mapping(UIMapping):
    """Holds all the data for mapping an input action to an output action.

    This implements the missing validations from UIMapping.
    """

    # Override Required attributes to enforce they are set
    event_combination: EventCombination
    target_uinput: KnownUinput

    def is_valid(self) -> bool:
        """If the mapping is valid."""
        return True

    @validator("output_symbol", pre=True)
    def validate_symbol(cls, symbol):
        if not symbol:
            return None

        if is_this_a_macro(symbol):
            try:
                parse(symbol, verbose=False)  # raises MacroParsingError
                return symbol
            except MacroParsingError as e:
                raise ValueError(
                    e
                )  # pydantic only catches ValueError, TypeError, and AssertionError

        if system_mapping.get(symbol) is not None:
            return symbol
        raise ValueError(
            f'the output_symbol "{symbol}" is not a macro and not a valid keycode-name'
        )

    @validator("event_combination")
    def only_one_analog_input(cls, combination) -> EventCombination:
        """Check that the event_combination specifies a maximum of one
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
        """Check if the trigger point for mapping analog axis to buttons is valid."""
        for event in combination:
            if event.type == EV_ABS and abs(event.value) >= 100:
                raise ValueError(
                    f"{event = } maps a absolute axis to a button, but the trigger "
                    f"point (event.value) is not between -100[%] and 100[%]"
                )
        return combination

    @validator("event_combination")
    def set_event_actions(cls, combination):
        """Sets the correct actions for each event."""
        new_combination = []
        for event in combination:
            if event.value != 0:
                event = event.modify(actions=(EventActions.as_key,))
            new_combination.append(event)
        return EventCombination(new_combination)

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
                    f"output_symbol is a macro: output_type "
                    f"and output_code must be None"
                )

        if code is not None and code != system_mapping.get(symbol) or type_ != EV_KEY:
            raise ValueError(
                f"output_symbol and output_code mismatch: "
                f"output macro is {symbol} --> {system_mapping.get(symbol)} "
                f"but output_code is {code} --> {system_mapping.get_name(code)} "
            )
        return values

    @root_validator
    def output_matches_input(cls, values):
        """Validate that an output type is an axis if we have an input axis.
        And vice versa"""
        combination: EventCombination = values.get("event_combination")
        event_values = [event.value for event in combination]

        output_type = values.get("output_type")
        output_symbol = values.get("output_symbol")

        use_as_analog = USE_AS_ANALOG_VALUE in event_values

        if not use_as_analog and not output_symbol and output_type != EV_KEY:
            raise ValueError(
                f"missing macro or key: "
                f"the {combination = } is not used as analog input, "
                f"but no output macro or key is programmed"
            )

        if (
            use_as_analog
            and output_type not in (EV_ABS, EV_REL)
            and output_symbol != DISABLE_NAME
        ):
            raise ValueError(
                f"missing output axis: "
                f"the {combination = } is used as analog input, "
                f"but the {output_type = } is not an axis "
            )

        return values


class MappingData(UIMapping):
    Config = ImmutableCfg
    message_type = MessageType.mapping  # allow this to be sent over the MessageBroker

    def __str__(self):
        return str(self.dict(exclude_defaults=True))

    def dict(self, *args, **kwargs):
        """will not include the message_type"""
        dict_ = super(MappingData, self).dict(*args, **kwargs)
        if "message_type" in dict_:
            del dict_["message_type"]
        return dict_
