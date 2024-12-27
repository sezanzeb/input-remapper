# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2024 sezanzeb <b8x45ygc9@mozmail.com>
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

"""Exceptions that are thrown when configurations are incorrect."""

# can't merge this with exceptions.py, because I want error constructors here to
# be intelligent to avoid redundant code, and they need imports, which would cause
# circular imports.

# pydantic only catches ValueError, TypeError, and AssertionError

from __future__ import annotations

from typing import Optional

from evdev.ecodes import EV_KEY

from inputremapper.configs.keyboard_layout import keyboard_layout
from inputremapper.injection.global_uinputs import GlobalUInputs


class OutputSymbolVariantError(ValueError):
    def __init__(self):
        super().__init__(
            "Missing Argument: Mapping must either contain "
            "`output_symbol` or `output_type` and `output_code`"
        )


class TriggerPointInRangeError(ValueError):
    def __init__(self, input_config):
        super().__init__(
            f"{input_config = } maps an absolute axis to a button, but the "
            "trigger point (event.analog_threshold) is not between -100[%] "
            "and 100[%]"
        )


class OnlyOneAnalogInputError(ValueError):
    def __init__(self, analog_events):
        super().__init__(
            f"Cannot map a combination of multiple analog inputs: {analog_events}"
            "add trigger points (event.value != 0) to map as a button"
        )


class SymbolNotAvailableInTargetError(ValueError):
    def __init__(self, symbol, target):
        code = keyboard_layout.get(symbol)

        fitting_targets = GlobalUInputs.find_fitting_default_uinputs(EV_KEY, code)
        fitting_targets_string = '", "'.join(fitting_targets)

        super().__init__(
            f'The output_symbol "{symbol}" is not available for the "{target}" '
            + f'target. Try "{fitting_targets_string}".'
        )


class OutputSymbolUnknownError(ValueError):
    def __init__(self, symbol: str):
        super().__init__(
            f'The output_symbol "{symbol}" is not a macro and not a valid '
            + "keycode-name"
        )


class MacroButTypeOrCodeSetError(ValueError):
    def __init__(self):
        super().__init__(
            "output_symbol is a macro: output_type " "and output_code must be None"
        )


class SymbolAndCodeMismatchError(ValueError):
    def __init__(self, symbol, code):
        super().__init__(
            "output_symbol and output_code mismatch: "
            f"output macro is {symbol} -> {keyboard_layout.get(symbol)} "
            f"but output_code is {code} -> {keyboard_layout.get_name(code)} "
        )


class WrongOutputTypeForKeyError(ValueError):
    def __init__(self):
        super().__init__(f"Wrong output_type for key input")


class MissingMacroOrKeyError(ValueError):
    def __init__(self):
        super().__init__("Missing macro or key")


class MissingOutputAxisError(ValueError):
    def __init__(self, analog_input_config, output_type):
        super().__init__(
            "Missing output axis: "
            f'"{analog_input_config}" is used as analog input, '
            f"but the {output_type = } is not an axis "
        )


class MacroError(ValueError):
    """Macro syntax errors."""

    def __init__(self, symbol: Optional[str] = None, msg="Error while parsing a macro"):
        self.symbol = symbol
        super().__init__(msg)


def pydantify(error: type):
    """Generate a string as it would appear IN pydantic error types.

    This does not include the base class name, which is transformed to snake case in
    pydantic. Example pydantic error type: "value_error.foobar" for FooBarError.
    """
    # See https://github.com/pydantic/pydantic/discussions/5112
    lower_classname = error.__name__.lower()
    if lower_classname.endswith("error"):
        return lower_classname[: -len("error")]
    return lower_classname
