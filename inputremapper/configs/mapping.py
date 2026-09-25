# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2026 sezanzeb <4t1pzast9@mozmail.com>
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
from collections.abc import Callable
from typing import Any

from evdev.ecodes import (
    EV_ABS,
    EV_KEY,
    EV_REL,
    REL_HWHEEL,
    REL_HWHEEL_HI_RES,
    REL_WHEEL,
    REL_WHEEL_HI_RES,
)

from inputremapper.logging.logger import logger

try:
    from pydantic.v1 import (
        VERSION,
        BaseConfig,
        BaseModel,
        PositiveFloat,
        PositiveInt,
        ValidationError,
        confloat,
        conint,
        root_validator,
        validator,
    )
except ImportError:
    from pydantic import (
        BaseConfig,
        BaseModel,
        PositiveFloat,
        PositiveInt,
        ValidationError,
        confloat,
        conint,
        root_validator,
    )


from inputremapper.configs.input_config import InputCombination
from inputremapper.configs.keyboard_layout import DISABLE_NAME, keyboard_layout
from inputremapper.configs.validation_errors import (
    MacroButTypeOrCodeSetError,
    MissingMacroOrKeyError,
    MissingOutputAxisError,
    OnlyOneAnalogInputError,
    OutputSymbolUnknownError,
    OutputSymbolVariantError,
    SymbolAndCodeMismatchError,
    SymbolNotAvailableInTargetError,
    TriggerPointInRangeError,
    WrongMappingTypeForKeyError,
)
from inputremapper.gui.components.output_type_names import OutputTypeNames
from inputremapper.gui.gettext import _
from inputremapper.injection.global_uinputs import GlobalUInputs
from inputremapper.injection.macros.parse import Parser
from inputremapper.utils import get_evdev_constant_name

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


class MappingType(str, enum.Enum):
    """What kind of output the mapping produces."""

    KEY_MACRO = "key_macro"
    ANALOG = "analog"


# TODO remove
CombinationChangedCallback = Callable[[InputCombination, InputCombination], None] | None


class Cfg(BaseConfig):
    validate_assignment = True
    use_enum_values = True
    underscore_attrs_are_private = True
    json_encoders = {InputCombination: lambda v: v.json_key()}


class Mapping(BaseModel):
    """Holds all the data for mapping an input action to an output action.

    The Preset contains multiple Mappings.

    This mapping does not validate the structure of the mapping or macros, only basic
    values. It is meant to be used in the GUI where invalid mappings are expected.
    """

    Config = Cfg

    # Required attributes
    # The InputEvent or InputEvent combination which is mapped
    input_combination: InputCombination = InputCombination.empty_combination()
    # The UInput to which the mapped event will be sent
    target_uinput: str | KnownUinput | None = None

    # Either `output_symbol` or `output_type` and `output_code` is required
    # Only set if output is "Key or Macro":
    output_symbol: str | None = None  # The symbol or macro string if applicable
    # "Analog Axis" or if preset edited manually to inject a code instead of a symbol:
    output_type: int | None = None  # The event type of the mapped event
    output_code: int | None = None  # The event code of the mapped event

    name: str | None = None
    mapping_type: MappingType | None = None

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

    # Attributes starting with an underscore are excluded by pydantic in .dict,
    # so they aren't saved to disk.
    # callback which gets called if the input_combination is updated
    _combination_changed: CombinationChangedCallback | None = None

    # TODO remove, somehow. call stuff manually instead of registering a callback
    def __setattr__(self, key: str, value: Any):
        """Call the combination changed callback
        if we are about to update the input_combination
        """
        if key != "input_combination" or self._combination_changed is None:
            super().__setattr__(key, value)
            return

        # the new combination is not yet validated
        try:
            new_combi = InputCombination.validate(value)
        except (ValueError, TypeError) as exception:
            raise ValidationError(
                [f"failed to Validate {value} as InputCombination"],
                Mapping,
            ) from exception

        if new_combi == self.input_combination:
            return

        # raises a keyError if the combination or a permutation is already mapped
        self._combination_changed(new_combi, self.input_combination)
        super().__setattr__("input_combination", new_combi)

    def __str__(self):
        return "Mapping " + str(
            self.dict(
                exclude_defaults=True,
                include={"input_combination", "target_uinput"},
            )
        )

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

    def is_analog_output(self):
        return self.mapping_type == MappingType.ANALOG

    def set_combination_changed_callback(self, callback: CombinationChangedCallback):
        self._combination_changed = callback

    def remove_combination_changed_callback(self):
        self._combination_changed = None

    def get_output_type_code(self) -> tuple[int, int] | None:
        """Returns the output_type and output_code if set,
        otherwise looks the output_symbol up in the keyboard_layout
        return None for unknown symbols and macros
        """
        if self.output_code is not None and self.output_type is not None:
            return self.output_type, self.output_code

        if self.output_symbol and not Parser.is_this_a_macro(self.output_symbol):
            return EV_KEY, keyboard_layout.get(self.output_symbol)

        return None

    def get_output_name_constant(self) -> str:
        """Get the evdev name costant for the output."""
        return get_evdev_constant_name(self.output_type, self.output_code)

    def is_valid(self) -> bool:
        """If the mapping is valid."""
        return len(self.get_readable_strict_errors()) == 0

    def _format_error_message(self, error: ValueError) -> str:
        """Check all the different error messages which are not useful for the user."""
        if (
            error is MacroButTypeOrCodeSetError or error is SymbolAndCodeMismatchError
        ) and self.input_combination.defines_analog_input:
            return _(
                "Remove the macro or key from the macro input field "
                "when specifying an analog output"
            )

        if (
            error is MacroButTypeOrCodeSetError or error is SymbolAndCodeMismatchError
        ) and not self.input_combination.defines_analog_input:
            return _(
                "Remove the Analog Output Axis when specifying a macro or key output"
            )

        if error is MissingOutputAxisError:
            error_message = _(
                "The input specifies an analog axis, but no output axis is selected."
            )
            if self.output_symbol is not None:
                event = next(
                    event
                    for event in self.input_combination
                    if event.defines_analog_input
                )
                error_message += (
                    _(
                        "\nIf you mean to create a key or macro mapping "
                        "go to the advanced input configuration"
                        ' and set a "Trigger Threshold" for "%s"'
                    )
                    % event.description()
                )
            return error_message

        if error is WrongMappingTypeForKeyError:
            error_message = (
                _('The input specifies a key, but the output type is not "%s".')
                % OutputTypeNames.key_or_macro
            )

            if self.output_type in (EV_ABS, EV_REL):
                error_message += _(
                    "\nIf you mean to create an analog axis mapping go to the "
                    'advanced input configuration and set an input to "Use as Analog".'
                )

            return error_message

        if error is MissingMacroOrKeyError:
            return _("Missing macro or key")

        return str(error)

    @root_validator
    def validate_mapping_type(cls, values):
        """Overrides the mapping type if the output mapping type is obvious."""
        output_type = values.get("output_type")
        output_code = values.get("output_code")
        output_symbol = values.get("output_symbol")

        if output_type is not None and output_symbol is not None:
            # This is currently only possible when someone edits the preset file by
            # hand. A key-output mapping without an output_symbol, but type and code
            # instead, is valid as well.
            logger.debug("Both output_type and output_symbol are set")

        if output_type != EV_KEY and output_code is not None and not output_symbol:
            values["mapping_type"] = MappingType.ANALOG.value

        if output_type is None and output_code is None and output_symbol:
            values["mapping_type"] = MappingType.KEY_MACRO.value

        if output_type == EV_KEY:
            values["mapping_type"] = MappingType.KEY_MACRO.value

        return values

    @root_validator(pre=True)
    def validate_symbol(cls, values):
        symbol = values.get("output_symbol")

        if symbol == "":
            values["output_symbol"] = None
            return values

        if symbol is None:
            return values

        symbol = symbol.strip()
        values["output_symbol"] = symbol

        if symbol == DISABLE_NAME:
            return values

        return values

    def get_readable_strict_errors(self) -> list[str]:
        """Human readable strict validation errors."""
        # Do not leak anything pydantic into the rest of the code,
        # makes the c++ port harder. Just strings please.
        methods = [
            # Same calls as in self.assert_strict
            self._assert_output,
            self._assert_only_one_analog_input,
            self._assert_trigger_point_in_range,
            self._assert_output_symbol_variant,
            self._assert_output_integrity,
            self._assert_output_matches_input,
            self._assert_idk,
        ]

        errors = []
        for method in methods:
            try:
                method()
            except ValueError as error:
                errors.append(self._format_error_message(error))

        return errors

    def assert_strict(self) -> None:
        """Raise an error if the mapping is not perfectly complete for the service."""
        # I suspect this doesn't fit pydantics patterns anymore, but for a potential
        # c++ port I'll have to move away from pydantic anyway.
        # The GUI allows incomplete mappings that still need some modification to
        # be valid.

        # same calls as in self.get_readable_strict_errors
        self._assert_output()
        self._assert_only_one_analog_input()
        self._assert_trigger_point_in_range()
        self._assert_output_symbol_variant()
        self._assert_output_integrity()
        self._assert_output_matches_input()
        self._assert_idk()

    def _assert_idk(self) -> None:
        # TODO check that input_combination is not empty? Would this mimic
        #  the (non-UI)Mapping properly?
        # input_combination: InputCombination

        if self.target_uinput is None:
            raise ValueError("target_uinput not set")

        target_uinput: KnownUinput

    def _assert_output(self) -> None:
        symbol = self.output_symbol

        if symbol == DISABLE_NAME:
            return

        if Parser.is_this_a_macro(symbol):
            # Just attempt to parse to check if it is valid, this is not where the
            # actual parsing for the macro execution happens.
            # TODO why create a mapping_mock?
            mapping_mock = self.copy()
            # raises MacroError
            Parser.parse(symbol, mapping=mapping_mock, verbose=False)
            return

        code = keyboard_layout.get(symbol)
        if code is None:
            raise OutputSymbolUnknownError(symbol)

        target = self.target_uinput
        if target is not None and not GlobalUInputs.can_default_uinput_emit(
            target, EV_KEY, code
        ):
            raise SymbolNotAvailableInTargetError(symbol, target)

    def _assert_only_one_analog_input(self) -> None:
        """Check that the input_combination specifies a maximum of one
        analog to analog mapping
        """
        combination = self.input_combination
        analog_events = [event for event in combination if event.defines_analog_input]
        if len(analog_events) > 1:
            raise OnlyOneAnalogInputError(analog_events)

    def _assert_trigger_point_in_range(self) -> None:
        """Check if the trigger point for mapping analog axis to buttons is valid."""
        combination = self.input_combination
        for input_config in combination:
            if (
                input_config.type == EV_ABS
                and input_config.analog_threshold
                and abs(input_config.analog_threshold) >= 100
            ):
                raise TriggerPointInRangeError(input_config)

    def _assert_output_symbol_variant(self) -> None:
        """Validate that either type and code or symbol are set for key output."""
        o_symbol = self.output_symbol
        o_type = self.output_type
        o_code = self.output_code
        if o_symbol is None and (o_type is None or o_code is None):
            raise OutputSymbolVariantError()

    def _assert_output_integrity(self) -> None:
        """Validate the output key configuration."""
        symbol = self.output_symbol
        type_ = self.output_type
        code = self.output_code
        if symbol is None:
            # If symbol is "", then validate_symbol changes it to None
            # type and code can be anything
            return

        if type_ is None and code is None:
            # we have a symbol: no type and code is fine
            return

        # disallow output type and code for macros
        if Parser.is_this_a_macro(symbol) and (type_ is not None or code is not None):
            raise MacroButTypeOrCodeSetError()

        if code is not None and code != keyboard_layout.get(symbol) or type_ != EV_KEY:
            raise SymbolAndCodeMismatchError(symbol, code)

    def _assert_output_matches_input(self) -> None:
        """Validate that an output type is an axis if we have an input axis.
        And vice versa."""
        assert isinstance(self.input_combination, InputCombination)
        combination: InputCombination = self.input_combination

        analog_input_config = combination.find_analog_input_config()
        defines_analog_input = analog_input_config is not None
        output_type = self.output_type
        output_code = self.output_code
        mapping_type = self.mapping_type
        output_symbol = self.output_symbol
        output_key_set = output_symbol or (output_type == EV_KEY and output_code)

        if mapping_type is None:
            # Empty mapping most likely
            return

        if not defines_analog_input and mapping_type != MappingType.KEY_MACRO.value:
            raise WrongMappingTypeForKeyError()

        if not defines_analog_input and not output_key_set:
            raise MissingMacroOrKeyError()

        if (
            defines_analog_input
            and output_type not in (EV_ABS, EV_REL)
            and output_symbol != DISABLE_NAME
        ):
            raise MissingOutputAxisError(analog_input_config, output_type)
