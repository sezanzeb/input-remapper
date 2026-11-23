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


"""Edits of a macro tree, addressed by path. No GTK.

The block editor shows a tree of stacks: a stack is a chain, and a block may hold
nested stacks in its macro arguments (the C-shaped slots). A *chain path* names one
stack: each step is `(call index, argument index)`, going into that call's argument.
The empty path is the top level stack. All functions return new trees.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from inputremapper.gui_v3.schema import SCHEMA, ArgKind, ArgSpec
from inputremapper.gui_v3.tree import Call, Chain, Value, Var, is_chain

ChainPath = tuple[tuple[int, int], ...]

# What a new block starts with, per kind of argument.
_DEFAULT_SYMBOL = ""


def default_value(spec: ArgSpec) -> Value:
    """A valid starting value for an argument."""
    if spec.kind is ArgKind.MACRO:
        return ()
    if spec.kind is ArgKind.SYMBOL:
        return _DEFAULT_SYMBOL
    if spec.kind is ArgKind.VARIABLE:
        return Var("")
    if spec.accepts_number:
        return 1 if spec.name in ("repeats", "speed") else 0
    return ""


def default_call(op: str) -> Call:
    """A new block of this kind with every required argument filled in."""
    if op == "symbol":
        return Call("symbol", (_DEFAULT_SYMBOL,))
    spec = SCHEMA[op]
    if spec.spread:
        return Call(op, (default_value(spec.args[0]),))
    args = [default_value(a) if a.required else a.default for a in spec.args]
    if op == "wait":
        args[0] = 100
    return Call.make(op, *args)


def full_args(call: Call) -> list[Value]:
    """The arguments including the trailing ones that equal their default."""
    spec = SCHEMA.get(call.op)
    args = list(call.args)
    if spec is None or spec.spread:
        return args
    for arg_spec in spec.args[len(args) :]:
        args.append(
            arg_spec.default if not arg_spec.required else default_value(arg_spec)
        )
    return args


def slot_chain(value: Value) -> Chain:
    """The stack inside a macro argument; an unset slot is an empty stack."""
    return cast("Chain", value) if is_chain(value) else ()


def _with_arg(call: Call, index: int, value: Value) -> Call:
    spec = SCHEMA.get(call.op)
    args = full_args(call)
    if spec is not None and spec.spread:
        while len(args) <= index:
            args.append(default_value(spec.args[0]))
        args[index] = value
        return Call(call.op, tuple(args))
    if (
        spec is not None
        and spec.args[index].kind is ArgKind.MACRO
        and is_chain(value)
        and not value
        and not spec.args[index].required
    ):
        value = None  # An empty optional slot is written as "not given".
    args[index] = value
    return Call.make(call.op, *args)


def get_chain(root: Chain, path: ChainPath) -> Chain:
    chain = root
    for call_index, arg_index in path:
        chain = slot_chain(full_args(chain[call_index])[arg_index])
    return chain


def update_chain(
    root: Chain, path: ChainPath, change: Callable[[Chain], Chain]
) -> Chain:
    """Replace the stack at `path` by `change(stack)`."""
    if not path:
        return change(root)
    (call_index, arg_index), rest = path[0], path[1:]
    call = root[call_index]
    inner = slot_chain(full_args(call)[arg_index])
    new_call = _with_arg(call, arg_index, update_chain(inner, rest, change))
    return root[:call_index] + (new_call,) + root[call_index + 1 :]


def insert_call(root: Chain, path: ChainPath, index: int, call: Call) -> Chain:
    def change(chain: Chain) -> Chain:
        position = max(0, min(index, len(chain)))
        return chain[:position] + (call,) + chain[position:]

    return update_chain(root, path, change)


def remove_call(root: Chain, path: ChainPath, index: int) -> Chain:
    return update_chain(root, path, lambda c: c[:index] + c[index + 1 :])


def set_arg(
    root: Chain, path: ChainPath, call_index: int, arg_index: int, value: Value
) -> Chain:
    def change(chain: Chain) -> Chain:
        new_call = _with_arg(chain[call_index], arg_index, value)
        return chain[:call_index] + (new_call,) + chain[call_index + 1 :]

    return update_chain(root, path, change)


def remove_spread_arg(
    root: Chain, path: ChainPath, call_index: int, arg_index: int
) -> Chain:
    def change(chain: Chain) -> Chain:
        call = chain[call_index]
        args = call.args[:arg_index] + call.args[arg_index + 1 :]
        return chain[:call_index] + (Call(call.op, args),) + chain[call_index + 1 :]

    return update_chain(root, path, change)


def _is_inside(path: ChainPath, call_path: ChainPath, call_index: int) -> bool:
    """Whether `path` is within the call at `call_path` + `call_index`."""
    depth = len(call_path)
    return (
        len(path) > depth and path[:depth] == call_path and path[depth][0] == call_index
    )


def can_move(src_path: ChainPath, src_index: int, dst_path: ChainPath) -> bool:
    """A block can't be dropped into itself."""
    return not _is_inside(dst_path, src_path, src_index)


def move_call(
    root: Chain,
    src_path: ChainPath,
    src_index: int,
    dst_path: ChainPath,
    dst_index: int,
) -> Chain:
    """Move a block, with whatever it holds, to a gap in any stack.

    `dst_index` is the gap as it looks before the move (gap 0 is above the first
    block). Moving next to itself changes nothing.
    """
    if not can_move(src_path, src_index, dst_path):
        raise ValueError("A block can't be moved into itself")

    call = get_chain(root, src_path)[src_index]
    removed = remove_call(root, src_path, src_index)

    # Removing the block shifts what comes after it in its stack, including the
    # stacks nested in those blocks.
    depth = len(src_path)
    if dst_path[:depth] == src_path and len(dst_path) > depth:
        call_index, arg_index = dst_path[depth]
        if call_index > src_index:
            dst_path = (
                dst_path[:depth]
                + ((call_index - 1, arg_index),)
                + dst_path[depth + 1 :]
            )
    elif dst_path == src_path and dst_index > src_index:
        dst_index -= 1

    return insert_call(removed, dst_path, dst_index, call)


def call_gap(call: Call) -> str | None:
    """What a block itself is missing, or None. Nested blocks are not looked at."""
    if call.op == "symbol" and not (call.args and call.args[0]):
        return 'a "type" block has no key chosen'
    spec = SCHEMA.get(call.op)
    if spec is None:
        return None
    for index, value in enumerate(call.args):
        arg = spec.args[0 if spec.spread else index]
        if arg.kind is ArgKind.SYMBOL and value == "":
            return f'a "{call.op}" block has no key chosen'
        if arg.kind is ArgKind.VARIABLE and isinstance(value, Var) and not value.name:
            return f'a "{call.op}" block has no variable chosen'
        if arg.kind is ArgKind.MACRO and arg.required and not slot_chain(value):
            return f'a "{call.op}" block is empty'
    return None


def first_gap(chain: Chain, _top: bool = True) -> str | None:
    """The first thing missing anywhere in the macro, or None if it is complete."""
    # An output key is a mapping's whole output, not a step of a macro.
    if any(call.op == "symbol" for call in chain) and (len(chain) > 1 or not _top):
        return 'a "type" block can\'t be combined with other blocks'
    for call in chain:
        gap = call_gap(call)
        if gap is not None:
            return gap
        spec = SCHEMA.get(call.op)
        if spec is None:
            continue
        for value in call.args:
            if is_chain(value):
                inner = first_gap(cast("Chain", value), False)
                if inner is not None:
                    return inner
    return None
