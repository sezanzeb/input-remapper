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

    def is_spread(self):
        """Does this Argument store all remaining Variables of a Task as a list?"""
        return self.position == ArgumentFlags.spread


class Argument(ArgumentConfig):
    """Validation of variables and access to their value for Tasks during runtime."""

    _variable: Optional[Variable] = None

    # If the position is set to ArgumentFlags.spread, then _variables will be filled
    # with all remaining positional arguments that were passed to a task.
    _variables: List[Variable]

    _mapping: Optional[Mapping] = None

    def __init__(
        self,
        argument_config: ArgumentConfig,
        mapping: Mapping,
    ) -> None:
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

    def initialize_variables(self, raw_values: List[RawValue]) -> None:
        """If the macro is supposed to contain multiple variables, set them.
        Should be done during parsing."""
        assert len(self._variables) == 0
        assert self._variable is None
        assert self.is_spread()

        for raw_value in raw_values:
            variable = self._parse_raw_value(raw_value)
            self._variables.append(variable)

    def initialize_variable(self, raw_value: RawValue) -> None:
        """Set the Arguments Variable. Done during parsing."""
        assert len(self._variables) == 0
        assert self._variable is None
        assert not self.is_spread()

        variable = self._parse_raw_value(raw_value)
        self._variable = variable

    def initialize_default(self) -> None:
        """Set the Arguments to its default value. Done during parsing."""
        assert len(self._variables) == 0
        assert self._variable is None
        assert not self.is_spread()

        variable = Variable(value=self.default, const=True)
        self._variable = variable

    def get_value(self) -> Any:
        """To ask for the current value of the variable during runtime."""
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
        """To ask for the current values of the variables during runtime."""
        assert self.is_spread(), f"Use .{self.get_value.__name__}()"

        values = []
        for variable in self._variables:
            if not variable.const:
                values.append(self._validate_dynamic_value(variable))
            else:
                values.append(variable.get_value())

        # TODO test hold_keys with both valid and invalid dynamic symbol-names.

        return values

    def get_variable_name(self) -> str:
        """If the variable is not const, return its name."""
        return self._variable.get_name()

    def contains_macro(self) -> bool:
        """Does the underlying Variable contain another child-macro?"""
        assert self._variable is not None
        return isinstance(self._variable.get_value(), Macro)

    def set_value(self, value: Any) -> Any:
        """To set the value of the underlying Variable during runtime.
        Fails for constants."""
        assert self._variable is not None
        if self._variable.const:
            raise Exception("Can't set value of a constant")

        self._variable.set_value(value)

    def assert_is_symbol(self, symbol: str) -> None:
        """Checks if the key/symbol-name is valid. Like "KEY_A" or "escape".

        Using `is_symbol` on the ArgumentConfig is prefered, which causes it to
        automatically do this for you. But some macros may be a bit more flexible,
        and there we want to assert this ourselves only in certain cases."""
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

        # The order of steps below matters.

        if isinstance(value, Macro):
            return Variable(value=value, const=True)

        if self.is_variable_name:
            # Treat this as a non-constant variable,
            # even without a `$` in front of its name
            if value.startswith('"'):
                # Remove quotes from the string
                value = value[1:-1]
            return Variable(value=value, const=False)

        if value.startswith("$"):
            # Will be resolved during the macros runtime
            return Variable(value=value[1:], const=False)

        if self.is_symbol:
            if value.startswith('"'):
                value = value[1:-1]
            self.assert_is_symbol(value)
            return Variable(value=value, const=True)

        if (value == "" or value == "None") and None in self.types:
            # I think "" is the deprecated alternative to "None"
            return Variable(value=None, const=True)

        if value.startswith('"') and str in self.types:
            # Something with explicit quotes should never be parsed as a number.
            # Treat it as a string no matter the content.
            value = value[1:-1]
            return Variable(value=value, const=True)

        if float in self.types:
            try:
                return Variable(value=float(value), const=True)
            except (ValueError, TypeError) as e:
                pass

        if int in self.types:
            try:
                return Variable(value=int(value), const=True)
            except (ValueError, TypeError) as e:
                pass

        if not value.startswith('"') and ("(" in value or ")" in value):
            # Looks like something that should have been a macro. It is not explicitly
            # wrapped in quotes. Most likely an error. If it was a valid macro, the
            # parser would have parsed it as such.
            raise MacroError(
                msg=f"A broken macro was passed as parameter to {self.name}"
            )

        if str in self.types:
            # Treat as a string. Something like KEY_A in key(KEY_A)
            return Variable(value=value, const=True)

        raise self._type_error_factory(value)

    def _validate_dynamic_value(self, variable: Variable) -> Any:
        """To make sure the value of a non-const variable, asked for at runtime, is
        fitting for the given ArgumentConfig."""
        # Most of the stuff has already been taken care of when, for example,
        # the "1" of set(foo, 1), or the '"bar"' or set(foo, "bar") was parsed the
        # first time. In the first case we get a number 1, and in the second a string
        # `bar` without quotes
        assert not variable.const
        value = variable.get_value()

        if self.is_symbol:
            # value might be int `1`, which is a valid symbol for `key(1)`
            value = str(value)
            self.assert_is_symbol(value)
            return value

        if None in self.types and value is None:
            return value

        if type(value) in self.types:
            return value

        # TODO test that a number actually ends up as a number, when both str and int
        #  are allowed
        if type(value) not in self.types and str in self.types:
            # `set` cannot make predictions where the variable will be used. Make sure
            # the type is compatible, and turn numbers back into strings if need be.
            return str(value)

        # If the value is "1", we don't attempt to parse it as a number. This being a
        # string means that something like `set(foo, "1")` was used, which enforces a
        # string datatype. Otherwise, `set` would have already turned it into an int.

        raise self._type_error_factory(value)

    def _is_numeric_string(self, value: str) -> bool:
        """Check if the value can be turned into a number."""
        try:
            float(value)
            return True
        except ValueError:
            return False

    def _type_error_factory(self, value: Any) -> MacroError:
        return MacroError(
            msg=(
                f'Expected "{self.name}" to be one of {self.types}, but got '
                f"{type(value)} {value}"
            )
        )
