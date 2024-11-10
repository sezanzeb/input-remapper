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
    from inputremapper.configs.mapping import Mapping


class ArgumentFlags(Enum):
    # No default value is set, and the user has to provide one when using the macro
    required = "required"

    # If used, acts like foo(*bar)
    spread = "spread"


@dataclass
class ArgumentConfig:
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
    """Definition and storage of argument-values for Tasks."""

    _variable: Optional[Variable] = None
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
        """Get the primitive constant value, or whatever primitive the variable
        currently stores."""
        assert not self.is_spread(), f"Use .{self.get_values.__name__}()"
        # If a user passed None as value, it should be a Variable(None, const=True) here.
        # If not, a test or input-remapper is broken.
        assert self._variable is not None

        value = self._variable.get_value()
        value = self._validate(value)

        # Otherwise, if it is a constant, it should have already been validated during
        # parsing so we don't call _validate here redundantly.
        return value

    def get_values(self) -> List[Any]:
        """If this argument shall take all remaining positional args, validate and
        return them."""
        assert self.is_spread(), f"Use .{self.get_value.__name__}()"
        values = [self._validate(value.get_value()) for value in self._variables]
        return values

    def contains_macro(self) -> bool:
        return isinstance(self._variable.get_value(), Macro)

    def set_value(self, value: Any) -> Any:
        assert self._variable is not None
        if self._variable.const:
            raise Exception("Can't set value of a constant")

        self._variable.set_value(value)

    def initialize_value(self, variable: Variable) -> None:
        """Take the value from the user-defined macro code, and insert it in self."""
        if self.is_variable_name:
            # This is weird, but when the parser sees `set(foo, 1)`, it inserts foo as a
            # string, therefore `foo` is expected to be a constant at first. If you do
            # `set($foo, 1)`, then it treats foo as a non-const variable. Theoretically
            # you could insert a dynamic variable name there, but that sounds incredibly
            # complicated for a macro, and there is a danger that people don't do it
            # correctly when they just want `set(foo, 1)`. Therefore, we want to assert
            # that it is "foo", not "$foo".
            if not variable.const:
                raise MacroError(
                    'Use "foo", not "$foo" in your macro as variable-name.'
                )

            variable.type_check_variablename()
            variable.const = False

        if variable.const:
            # Otherwise it will be validated in self.get_value/self.get_values
            self._validate(variable.get_value())

        self._variable = variable

    def append_variable(self, variable: Variable) -> None:
        if variable.const:
            self._validate(variable.get_value())

        self._variables.append(variable)

    def is_spread(self):
        return self.position == ArgumentFlags.spread

    def _validate(self, value: Any) -> Any:
        assert not isinstance(value, Variable)
        value = self.assert_type(value)
        if self.is_symbol:
            self.assert_is_symbol(value)

        return value

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

    def assert_type(self, value: Any) -> Any:
        """Validate a parameter used in a macro.

        If the value is a Variable, it will be returned and should be resolved
        during runtime with _resolve.
        """
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
            # work. However, 1 is not a number in the technical sense, it is a
            # symbol-name, and therefore a string.
            return str(value)

        if self.name is not None and self.position is not None:
            raise MacroError(
                msg=(
                    f'Expected "{self.name}" to be one of {self.types}, but got '
                    f"{type(value)} {value}"
                )
            )

        raise MacroError(
            msg=f"Expected parameter to be one of {self.types}, but got {value}"
        )
