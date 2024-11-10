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

import re
from typing import Any

from inputremapper.configs.validation_errors import MacroError
from inputremapper.injection.macros.macro import macro_variables


class Variable:
    """Something that the user passed into a macro function.

    Examples:
    - `KEY_A` in `key(KEY_A)` (const=True)
    - `$foo` in `repeat($foo, key(KEY_A))` (const=False)

    Its value is unknown during construction and needs to be set using the `set` macro
    during runtime.
    """

    def __init__(self, value: Any, const: bool):
        if not const and not isinstance(value, str):
            raise MacroError(f"Variables require a string name, not {value}")

        self.value = value
        self.const = const

        if not const:
            self.type_check_variablename()

    def get_name(self) -> str:
        assert not self.const
        assert isinstance(self.value, str)
        return self.value

    def get_value(self) -> Any:
        """Get the variables value from the common variable storage process."""
        if self.const:
            return self.value

        return macro_variables.get(self.value)

    def set_value(self, value: Any) -> Any:
        """Set the variables value across all macros."""
        assert not self.const
        macro_variables[self.value] = value

    def type_check_variablename(self):
        """Check if this is a legit variable name.

        Because they could clash with language features. If the macro can be
        parsed at all due to a problematic choice of a variable name.

        Allowed examples: "foo", "Foo1234_", "_foo_1234"
        Not allowed: "1_foo", "foo=blub", "$foo", "foo,1234", "foo()"
        """
        if not isinstance(self.value, str) or not re.match(
            r"^[A-Za-z_][A-Za-z_0-9]*$", self.value
        ):
            raise MacroError(msg=f'"{self.value}" is not a legit variable name')

    def __repr__(self):
        return f'<Variable "{self.value}" const={self.const} at {hex(id(self))}>'

    def __eq__(self, other):
        if not isinstance(other, Variable):
            return False

        return self.const == other.const and self.value == other.value
