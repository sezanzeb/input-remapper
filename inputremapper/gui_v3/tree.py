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


"""The macro tree: plain, immutable data. No runtime context, no parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, cast

from inputremapper.gui_v3.schema import SCHEMA


@dataclass(frozen=True)
class Var:
    """A reference to a macro variable, `$name` in the macro language."""

    name: str


# A macro is a sequence of calls, joined by "." in the macro language.
Chain = tuple["Call", ...]

# int, float and str are literals. None is an omitted or explicit None.
# A str in a "macro" slot is a bare symbol, like `hold(KEY_A)`.
Value = int | float | str | None | Var | Chain


@dataclass(frozen=True)
class Call:
    """One function call of the macro language, like `wait(40)`.

    `args` are positional, in the order of the block's schema. Trailing arguments
    that equal their default are not stored, so equal macros compare equal.
    Spread blocks (parallel, hold_keys) store all their varargs in `args`.

    Two pseudo operations exist, both with a single str argument that is kept
    verbatim: "symbol" (a mapping output that is not a macro, like `KEY_ESC`) and
    "raw" (a call the editor doesn't know, shown as a grey block).
    """

    op: str
    args: tuple[Value, ...] = ()

    @staticmethod
    def make(op: str, *args: Value) -> Call:
        """Create a Call with trailing default arguments dropped."""
        spec = SCHEMA.get(op)
        trimmed = list(args)
        if spec is not None and not spec.spread:
            while trimmed and len(trimmed) > spec.required_count:
                if trimmed[-1] != spec.args[len(trimmed) - 1].default:
                    break
                trimmed.pop()
        return Call(op, tuple(trimmed))


_VARIABLE_IN_TEXT = re.compile(r"\$([A-Za-z_]\w*)")


def variables_used(chain: Chain) -> list[str]:
    """Names of the variables a macro reads or writes, in order of appearance."""
    found: list[str] = []

    def add(name: str) -> None:
        if name not in found:
            found.append(name)

    for call in chain:
        if call.op == "raw":
            for arg in call.args:
                if isinstance(arg, str):
                    for name in _VARIABLE_IN_TEXT.findall(arg):
                        add(name)
            continue
        for arg in call.args:
            if isinstance(arg, Var):
                add(arg.name)
            elif is_chain(arg):
                for name in variables_used(cast("Chain", arg)):
                    add(name)
    return found


def is_chain(value: object) -> bool:
    if not isinstance(value, tuple):
        return False
    return all(isinstance(c, Call) for c in cast("tuple[object, ...]", value))


# JSON ---------------------------------------------------------------------------


def value_to_json(value: Value) -> Any:
    if isinstance(value, Var):
        return {"var": value.name}
    if isinstance(value, tuple):
        return [call_to_json(call) for call in value]
    return value


def value_from_json(data: Any) -> Value:
    if isinstance(data, dict):
        return Var(cast("dict[str, Any]", data)["var"])
    if isinstance(data, list):
        items = cast("list[dict[str, Any]]", data)
        return tuple(call_from_json(item) for item in items)
    return data


def call_to_json(call: Call) -> dict[str, Any]:
    """Named arguments, so the file is readable: {"op": "wait", "time": 40}."""
    out: dict[str, Any] = {"op": call.op}
    spec = SCHEMA.get(call.op)
    if spec is None:
        out["text"] = call.args[0] if call.args else ""
        return out

    if spec.spread:
        out[spec.args[0].name] = [value_to_json(arg) for arg in call.args]
        return out

    for arg_spec, value in zip(spec.args, call.args):
        out[arg_spec.name] = value_to_json(value)
    return out


def call_from_json(data: dict[str, Any]) -> Call:
    op = data["op"]
    spec = SCHEMA.get(op)
    if spec is None:
        return Call(op, (data.get("text", ""),))

    if spec.spread:
        items = data.get(spec.args[0].name, [])
        return Call(op, tuple(value_from_json(item) for item in items))

    args: list[Value] = []
    for arg_spec in spec.args:
        if arg_spec.name in data:
            args.append(value_from_json(data[arg_spec.name]))
        else:
            args.append(arg_spec.default)
    return Call.make(op, *args)


def chain_to_json(chain: Chain) -> list[dict[str, Any]]:
    return [call_to_json(call) for call in chain]


def chain_from_json(data: list[dict[str, Any]]) -> Chain:
    return tuple(call_from_json(item) for item in data)
