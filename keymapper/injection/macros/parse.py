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
from keymapper.injection.macros.macro import Macro, Variable


def is_this_a_macro(output):
    """Figure out if this is a macro."""
    if not isinstance(output, str):
        return False

    if "+" in output.strip():
        # for example "a + b"
        return True

    return "(" in output and ")" in output and len(output) >= 4


FUNCTIONS = {
    # shorthands for common functions because the space to type is so constrained
    "m": Macro.add_modify,
    "r": Macro.add_repeat,
    "k": Macro.add_key,
    "e": Macro.add_event,
    "w": Macro.add_wait,
    "h": Macro.add_hold,
    # add proper full function names for all other future macros
    "modify": Macro.add_modify,
    "repeat": Macro.add_repeat,
    "key": Macro.add_key,
    "event": Macro.add_event,
    "wait": Macro.add_wait,
    "hold": Macro.add_hold,
    "mouse": Macro.add_mouse,
    "wheel": Macro.add_wheel,
    "ifeq": Macro.add_ifeq,  # kept for compatibility with existing old macros
    "if_eq": Macro.add_if_eq,
    "set": Macro.add_set,
    "if_tap": Macro.add_if_tap,
    "if_single": Macro.add_if_single,
}


def use_safe_argument_names(keyword_args):
    """Certain names cannot be used internally as parameters, Add _ in front of them.

    For example the macro `if_eq(1, 1, else=k(b))` uses the _else parameter of
    `def add_if_eq` to work.
    """
    # extend this list with parameter names that cannot be used in python, but should
    # be used in macro code.
    built_ins = ["else", "type"]

    for built_in in built_ins:
        if keyword_args.get(built_in) is not None:
            keyword_args[f"_{built_in}"] = keyword_args[built_in]
            del keyword_args[built_in]


def get_num_parameters(function):
    """Get the number of required parameters and the maximum number of parameters."""
    fullargspec = inspect.getfullargspec(function)
    num_args = len(fullargspec.args) - 1  # one is `self`
    return num_args - len(fullargspec.defaults or ()), num_args


def _extract_args(inner):
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
    string = False
    for position, char in enumerate(inner):
        # ignore anything between string quotes
        if char == '"':
            string = not string
        if string:
            continue

        # ignore commas inside child macros
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
        raise SyntaxError(f"Found {openings} opening and {closings} closing brackets")

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


def _split_keyword_arg(param):
    """Split "foo=bar" into "foo" and "bar".

    If not a keyward param, return None and the param.
    """
    if re.match(r"[a-zA-Z_][a-zA-Z_\d]*=.+", param):
        split = param.split("=", 1)
        return split[0], split[1]

    return None, param


def _parse_recurse(macro, context, macro_instance=None, depth=0):
    """Handle a subset of the macro, e.g. one parameter or function call.

    Not using eval for security reasons.

    Parameters
    ----------
    macro : string
        Just like parse.
        A single parameter of a function or the complete macro as string.
    context : Context
    macro_instance : Macro or None
        A macro instance to add tasks to
    depth : int
        For logging porposes
    """
    assert isinstance(macro, str)
    assert isinstance(depth, int)

    if macro == "":
        return None

    if macro.startswith('"'):
        # a string, don't parse
        return macro[1:-1]

    if macro.startswith("$"):
        # will be resolved during the macros runtime
        return Variable(macro.split("$", 1)[1])

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
        # of their arguments
        function = FUNCTIONS.get(call)
        if function is None:
            raise Exception(f"Unknown function {call}")

        # get all the stuff inbetween
        position = _count_brackets(macro)

        inner = macro[macro.index("(") + 1 : position - 1]
        logger.spam("%scalls %s with %s", space, call, inner)

        # split "3, foo=k(a).w(10)" into arguments
        raw_string_args = _extract_args(inner)

        # parse and sort the params
        positional_args = []
        keyword_args = {}
        for param in raw_string_args:
            key, value = _split_keyword_arg(param)
            parsed = _parse_recurse(value.strip(), context, None, depth + 1)
            if key is None:
                if len(keyword_args) > 0:
                    msg = f'Positional argument "{key}" follows keyword argument'
                    raise SyntaxError(msg)
                positional_args.append(parsed)
            else:
                if key in keyword_args:
                    raise SyntaxError(f'The "{key}" argument was specified twice')
                keyword_args[key] = parsed

        logger.spam(
            "%sadd call to %s with %s, %s",
            space,
            call,
            positional_args,
            keyword_args,
        )

        min_args, max_args = get_num_parameters(function)
        num_provided_args = len(raw_string_args)
        if num_provided_args < min_args or num_provided_args > max_args:
            if min_args != max_args:
                msg = (
                    f"{call} takes between {min_args} and {max_args}, "
                    f"not {num_provided_args} parameters"
                )
            else:
                msg = f"{call} takes {min_args}, " f"not {num_provided_args} parameters"

            raise ValueError(msg)

        use_safe_argument_names(keyword_args)

        function(macro_instance, *positional_args, **keyword_args)

        # is after this another call? Chain it to the macro_instance
        if len(macro) > position and macro[position] == ".":
            chain = macro[position + 1 :]
            logger.spam("%sfollowed by %s", space, chain)
            _parse_recurse(chain, context, macro_instance, depth)

        return macro_instance

    # at this point it is still a string since no previous rule matched
    assert isinstance(macro, str)

    try:
        # If it can be parsed as number, then it's probably a parameter to a function.
        # It isn't really needed to parse it here, but is nice for the logs.
        macro = int(macro)
    except ValueError:
        try:
            macro = float(macro)
        except ValueError:
            # use as string instead
            # If a string, it is probably either a key name like KEY_A or a variable
            # name as n `set(var, 1)`, both won't contain special characters that can
            # break macro syntax so they don't have to be wrapped in quotes.
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


def _remove_whitespaces(macro, delimiter='"'):
    """Remove whitespaces, tabs, newlines and such outside of string quotes."""
    result = ""
    for i, chunk in enumerate(macro.split(delimiter)):
        if i % 2 == 0:
            result += re.sub(r"\s", "", chunk)
        else:
            result += chunk
        result += delimiter

    # one extra delimiter was added
    return result[: -len(delimiter)]


def parse(macro, context, return_errors=False):
    """parse and generate a Macro that can be run as often as you want.

    If it could not be parsed, possibly due to syntax errors, will log the
    error and return None.

    Parameters
    ----------
    macro : string
        "r(3, k(a).w(10))"
        "r(2, k(a).k(KEY_A)).k(b)"
        "w(1000).m(Shift_L, r(2, k(a))).w(10, 20).k(b)"
    context : Context
    return_errors : bool
        If True, returns errors as a string or None if parsing worked.
        If False, returns the parsed macro.
    """
    macro = handle_plus_syntax(macro)

    macro = _remove_whitespaces(macro, '"')

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
