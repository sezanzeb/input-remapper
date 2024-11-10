#!/usr/bin/env python3
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

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Any, Union, List, Literal, Type, TYPE_CHECKING

from evdev._ecodes import EV_KEY

from inputremapper.configs.keyboard_layout import keyboard_layout
from inputremapper.configs.validation_errors import (
    MacroError,
    SymbolNotAvailableInTargetError,
)
from inputremapper.injection.global_uinputs import GlobalUInputs
from inputremapper.injection.macros.macro import Macro
from inputremapper.injection.macros.variable import Variable

if TYPE_CHECKING:
    from inputremapper.injection.macros.raw_value import RawValue
    from inputremapper.configs.mapping import Mapping


class ArgumentFlags(Enum):
    # No default value is set, and the user has to provide one when using the macro
    required = "required"

    # If used, acts like foo(*bar)
    spread = "spread"


@dataclass
class ArgumentConfig:
    """Definition what kind of arguments a task may take."""

    position: Union[int, Literal[ArgumentFlags.spread]]
    name: str
    types: List[Optional[Type]]
    is_symbol: bool = False
    default: Any = ArgumentFlags.required

    # If True, then the value (which should be a string), is the name of a non-constant
    # variable. Tasks that overwrite their value need this, like `set`. The specified
    # types are those that the current value of that variable may have. For `set` this
    # doesn't matter, but something like `add` requires them to be numbers.
    is_variable_name: bool = False

    def is_required(self) -> bool:
        return self.default == ArgumentFlags.required


class Argument(ArgumentConfig):
    """Validation of variables and access to their value for Tasks during runtime."""

    _variable: Optional[Variable] = None

    # If the position is set to ArgumentFlags.spread, then _variables will be filled
    # with all remaining positional arguments that were passed to a task.
    _variables: List[Variable]

    _mapping: Optional[Mapping] = None

    def __init__(self, argument_config: ArgumentConfig, mapping: Mapping):
        # If a default of None is specified, but None is not an allowed type, then
        # input-remapper has a bug here. Add "None" to your ArgumentConfig.types
        assert not (
            argument_config.default is None and None not in argument_config.types
        )

        self.position = argument_config.position
        self.name = argument_config.name
        self.types = argument_config.types
        self.is_symbol = argument_config.is_symbol
        self.default = argument_config.default
        self.is_variable_name = argument_config.is_variable_name

        self._mapping = mapping
        self._variables = []

        if not self.is_required():
            # Initialize default, might be overwritten later when going through the
            # user-defined stuff.
            self._variable = Variable(self.default, const=True)

    def get_value(self) -> Any:
        """Get the primitive constant value, or whatever primitive the Variable
        currently stores."""
        assert not self.is_spread(), f"Use .{self.get_values.__name__}()"
        # If a user passed None as value, it should be a Variable(None, const=True) here.
        # If not, a test or input-remapper is broken.
        assert self._variable is not None

        value = self._variable.get_value()

        if not self._variable.const:
            # Dynamic value. Hasn't been validated yet
            value = self._validate_dynamic_value(self._variable)

        return value

    def get_values(self) -> List[Any]:
        """If this Argument shall take all remaining positional args, validate and
        return them."""
        assert self.is_spread(), f"Use .{self.get_value.__name__}()"

        values = []
        for variable in self._variables:
            if not variable.const:
                values.append(self._validate_dynamic_value(variable))
            else:
                values.append(variable.get_value())

        # TODO test hold_keys with both valid and invalid dynamic symbol-names.

        return values

    def contains_macro(self) -> bool:
        """Does the underlying Variable contain another child-macro?"""
        return isinstance(self._variable.get_value(), Macro)

    def set_value(self, value: Any) -> Any:
        """Set the value of the underlying Variable. Fails for constants."""
        assert self._variable is not None
        if self._variable.const:
            raise Exception("Can't set value of a constant")

        self._variable.set_value(value)

    def type_error_factory(self, value):
        return MacroError(
            msg=(
                f'Expected "{self.name}" to be one of {self.types}, but got '
                f"{type(value)} {value}"
            )
        )

    def append_variable(self, raw_value: RawValue) -> None:
        """Some Arguments are supposed to contain a list of Variables. Add one to it."""
        assert self.is_spread()
        variable = self._parse_raw_value(raw_value)
        self._variables.append(variable)

    def set_variable(self, raw_value: RawValue):
        assert not self.is_spread()
        variable = self._parse_raw_value(raw_value)
        self._variable = variable

    def set_default(self):
        assert not self.is_spread()
        variable = Variable(value=self.default, const=True)
        self._variable = variable

    def is_spread(self):
        """Does this Argument store all remaining Variables of a Task as a list?"""
        return self.position == ArgumentFlags.spread

    def assert_is_symbol(self, symbol: str) -> None:
        """Checks if the key/symbol-name is valid. Like "KEY_A" or "escape"."""
        symbol = str(symbol)
        code = keyboard_layout.get(symbol)

        if code is None:
            raise MacroError(msg=f'Unknown key "{symbol}"')

        if self._mapping is not None:
            target = self._mapping.target_uinput
            if target is not None and not GlobalUInputs.can_default_uinput_emit(
                target, EV_KEY, code
            ):
                raise SymbolNotAvailableInTargetError(symbol, target)

    def _parse_raw_value(self, raw_value: RawValue) -> Variable:
        """Validate and parse."""
        value = raw_value.value

        if isinstance(value, Macro):
            return Variable(value=value, const=True)

        if self.is_variable_name:
            # Treat this as a non-constant variable,
            # even without a `$` in front of its name
            if value.startswith('"'):
                # Remove quotes from the string
                value = value[1:-1]
            return Variable(value=value, const=False)

        if (value == "" or value == "None") and None in self.types:
            # I think "" is the deprecated alternative to "None"
            return Variable(value=None, const=True)

        if value.startswith('"') and str in self.types:
            # Something with explicit quotes should never be parsed as a number.
            # Remove quotes from the string
            value = value[1:-1]
            return Variable(value=value, const=True)

        if value.startswith("$"):
            # Will be resolved during the macros runtime
            return Variable(value=value[1:], const=False)

        if float in self.types:
            try:
                value = float(value)
                return Variable(value=value, const=True)
            except (ValueError, TypeError) as e:
                pass

        if int in self.types:
            try:
                value = int(value)
                return Variable(value=value, const=True)
            except (ValueError, TypeError) as e:
                pass

        if not value.startswith('"') and ("(" in value or ")" in value):
            # Looks like something that should have been a macro. It is not explicitly
            # wrapped in quotes. Most likely an error. If it was a valid macro, the
            # parser would have parsed it as such.
            raise MacroError(
                msg=f"A broken macro was passed as parameter to {self.name}"
            )

        if self.is_symbol:
            self.assert_is_symbol(value)

        if str in self.types:
            # Treat as a string. Something like KEY_A in key(KEY_A)
            return Variable(value=value, const=True)

        raise self.type_error_factory(value)

    def _validate_dynamic_value(self, variable: Variable) -> Any:
        assert isinstance(variable, Variable)
        assert not variable.const

        value = self._parse_dynamic_variable(variable)
        if self.is_symbol:
            self.assert_is_symbol(value)

        return value

    def _parse_dynamic_variable(self, variable: Variable) -> Any:
        # Most of the stuff has already been taken care of when, for example,
        # the "1" of set(foo, 1) was parsed the first time.
        assert isinstance(variable, Variable)
        assert not variable.const

        value = variable.get_value()
        for allowed_type in self.types:
            if allowed_type is None:
                if value is None:
                    return value
                continue

            if isinstance(value, allowed_type):
                return value

        if str in self.types:
            # String quotes can be omitted in macros. For example If something was
            # parsed as a number, but only strings are allowed, convert it back into
            # a string.
            # Example: key(KEY_A) works, key(b) works, therefore key(1) should also
            # work. It is a symbol-name, and therefore a string.
            return str(value)

        raise self.type_error_factory(value)

    def _is_numeric_string(self, value: str) -> bool:
        """Check if the value can be turned into a number."""
        try:
            float(value)
            return True
        except ValueError:
            return False
