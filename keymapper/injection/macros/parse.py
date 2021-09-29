#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@sezanzeb.de>
#
# This file is part of key-mapper.
#
# key-mapper is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# key-mapper is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with key-mapper.  If not, see <https://www.gnu.org/licenses/>.


"""Parse macro code"""


import re
import traceback
import inspect

from keymapper.logger import logger
from keymapper.injection.macros.macro import Macro


def is_this_a_macro(output):
    """Figure out if this is a macro."""
    if not isinstance(output, str):
        return False

    if "+" in output.strip():
        # for example "a + b"
        return True

    return "(" in output and ")" in output and len(output) >= 4


FUNCTIONS = {
    "m": Macro.modify,
    "r": Macro.repeat,
    "k": Macro.keycode,
    "e": Macro.event,
    "w": Macro.wait,
    "h": Macro.hold,
    "mouse": Macro.mouse,
    "wheel": Macro.wheel,
    "ifeq": Macro.ifeq,
    "set": Macro.set,
    "if_tap": Macro.if_tap,
    "if_single": Macro.if_single,
}


def get_num_parameters(function):
    """Get the number of required parameters and the maximum number of parameters."""
    fullargspec = inspect.getfullargspec(function)
    num_args = len(fullargspec.args) - 1  # one is `self`
    return num_args - len(fullargspec.defaults or ()), num_args


def _extract_params(inner):
    """Extract parameters from the inner contents of a call.

    This does not parse them.

    Parameters
    ----------
    inner : string
        for example '1, r, r(2, k(a))' should result in ['1', 'r', 'r(2, k(a))']
    """
    inner = inner.strip()
    brackets = 0
    params = []
    start = 0
    for position, char in enumerate(inner):
        if char == "(":
            brackets += 1
        if char == ")":
            brackets -= 1
        if char == "," and brackets == 0:
            # , potentially starts another parameter, but only if
            # the current brackets are all closed.
            params.append(inner[start:position].strip())
            # skip the comma
            start = position + 1

    # one last parameter
    params.append(inner[start:].strip())

    return params


def _count_brackets(macro):
    """Find where the first opening bracket closes."""
    openings = macro.count("(")
    closings = macro.count(")")
    if openings != closings:
        raise Exception(
            f"You entered {openings} opening and {closings} " "closing brackets"
        )

    brackets = 0
    position = 0
    for char in macro:
        position += 1
        if char == "(":
            brackets += 1
            continue

        if char == ")":
            brackets -= 1
            if brackets == 0:
                # the closing bracket of the call
                break

    return position


def _parse_recurse(macro, context, macro_instance=None, depth=0):
    """Handle a subset of the macro, e.g. one parameter or function call.

    Parameters
    ----------
    macro : string
        Just like parse
    context : Context
    macro_instance : Macro or None
        A macro instance to add tasks to
    depth : int
    """
    # not using eval for security reasons
    assert isinstance(macro, str)
    assert isinstance(depth, int)

    if macro == "":
        return None

    if macro_instance is None:
        macro_instance = Macro(macro, context)
    else:
        assert isinstance(macro_instance, Macro)

    macro = macro.strip()
    space = "  " * depth

    # is it another macro?
    call_match = re.match(r"^(\w+)\(", macro)
    call = call_match[1] if call_match else None
    if call is not None:
        # available functions in the macro and the minimum and maximum number
        # of their parameters
        function = FUNCTIONS.get(call)
        if function is None:
            raise Exception(f"Unknown function {call}")

        # get all the stuff inbetween
        position = _count_brackets(macro)

        inner = macro[macro.index("(") + 1 : position - 1]

        # split "3, k(a).w(10)" into parameters
        string_params = _extract_params(inner)
        logger.spam("%scalls %s with %s", space, call, string_params)
        # evaluate the params
        params = [
            _parse_recurse(param.strip(), context, None, depth + 1)
            for param in string_params
        ]

        logger.spam("%sadd call to %s with %s", space, call, params)

        min_params, max_params = get_num_parameters(function)
        if len(params) < min_params or len(params) > max_params:
            if min_params != max_params:
                msg = (
                    f"{call} takes between {min_params} and {max_params}, "
                    f"not {len(params)} parameters"
                )
            else:
                msg = f"{call} takes {min_params}, " f"not {len(params)} parameters"

            raise ValueError(msg)

        function(macro_instance, *params)

        # is after this another call? Chain it to the macro_instance
        if len(macro) > position and macro[position] == ".":
            chain = macro[position + 1 :]
            logger.spam("%sfollowed by %s", space, chain)
            _parse_recurse(chain, context, macro_instance, depth)

        return macro_instance

    # probably a parameter for an outer function
    try:
        # if possible, parse as int
        macro = int(macro)
    except ValueError:
        # use as string instead
        pass

    logger.spam("%s%s %s", space, type(macro), macro)
    return macro


def handle_plus_syntax(macro):
    """transform a + b + c to m(a, m(b, m(c, h())))"""
    if "+" not in macro:
        return macro

    if "(" in macro or ")" in macro:
        logger.error('Mixing "+" and macros is unsupported: "%s"', macro)
        return macro

    chunks = [chunk.strip() for chunk in macro.split("+")]
    output = ""
    depth = 0
    for chunk in chunks:
        if chunk == "":
            # invalid syntax
            logger.error('Invalid syntax for "%s"', macro)
            return macro

        depth += 1
        output += f"m({chunk},"

    output += "h()"
    output += depth * ")"

    logger.debug('Transformed "%s" to "%s"', macro, output)
    return output


def parse(macro, context, return_errors=False):
    """parse and generate a Macro that can be run as often as you want.

    If it could not be parsed, possibly due to syntax errors, will log the
    error and return None.

    Parameters
    ----------
    macro : string
        "r(3, k(a).w(10))"
        "r(2, k(a).k(-)).k(b)"
        "w(1000).m(Shift_L, r(2, k(a))).w(10, 20).k(b)"
    context : Context
    return_errors : bool
        If True, returns errors as a string or None if parsing worked.
        If False, returns the parsed macro.
    """
    macro = handle_plus_syntax(macro)

    # whitespaces, tabs, newlines and such don't serve a purpose. make
    # the log output clearer and the parsing easier.
    macro = re.sub(r"\s", "", macro)

    if '"' in macro or "'" in macro:
        logger.info("Quotation marks in macros are not needed")
        macro = macro.replace('"', "").replace("'", "")

    if return_errors:
        logger.spam("checking the syntax of %s", macro)
    else:
        logger.spam("preparing macro %s for later execution", macro)

    try:
        macro_object = _parse_recurse(macro, context)
        return macro_object if not return_errors else None
    except Exception as error:
        logger.error('Failed to parse macro "%s": %s', macro, error.__repr__())
        # print the traceback in case this is a bug of key-mapper
        logger.debug("".join(traceback.format_tb(error.__traceback__)).strip())
        return f"{error.__class__.__name__}: {str(error)}" if return_errors else None
