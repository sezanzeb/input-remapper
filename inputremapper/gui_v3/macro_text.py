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


# The engine's parser helpers are underscore-prefixed but are the one source of truth
# for splitting macro code; reusing them keeps both parsers in agreement.
# pyright: reportPrivateUsage=false
"""Convert between the macro language and the tree.

`print_chain` is used on every Apply. `parse_text` is only needed to import v1
presets and for the "Edit as text" box, so parse errors never reach the editor's
document: they are raised as `MacroTextError` for the caller to show.
"""

from __future__ import annotations

import re

from inputremapper.configs.validation_errors import MacroError
from inputremapper.gui_v3.schema import SCHEMA, ArgKind, ArgSpec, canonical_op
from inputremapper.gui_v3.tree import Call, Chain, Value, Var
from inputremapper.injection.macros.parse import Parser

_CALL_START = re.compile(r"^(\w+)\(")
_BARE_WORD = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*$")
_BARE_SYMBOL = re.compile(r"^[A-Za-z_0-9][A-Za-z_0-9.\-]*$")


class MacroTextError(ValueError):
    pass


# Text -> tree -------------------------------------------------------------------


def is_macro_text(text: str) -> bool:
    """Same test the engine uses to tell a macro from a plain symbol like KEY_A."""
    return Parser.is_this_a_macro(text)


def parse_text(text: str) -> Chain:
    """Parse macro code, or a plain symbol, into a chain.

    Unknown functions become "raw" calls and survive a round trip unchanged.
    """
    try:
        code = Parser.clean(text)
        if code.count("(") != code.count(")"):
            raise MacroTextError("Unbalanced brackets")
        if not is_macro_text(code):
            return (Call("symbol", (text.strip(),)),)
        code = Parser.handle_plus_syntax(code)
        return _parse_chain(code)
    except MacroError as error:
        raise MacroTextError(str(error)) from error


def _parse_chain(code: str) -> Chain:
    calls: list[Call] = []
    rest = code.strip()
    while rest:
        match = _CALL_START.match(rest)
        if match is None:
            raise MacroTextError(f'Expected a function call, found "{rest}"')

        end = Parser._count_brackets(rest)
        call_code = rest[:end]
        calls.append(_parse_call(match[1], call_code))

        rest = rest[end:]
        if rest.startswith("."):
            rest = rest[1:]
        elif rest:
            raise MacroTextError(f'Expected a "." before "{rest}"')
    return tuple(calls)


def _parse_call(name: str, call_code: str) -> Call:
    op = canonical_op(name)
    spec = SCHEMA.get(op)
    if spec is None:
        return Call("raw", (call_code,))

    inner = call_code[call_code.index("(") + 1 : -1]
    raw_args = [] if inner.strip() == "" else Parser._extract_args(inner)

    positional: list[str] = []
    keywords: dict[str, str] = {}
    for raw in raw_args:
        key, value = Parser._split_keyword_arg(raw)
        if key is None:
            if keywords:
                raise MacroTextError(
                    f"Positional argument after keyword in {call_code}"
                )
            positional.append(value)
        else:
            keywords[key] = value

    if spec.spread:
        arg_spec = spec.args[0]
        return Call(op, tuple(_parse_value(v, arg_spec) for v in positional))

    if len(positional) > len(spec.args):
        raise MacroTextError(f"Too many arguments for {op}")

    by_name = dict(zip((a.name for a in spec.args), positional))
    for key, value in keywords.items():
        if key not in {a.name for a in spec.args}:
            raise MacroTextError(f'Unknown argument "{key}" for {op}')
        by_name[key] = value

    values: list[Value] = []
    for arg_spec in spec.args:
        if arg_spec.name in by_name:
            values.append(_parse_value(by_name[arg_spec.name], arg_spec))
        elif arg_spec.required:
            raise MacroTextError(f'{op} needs "{arg_spec.name}"')
        else:
            values.append(arg_spec.default)
    return Call.make(op, *values)


def _parse_value(raw: str, spec: ArgSpec) -> Value:
    raw = raw.strip()

    if _CALL_START.match(raw):
        return _parse_chain(raw)

    if spec.kind is ArgKind.VARIABLE:
        return Var(_unquote(raw).lstrip("$"))

    if raw.startswith("$"):
        return Var(raw[1:])

    if spec.kind is ArgKind.SYMBOL:
        return _unquote(raw)

    if raw in ("", "None") and spec.accepts_none:
        return None

    if raw.startswith('"'):
        return raw[1:-1]

    if spec.accepts_number:
        if "." in raw:
            try:
                return float(raw)
            except ValueError:
                pass
        try:
            return int(raw)
        except ValueError:
            pass

    return raw


def _unquote(raw: str) -> str:
    if len(raw) >= 2 and raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    return raw


# Tree -> text -------------------------------------------------------------------


def print_chain(chain: Chain) -> str:
    return ".".join(_print_call(call) for call in chain)


# Layout for the Code tab. The engine drops whitespace outside quotes before it
# parses, so any layout is valid and reads back into the same tree.
_INDENT = "  "
_CHAIN_WIDTH = 60  # a chain of plain blocks stays on one line up to this long
_CALL_WIDTH = 50  # so does a block holding a nested macro


def format_chain(chain: Chain, level: int = 0) -> str:
    """The macro as readable text: a block per line, nested macros on their own
    lines, and short ones kept on a single line.

        set(whipping, 1)
          .key_down(BTN_LEFT)
          .while_eq($whipping, 1,
            key(4)
              .wait(700)
              .if_eq($whipping, 1, key(1).wait(1500)))
          .key_up(BTN_LEFT)
    """
    flat = print_chain(chain)
    plain = not any(_nested_chains(call) for call in chain)
    if len(chain) < 2 or (plain and len(flat) + len(_INDENT) * level <= _CHAIN_WIDTH):
        if len(chain) < 2:
            return _format_call(chain[0], level) if chain else ""
        return flat

    lines = [_format_call(chain[0], level)]
    for call in chain[1:]:
        lines.append(f"{_INDENT * (level + 1)}.{_format_call(call, level + 1)}")
    return "\n".join(lines)


def _nested_chains(call: Call) -> list[Chain]:
    return [arg for arg in call.args if isinstance(arg, tuple) and arg]


def _format_call(call: Call, level: int) -> str:
    """One block; `level` is how far in the line it starts is indented."""
    flat = _print_call(call)
    if not _nested_chains(call) or len(flat) + len(_INDENT) * level <= _CALL_WIDTH:
        return flat

    spec = SCHEMA.get(call.op)
    assert spec is not None
    pad = _INDENT * (level + 1)
    text = f"{call.op}("
    after_macro = False
    for index, arg in enumerate(call.args):
        arg_spec = spec.args[0 if spec.spread else index]
        if isinstance(arg, tuple) and arg:
            is_macro, shown = True, format_chain(arg, level + 1)
        else:
            is_macro, shown = False, _print_value(arg, arg_spec)
        if is_macro or after_macro:
            text += ("," if index else "") + f"\n{pad}{shown}"
        else:
            text += (", " if index else "") + shown
        after_macro = is_macro
    return text + ")"


def _print_call(call: Call) -> str:
    if call.op in ("symbol", "raw"):
        return str(call.args[0]) if call.args else ""

    spec = SCHEMA.get(call.op)
    if spec is None:
        raise MacroTextError(f'Unknown block "{call.op}"')

    if spec.spread:
        printed = [_print_value(arg, spec.args[0]) for arg in call.args]
    else:
        printed: list[str] = []
        for index, value in enumerate(call.args):
            printed.append(_print_value(value, spec.args[index]))

    return f"{call.op}({', '.join(printed)})"


def _print_value(value: Value, spec: ArgSpec) -> str:
    if isinstance(value, Var):
        # `set(foo, 1)` takes the bare name, everything else a `$` prefix.
        return value.name if spec.kind is ArgKind.VARIABLE else f"${value.name}"

    if isinstance(value, tuple):
        return print_chain(value)

    if value is None:
        return "None"

    if isinstance(value, bool):
        raise MacroTextError("Booleans are not part of the macro language")

    if isinstance(value, (int, float)):
        return repr(value)

    if spec.kind in (ArgKind.SYMBOL, ArgKind.MACRO):
        if _BARE_SYMBOL.match(value):
            return value
        return f'"{value}"'

    if spec.kind is ArgKind.VARIABLE:
        return value

    # A string in a value slot: quote anything that could be read as a number,
    # None, a variable or code.
    if _BARE_WORD.match(value) and value != "None":
        return value
    return f'"{value}"'


def parse_arg(raw: str, spec: ArgSpec) -> Value:
    """The value of one argument field, as typed."""
    return _parse_value(raw, spec)


def print_arg(value: Value, spec: ArgSpec) -> str:
    """One argument as shown in its field: bare, without quotes where possible."""
    if value is None:
        return ""
    if isinstance(value, tuple):
        return print_chain(value)
    if isinstance(value, str) and spec.kind in (ArgKind.SYMBOL, ArgKind.VARIABLE):
        return value
    return _print_value(value, spec)
