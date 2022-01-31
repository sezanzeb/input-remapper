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
from evdev.ecodes import EV_KEY
from pydantic import BaseModel, PositiveInt, confloat, root_validator, validator, ValidationError
from typing import Optional, Callable, Tuple

from inputremapper.event_combination import EventCombination
from inputremapper.configs.system_mapping import system_mapping
from inputremapper.injection.macros.parse import is_this_a_macro, parse


# TODO: in python 3.11 inherit enum.StrEnum
class KnownUinput(str, enum.Enum):
    keyboard = "keyboard"
    mouse = "mouse"
    gamepad = "gamepad"


CombinationChangedCallback = Optional[Callable[[EventCombination, EventCombination], None]]


class Mapping(BaseModel):
    """
    holds all the data for mapping an
    input action to an output action
    """

    # Required attributes
    event_combination: EventCombination  # The InputEvent or InputEvent combination which is mapped
    target_uinput: KnownUinput  # The UInput to which the mapped event will be sent

    # Either `output_symbol` or `output_type` and `output_code` is required
    output_symbol: Optional[str] = None  # The symbol or macro string if applicable
    output_type: Optional[int] = None  # The event type of the mapped event
    output_code: Optional[int] = None  # The event code of the mapped event

    # Optional attributes for mapping Axis to Axis
    deadzone: confloat(ge=0, le=1) = 0.1  # The deadzone of the input axis
    gain: float = 1.0  # The scale factor for the transformation
    expo: confloat(ge=-1, le=1) = 0  # The expo factor for the transformation

    # when mapping to relative axis
    rate: PositiveInt = 60  # The frequency [Hz] at which EV_REL events get generated

    # when mapping from relative axis:
    # the absolute value at which a EV_REL axis is considered at its maximum
    rel_input_cutoff: PositiveInt = 120
    # if no event arrives for more than the timeout the axis is considered stationary
    rel_reset_timeout_ms: PositiveInt = 20

    # callback which gets called if the
    _combination_changed: CombinationChangedCallback = None

    def __setattr__(self, key, value):
        """
        call the combination changed callback
        if we are about to update the event_combination
        """
        if key != "event_combination" or self._combination_changed is None:
            super(Mapping, self).__setattr__(key, value)
            return

        # the new combination is not yet validated
        try:
            new_combi = EventCombination.validate(value)
        except ValueError:
            raise ValidationError(f"failed to Validate {value} as EventCombination")

        if new_combi == self.event_combination:
            return

        self._combination_changed(new_combi, self.event_combination)
        super(Mapping, self).__setattr__(key, value)

    def set_combination_changed_callback(self, callback: CombinationChangedCallback):
        self._combination_changed = callback

    def remove_combination_changed_callback(self):
        self._combination_changed = None

    @property
    def output_type_and_code(self) -> Optional[Tuple[int, int]]:
        return self.output_type, self.output_code or None

    @validator("output_symbol", pre=True)
    @classmethod
    def validate_macro(cls, symbol):
        if symbol is None:
            return symbol

        if is_this_a_macro(symbol):
            parse(symbol)  # raises MacroParsingError
            return symbol

        if system_mapping.get(symbol) is not None:
            return symbol
        raise ValueError(
            f"the output_symbol '{symbol}' is not a macro and not a valid keycode-name"
        )

    @root_validator
    @classmethod
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
    @classmethod
    def validate_output_integrity(cls, values):
        o_symbol = values.get("output_symbol")
        o_type = values.get("output_type")
        o_code = values.get("output_code")
        if o_symbol is None:
            return values  # type and code can be anything

        if o_type is None and o_code is None:
            return values  # we have a symbol: no type and code is fine

        if is_this_a_macro(o_symbol):  # disallow output type and code for macros
            if o_type is not None or o_code is not None:
                raise ValueError(
                    f"output_symbol is a macro: output_type and output_code must be None"
                )

        if o_type is not None and o_type != EV_KEY:
            raise ValueError(
                f"output_type is not EV_KEY ({EV_KEY}) but output_symbol is not None."
            )

        if o_code is not None and o_code != system_mapping.get(o_symbol):
            raise ValueError(
                f"output_symbol and output_code mismatch: "
                f"output macro is {o_symbol} --> {system_mapping.get(o_symbol)} "
                f"but output_code is {o_code} --> {system_mapping.get_name(o_code)} "
            )
        return values

    class Config:
        validate_assignment = True
        use_enum_values = True
        underscore_attrs_are_private = True


        json_encoders = {
            EventCombination: lambda v: v.json_str()
        }
