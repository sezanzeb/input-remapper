# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2023 sezanzeb <proxima@sezanzeb.de>
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


"""Parse macro code"""


import inspect
import re
from typing import Optional, Any

from inputremapper.configs.validation_errors import MacroParsingError
from inputremapper.injection.macros.macro import Macro, Variable
from inputremapper.logger.logger import logger


def is_this_a_macro(output: Any):
    """Figure out if this is a macro."""
    if not isinstance(output, str):
        return False

    if "+" in output.strip():
        # for example "a + b"
        return True

    return "(" in output and ")" in output and len(output) >= 4


TASK_FACTORIES = {
    "modify": Macro.add_modify,
    "repeat": Macro.add_repeat,
    "key": Macro.add_key,
    "key_down": Macro.add_key_down,
    "key_up": Macro.add_key_up,
    "event": Macro.add_event,
    "wait": Macro.add_wait,
    "hold": Macro.add_hold,
    "hold_keys": Macro.add_hold_keys,
    "mouse": Macro.add_mouse,
    "wheel": Macro.add_wheel,
    "if_eq": Macro.add_if_eq,
    "set": Macro.add_set,
    "if_tap": Macro.add_if_tap,
    "if_single": Macro.add_if_single,
    "add": Macro.add_add,
    # Those are only kept for backwards compatibility with old macros. The space for
    # writing macro was very constrained in the past, so shorthands were introduced:
    "m": Macro.add_modify,
    "r": Macro.add_repeat,
    "k": Macro.add_key,
    "e": Macro.add_event,
    "w": Macro.add_wait,
    "h": Macro.add_hold,
    # It was not possible to adjust ifeq to support variables without breaking old
    # macros, so this function is deprecated and if_eq introduced. Kept for backwards
    # compatibility:
    "ifeq": Macro.add_ifeq,
}


def use_safe_argument_names(keyword_args):
    """Certain names cannot be used internally as parameters, Add a trailing "_".

    This is the PEP 8 compliant way of avoiding conflicts with built-ins:
    https://www.python.org/dev/peps/pep-0008/#descriptive-naming-styles

    For example the macro `if_eq(1, 1, else=k(b))` uses the else_ parameter of
    `def add_if_eq` to work.
    """
    # extend this list with parameter names that cannot be used in python, but should
    # be used in macro code.
    built_ins = ["else", "type"]

    keys = keyword_args.keys()
    for built_in in built_ins:
        if built_in in keys:
            keyword_args[f"{built_in}_"] = keyword_args[built_in]
            del keyword_args[built_in]


def get_macro_argument_names(function):
    """Certain names, like "else" or "type" cannot be used as parameters in python.

    Removes the trailing "_" for displaying them correctly.
    """
    args = inspect.getfullargspec(function).args[1:]  # don't include "self"
    arg_names = [name[:-1] if name.endswith("_") else name for name in args]

    varargs = inspect.getfullargspec(function).varargs
    if varargs:
        arg_names.append(f"*{varargs}")

    return arg_names


def get_num_parameters(function):
    """Get the number of required parameters and the maximum number of parameters."""
    fullargspec = inspect.getfullargspec(function)
    num_args = len(fullargspec.args) - 1  # one of them is `self`
    min_num_args = num_args - len(fullargspec.defaults or ())

    if fullargspec.varargs is not None:
        max_num_args = float("inf")
    else:
        max_num_args = num_args

    return min_num_args, max_num_args


def _extract_args(inner: str):
    """Extract parameters from the inner contents of a call.

    This does not parse them.

    Parameters
    ----------
    inner
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
        raise MacroParsingError(
            macro, f"Found {openings} opening and {closings} closing brackets"
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


def _split_keyword_arg(param):
    """Split "foo=bar" into "foo" and "bar".

    If not a keyward param, return None and the param.
    """
    if re.match(r"[a-zA-Z_][a-zA-Z_\d]*=.+", param):
        split = param.split("=", 1)
        return split[0], split[1]

    return None, param


def _is_number(value):
    """Check if the value can be turned into a number."""
    try:
        float(value)
        return True
    except ValueError:
        return False


def _parse_recurse(
    code: str,
    context,
    mapping,
    verbose: bool,
    macro_instance: Optional[Macro] = None,
    depth: int = 0,
):
    """Handle a subset of the macro, e.g. one parameter or function call.

    Not using eval for security reasons.

    Parameters
    ----------
    code
        Just like parse. A single parameter or the complete macro as string.
        Comments and redundant whitespace characters are expected to be removed already.
        TODO add some examples.
          Are all of "foo(1);bar(2)" "foo(1)" and "1" valid inputs?
    context : Context
    macro_instance
        A macro instance to add tasks to. This is the output of the parser, and is
        organized like a tree.
    depth
        For logging porposes
    """
    assert isinstance(code, str)
    assert isinstance(depth, int)

    def debug(*args, **kwargs):
        if verbose:
            logger.debug(*args, **kwargs)

    space = "  " * depth

    code = code.strip()

    if code == "" or code == "None":
        # A function parameter probably
        # I think "" is the deprecated alternative to "None"
        return None

    if code.startswith('"'):
        # TODO and endswith check, if endswith fails throw error?
        #  what is currently the error if only one quote is set?
        # a string, don't parse. remove quotes
        string = code[1:-1]
        debug("%sstring %s", space, string)
        return string

    if code.startswith("$"):
        # will be resolved during the macros runtime
        return Variable(code.split("$", 1)[1])

    if _is_number(code):
        if "." in code:
            code = float(code)
        else:
            code = int(code)
        debug("%snumber %s", space, code)
        return code

    # is it another macro?
    call_match = re.match(r"^(\w+)\(", code)
    call = call_match[1] if call_match else None
    if call is not None:
        if macro_instance is None:
            # start a new chain
            macro_instance = Macro(code, context, mapping)
        else:
            # chain this call to the existing instance
            assert isinstance(macro_instance, Macro)

        task_factory = TASK_FACTORIES.get(call)
        if task_factory is None:
            raise MacroParsingError(code, f"Unknown function {call}")

        # get all the stuff inbetween
        closing_bracket_position = _count_brackets(code) - 1
        inner = code[code.index("(") + 1 : closing_bracket_position]
        debug("%scalls %s with %s", space, call, inner)

        # split "3, foo=a(2, k(a).w(10))" into arguments
        raw_string_args = _extract_args(inner)

        # parse and sort the params
        positional_args = []
        keyword_args = {}
        for param in raw_string_args:
            key, value = _split_keyword_arg(param)
            parsed = _parse_recurse(
                value.strip(), context, mapping, verbose, None, depth + 1
            )
            if key is None:
                if len(keyword_args) > 0:
                    msg = f'Positional argument "{key}" follows keyword argument'
                    raise MacroParsingError(code, msg)
                positional_args.append(parsed)
            else:
                if key in keyword_args:
                    raise MacroParsingError(
                        code, f'The "{key}" argument was specified twice'
                    )
                keyword_args[key] = parsed

        debug(
            "%sadd call to %s with %s, %s",
            space,
            call,
            positional_args,
            keyword_args,
        )

        min_args, max_args = get_num_parameters(task_factory)
        num_provided_args = len(raw_string_args)
        if num_provided_args < min_args or num_provided_args > max_args:
            if min_args != max_args:
                msg = (
                    f"{call} takes between {min_args} and {max_args}, "
                    f"not {num_provided_args} parameters"
                )
            else:
                msg = f"{call} takes {min_args}, not {num_provided_args} parameters"

            raise MacroParsingError(code, msg)

        use_safe_argument_names(keyword_args)

        try:
            task_factory(macro_instance, *positional_args, **keyword_args)
        except TypeError as exception:
            raise MacroParsingError(msg=str(exception)) from exception

        # is after this another call? Chain it to the macro_instance
        more_code_exists = len(code) > closing_bracket_position + 1
        if more_code_exists:
            next_char = code[closing_bracket_position + 1]
            statement_closed = next_char == "."

            if statement_closed:
                # skip over the ")."
                chain = code[closing_bracket_position + 2 :]
                debug("%sfollowed by %s", space, chain)
                _parse_recurse(chain, context, mapping, verbose, macro_instance, depth)
            elif re.match(r"[a-zA-Z_]", next_char):
                # something like foo()bar
                raise MacroParsingError(
                    code,
                    f'Expected a "." to follow after '
                    f"{code[:closing_bracket_position + 1]}",
                )

        return macro_instance

    # It is probably either a key name like KEY_A or a variable name as in `set(var,1)`,
    # both won't contain special characters that can break macro syntax so they don't
    # have to be wrapped in quotes.
    debug("%sstring %s", space, code)
    return code


def handle_plus_syntax(macro):
    """Transform a + b + c to hold_keys(a,b,c)."""
    if "+" not in macro:
        return macro

    if "(" in macro or ")" in macro:
        raise MacroParsingError(
            macro, f'Mixing "+" and macros is unsupported: "{ macro}"'
        )

    chunks = [chunk.strip() for chunk in macro.split("+")]

    if "" in chunks:
        raise MacroParsingError(f'Invalid syntax for "{macro}"')

    output = f"hold_keys({','.join(chunks)})"

    logger.debug('Transformed "%s" to "%s"', macro, output)
    return output


def remove_whitespaces(macro, delimiter='"'):
    """Remove whitespaces, tabs, newlines and such outside of string quotes."""
    result = ""
    for i, chunk in enumerate(macro.split(delimiter)):
        # every second chunk is inside string quotes
        if i % 2 == 0:
            result += re.sub(r"\s", "", chunk)
        else:
            result += chunk
        result += delimiter

    # one extra delimiter was added
    return result[: -len(delimiter)]


def remove_comments(macro):
    """Remove comments from the macro and return the resulting code."""
    # keep hashtags inside quotes intact
    result = ""

    for i, line in enumerate(macro.split("\n")):
        for j, chunk in enumerate(line.split('"')):
            if j > 0:
                # add back the string quote
                chunk = f'"{chunk}'

            # every second chunk is inside string quotes
            if j % 2 == 0 and "#" in chunk:
                # everything from now on is a comment and can be ignored
                result += chunk.split("#")[0]
                break
            else:
                result += chunk

        if i < macro.count("\n"):
            result += "\n"

    return result


def clean(code):
    """Remove everything irrelevant for the macro."""
    return remove_whitespaces(remove_comments(code), '"')


def parse(macro: str, context=None, mapping=None, verbose: bool = True):
    """Parse and generate a Macro that can be run as often as you want.

    Parameters
    ----------
    macro
        "repeat(3, key(a).wait(10))"
        "repeat(2, key(a).key(KEY_A)).key(b)"
        "wait(1000).modify(Shift_L, repeat(2, k(a))).wait(10, 20).key(b)"
    context : Context, or None for use in Frontend
    mapping
        the mapping for the macro, or None for use in Frontend
    verbose
        log the parsing True by default
    """
    # TODO pass mapping in frontend and do the target check for keys?
    logger.debug("parsing macro %s", macro.replace("\n", ""))
    macro = clean(macro)
    macro = handle_plus_syntax(macro)

    macro_obj = _parse_recurse(macro, context, mapping, verbose)
    if not isinstance(macro_obj, Macro):
        raise MacroParsingError(macro, "The provided code was not a macro")

    return macro_obj
