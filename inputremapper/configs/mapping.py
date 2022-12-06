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
from typing import Optional, Callable, Tuple, TypeVar, Literal, Union, Any, Dict

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

from inputremapper.configs.input_config import InputCombination
from inputremapper.configs.system_mapping import system_mapping, DISABLE_NAME
from inputremapper.exceptions import MacroParsingError
from inputremapper.gui.gettext import _
from inputremapper.gui.messages.message_types import MessageType
from inputremapper.injection.macros.parse import is_this_a_macro, parse

# TODO: remove pydantic VERSION check as soon as we no longer support
#  Ubuntu 20.04 and with it the ancient pydantic 1.2

needs_workaround = pkg_resources.parse_version(
    str(VERSION)
) < pkg_resources.parse_version("1.7.1")


EMPTY_MAPPING_NAME: str = _("Empty Mapping")

# If `1` is the default speed for EV_REL, how much does this value needs to be scaled
# up to get reasonable speeds for various EV_REL events?
# Mouse injection rates vary wildly, and so do the values.
REL_XY_SCALING: float = 60
WHEEL_SCALING: float = 1
# WHEEL_HI_RES always generates events with 120 times higher values than WHEEL
# https://www.kernel.org/doc/html/latest/input/event-codes.html?highlight=wheel_hi_res#ev-rel
WHEEL_HI_RES_SCALING: float = 120
# Those values are assuming a rate of 60hz
DEFAULT_REL_RATE: float = 60


class KnownUinput(str, enum.Enum):
    """The default targets."""

    KEYBOARD = "keyboard"
    MOUSE = "mouse"
    GAMEPAD = "gamepad"
    KEYBOARD_MOUSE = "keyboard + mouse"


CombinationChangedCallback = Optional[
    Callable[[InputCombination, InputCombination], None]
]
MappingModel = TypeVar("MappingModel", bound="UIMapping")


class Cfg(BaseConfig):
    validate_assignment = True
    use_enum_values = True
    underscore_attrs_are_private = True
    json_encoders = {InputCombination: lambda v: v.json_key()}


class ImmutableCfg(Cfg):
    allow_mutation = False


class UIMapping(BaseModel):
    """Holds all the data for mapping an input action to an output action.

    The Preset contains multiple UIMappings.

    This mapping does not validate the structure of the mapping or macros, only basic
    values. It is meant to be used in the GUI where invalid mappings are expected.
    """

    if needs_workaround:
        __slots__ = ("_combination_changed",)

    # Required attributes
    # The InputEvent or InputEvent combination which is mapped
    input_combination: InputCombination = InputCombination.empty_combination()
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
    # The frequency [Hz] at which EV_REL events get generated
    rel_rate: PositiveInt = 60

    # when mapping from a relative axis:
    # the relative value at which a EV_REL axis is considered at its maximum. Moving
    # a mouse at 2x the regular speed would be considered max by default.
    rel_to_abs_input_cutoff: PositiveInt = 2

    # the time until a relative axis is considered stationary if no new events arrive
    release_timeout: PositiveFloat = 0.05
    # don't release immediately when a relative axis drops below the speed threshold
    # instead wait until it dropped for loger than release_timeout below the threshold
    force_release_timeout: bool = False

    # callback which gets called if the input_combination is updated
    if not needs_workaround:
        _combination_changed: Optional[CombinationChangedCallback] = None

    # use type: ignore, looks like a mypy bug related to:
    # https://github.com/samuelcolvin/pydantic/issues/2949
    def __init__(self, **kwargs):  # type: ignore
        super().__init__(**kwargs)
        if needs_workaround:
            object.__setattr__(self, "_combination_changed", None)

    def __setattr__(self, key: str, value: Any):
        """Call the combination changed callback
        if we are about to update the input_combination
        """
        if key != "input_combination" or self._combination_changed is None:
            if key == "_combination_changed" and needs_workaround:
                object.__setattr__(self, "_combination_changed", value)
                return
            super().__setattr__(key, value)
            return

        # the new combination is not yet validated
        try:
            new_combi = InputCombination.validate(value)
        except (ValueError, TypeError) as exception:
            raise ValidationError(
                f"failed to Validate {value} as InputCombination", UIMapping
            ) from exception

        if new_combi == self.input_combination:
            return

        # raises a keyError if the combination or a permutation is already mapped
        self._combination_changed(new_combi, self.input_combination)
        super().__setattr__("input_combination", new_combi)

    def __str__(self):
        return str(
            self.dict(
                exclude_defaults=True, include={"input_combination", "target_uinput"}
            )
        )

    if needs_workaround:
        # https://github.com/samuelcolvin/pydantic/issues/1383
        def copy(self: MappingModel, *args, **kwargs) -> MappingModel:
            kwargs["deep"] = True
            copy = super().copy(*args, **kwargs)
            object.__setattr__(copy, "_combination_changed", self._combination_changed)
            return copy

    def format_name(self) -> str:
        """Get the custom-name or a readable representation of the combination."""
        if self.name:
            return self.name

        if (
            self.input_combination == InputCombination.empty_combination()
            or self.input_combination is None
        ):
            return EMPTY_MAPPING_NAME

        return self.input_combination.beautify()

    def has_input_defined(self) -> bool:
        """Whether this mapping defines an event-input."""
        return self.input_combination != InputCombination.empty_combination()

    def is_axis_mapping(self) -> bool:
        """Whether this mapping specifies an output axis."""
        return self.output_type in [EV_ABS, EV_REL]

    def is_wheel_output(self) -> bool:
        """Check if this maps to wheel output."""
        return self.output_code in (
            REL_WHEEL,
            REL_HWHEEL,
        )

    def is_high_res_wheel_output(self) -> bool:
        """Check if this maps to high-res wheel output."""
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
        if self.output_symbol and not is_this_a_macro(self.output_symbol):
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
        except ValidationError as exception:
            return exception
        return None

    def get_bus_message(self) -> MappingData:
        """Return an immutable copy for use in the message broker."""
        return MappingData(**self.dict())

    @root_validator
    def validate_mapping_type(cls, values):
        """Overrides the mapping type if the output mapping type is obvious."""
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
    input_combination: InputCombination
    target_uinput: KnownUinput

    def is_valid(self) -> bool:
        """If the mapping is valid."""
        return True

    @validator("output_symbol", pre=True)
    def validate_symbol(cls, symbol):
        """Parse a macro to check for syntax errors."""
        if not symbol:
            return None

        symbol = symbol.strip()

        if is_this_a_macro(symbol):
            try:
                parse(symbol, verbose=False)  # raises MacroParsingError
                return symbol
            except MacroParsingError as exception:
                # pydantic only catches ValueError, TypeError, and AssertionError
                raise ValueError(exception) from exception

        if system_mapping.get(symbol) is not None:
            return symbol

        raise ValueError(
            f'The output_symbol "{symbol}" is not a macro and not a valid keycode-name'
        )

    @validator("input_combination")
    def only_one_analog_input(cls, combination) -> InputCombination:
        """Check that the input_combination specifies a maximum of one
        analog to analog mapping
        """
        analog_events = [event for event in combination if event.defines_analog_input]
        if len(analog_events) > 1:
            raise ValueError(
                f"Cannot map a combination of multiple analog inputs: {analog_events}"
                "add trigger points (event.value != 0) to map as a button"
            )

        return combination

    @validator("input_combination")
    def trigger_point_in_range(cls, combination: InputCombination) -> InputCombination:
        """Check if the trigger point for mapping analog axis to buttons is valid."""
        for input_config in combination:
            if (
                input_config.type == EV_ABS
                and input_config.analog_threshold
                and abs(input_config.analog_threshold) >= 100
            ):
                raise ValueError(
                    f"{input_config = } maps an absolute axis to a button, but the trigger "
                    "point (event.analog_threshold) is not between -100[%] and 100[%]"
                )
        return combination

    @root_validator
    def validate_output_symbol_variant(cls, values):
        """Validate that either type and code or symbol are set for key output."""
        o_symbol = values.get("output_symbol")
        o_type = values.get("output_type")
        o_code = values.get("output_code")
        if o_symbol is None and (o_type is None or o_code is None):
            raise ValueError(
                "Missing Argument: Mapping must either contain "
                "`output_symbol` or `output_type` and `output_code`"
            )
        return values

    @root_validator
    def validate_output_integrity(cls, values):
        """Validate the output key configuration."""
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
                    "output_symbol is a macro: output_type "
                    "and output_code must be None"
                )

        if code is not None and code != system_mapping.get(symbol) or type_ != EV_KEY:
            raise ValueError(
                "output_symbol and output_code mismatch: "
                f"output macro is {symbol} --> {system_mapping.get(symbol)} "
                f"but output_code is {code} --> {system_mapping.get_name(code)} "
            )
        return values

    @root_validator
    def output_matches_input(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that an output type is an axis if we have an input axis.
        And vice versa."""
        assert isinstance(values.get("input_combination"), InputCombination)
        combination: InputCombination = values["input_combination"]
        use_as_analog = True in [event.defines_analog_input for event in combination]

        output_type = values.get("output_type")
        output_symbol = values.get("output_symbol")

        if not use_as_analog and not output_symbol and output_type != EV_KEY:
            raise ValueError(
                "missing macro or key: "
                f'"{str(combination)}" is not used as analog input, '
                f"but no output macro or key is programmed"
            )

        if (
            use_as_analog
            and output_type not in (EV_ABS, EV_REL)
            and output_symbol != DISABLE_NAME
        ):
            raise ValueError(
                "Missing output axis: "
                f'"{str(combination)}" is used as analog input, '
                f"but the {output_type = } is not an axis "
            )

        return values


class MappingData(UIMapping):
    """Like UIMapping, but can be sent over the message broker."""

    Config = ImmutableCfg
    message_type = MessageType.mapping  # allow this to be sent over the MessageBroker

    def __str__(self):
        return str(self.dict(exclude_defaults=True))

    def dict(self, *args, **kwargs):
        """Will not include the message_type."""
        dict_ = super().dict(*args, **kwargs)
        if "message_type" in dict_:
            del dict_["message_type"]
        return dict_
