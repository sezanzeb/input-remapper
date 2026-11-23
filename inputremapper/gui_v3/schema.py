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


"""What blocks exist and what arguments they take.

Derived from the engine's own `argument_configs`, so the block editor can't drift
from the macro language. Only the units and the aliases are maintained by hand.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from inputremapper.injection.macros.argument import ArgumentFlags
from inputremapper.injection.macros.macro import Macro
from inputremapper.injection.macros.parse import Parser


class ArgKind(str, Enum):
    VALUE = "value"  # a number, a string, or a $variable
    SYMBOL = "symbol"  # a key name like KEY_A
    VARIABLE = "variable"  # the name of a variable that is written to
    MACRO = "macro"  # a nested macro, rendered as a C-shaped slot


@dataclass(frozen=True)
class ArgSpec:
    name: str
    kind: ArgKind
    required: bool
    default: Any = None
    unit: str | None = None
    # str is an accepted type, which means numeric looking strings need quotes
    accepts_str: bool = False
    accepts_number: bool = False
    accepts_none: bool = False


@dataclass(frozen=True)
class BlockSpec:
    op: str
    args: tuple[ArgSpec, ...]
    spread: bool = False

    @property
    def required_count(self) -> int:
        return sum(1 for arg in self.args if arg.required)


# Aliases that only exist for backwards compatibility, mapped to their modern name.
ALIASES = {
    "m": "modify",
    "r": "repeat",
    "k": "key",
    "e": "event",
    "w": "wait",
    "h": "hold",
}

# (op, argument) -> unit, shown next to the field and never typed by the user.
UNITS = {
    ("wait", "time"): "ms",
    ("wait", "max_time"): "ms",
    ("if_tap", "timeout"): "ms",
    ("if_single", "timeout"): "ms",
    ("mod_tap", "tapping_term"): "ms",
}


def _build() -> dict[str, BlockSpec]:
    schema: dict[str, BlockSpec] = {}
    for op, task_class in Parser.TASK_CLASSES.items():
        if op in ALIASES:
            continue

        args: list[ArgSpec] = []
        spread = False
        for config in task_class.argument_configs:
            if config.is_variable_name:
                kind = ArgKind.VARIABLE
            elif config.is_symbol:
                kind = ArgKind.SYMBOL
            elif Macro in config.types:
                kind = ArgKind.MACRO
            else:
                kind = ArgKind.VALUE

            spread = spread or config.position == ArgumentFlags.spread
            required = config.is_required()
            args.append(
                ArgSpec(
                    name=config.name.lstrip("*"),
                    kind=kind,
                    required=required,
                    default=None if required else config.default,
                    unit=UNITS.get((op, config.name)),
                    accepts_str=str in config.types,
                    accepts_number=int in config.types or float in config.types,
                    accepts_none=None in config.types,
                )
            )
        schema[op] = BlockSpec(op=op, args=tuple(args), spread=spread)
    return schema


SCHEMA: dict[str, BlockSpec] = _build()

# Not engine functions: see `Call`.
PSEUDO_OPS = ("symbol", "raw")


def canonical_op(name: str) -> str:
    return ALIASES.get(name, name)
