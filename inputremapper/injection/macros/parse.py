# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2025 sezanzeb <b8x45ygc9@mozmail.com>
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

from __future__ import annotations

import re
from typing import Optional, Any, Type, TYPE_CHECKING, Dict, List

from inputremapper.configs.validation_errors import MacroError
from inputremapper.injection.macros.macro import Macro
from inputremapper.injection.macros.raw_value import RawValue
from inputremapper.injection.macros.task import Task
from inputremapper.injection.macros.tasks.add import AddTask
from inputremapper.injection.macros.tasks.event import EventTask
from inputremapper.injection.macros.tasks.hold import HoldTask
from inputremapper.injection.macros.tasks.hold_keys import HoldKeysTask
from inputremapper.injection.macros.tasks.if_eq import IfEqTask
from inputremapper.injection.macros.tasks.if_led import IfNumlockTask, IfCapslockTask
from inputremapper.injection.macros.tasks.if_single import IfSingleTask
from inputremapper.injection.macros.tasks.if_tap import IfTapTask
from inputremapper.injection.macros.tasks.ifeq import DeprecatedIfEqTask
from inputremapper.injection.macros.tasks.key import KeyTask
from inputremapper.injection.macros.tasks.key_down import KeyDownTask
from inputremapper.injection.macros.tasks.key_up import KeyUpTask
from inputremapper.injection.macros.tasks.mod_tap import ModTapTask
from inputremapper.injection.macros.tasks.modify import ModifyTask
from inputremapper.injection.macros.tasks.mouse import MouseTask
from inputremapper.injection.macros.tasks.parallel import ParallelTask
from inputremapper.injection.macros.tasks.mouse_xy import MouseXYTask
from inputremapper.injection.macros.tasks.repeat import RepeatTask
from inputremapper.injection.macros.tasks.set import SetTask
from inputremapper.injection.macros.tasks.wait import WaitTask
from inputremapper.injection.macros.tasks.wheel import WheelTask
from inputremapper.logging.logger import logger

if TYPE_CHECKING:
    from inputremapper.injection.context import Context
    from inputremapper.configs.mapping import Mapping


class Parser:
    TASK_CLASSES: dict[str, type[Task]] = {
        "modify": ModifyTask,
        "repeat": RepeatTask,
        "key": KeyTask,
        "key_down": KeyDownTask,
        "key_up": KeyUpTask,
        "event": EventTask,
        "wait": WaitTask,
        "hold": HoldTask,
        "hold_keys": HoldKeysTask,
        "mouse": MouseTask,
        "mouse_xy": MouseXYTask,
        "wheel": WheelTask,
        "if_eq": IfEqTask,
        "if_numlock": IfNumlockTask,
        "if_capslock": IfCapslockTask,
        "set": SetTask,
        "if_tap": IfTapTask,
        "if_single": IfSingleTask,
        "add": AddTask,
        "mod_tap": ModTapTask,
        "parallel": ParallelTask,
        # Those are only kept for backwards compatibility with old macros. The space for
        # writing macro was very constrained in the past, so shorthands were introduced:
        "m": ModifyTask,
        "r": RepeatTask,
        "k": KeyTask,
        "e": EventTask,
        "w": WaitTask,
        "h": HoldTask,
        # It was not possible to adjust ifeq to support variables without breaking old
        # macros, so this function is deprecated and if_eq introduced. Kept for backwards
        # compatibility:
        "ifeq": DeprecatedIfEqTask,
    }

    @staticmethod
    def is_this_a_macro(output: Any):
        """Figure out if this is a macro."""
        if not isinstance(output, str):
            return False

        if "+" in output.strip():
            # for example "a + b"
            return True

        return "(" in output and ")" in output and len(output) >= 4

    @staticmethod
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

    @staticmethod
    def _count_brackets(macro):
        """Find where the first opening bracket closes."""
        openings = macro.count("(")
        closings = macro.count(")")
        if openings != closings:
            raise MacroError(
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

    @staticmethod
    def _split_keyword_arg(param):
        """Split "foo=bar" into "foo" and "bar".

        If not a keyward param, return None and the param.
        """
        if re.match(r"[a-zA-Z_][a-zA-Z_\d]*=.+", param):
            split = param.split("=", 1)
            return split[0], split[1]

        return None, param

    @staticmethod
    def _validate_keyword_argument_names(
        keyword_args: Dict[str, Any],
        task_class: Type[Task],
    ) -> None:
        for keyword_arg in keyword_args:
            for argument in task_class.argument_configs:
                if argument.name == keyword_arg:
                    break
            else:
                raise MacroError(msg=f"Unknown keyword argument {keyword_arg}")

    @staticmethod
    def _parse_recurse(
        code: str,
        context: Optional[Context],
        mapping: Mapping,
        verbose: bool,
        macro_instance: Optional[Macro] = None,
        depth: int = 0,
    ) -> RawValue:
        """Handle a subset of the macro, e.g. one parameter or function call.

        Not using eval for security reasons.

        Parameters
        ----------
        code
            Just like parse. A single parameter or the complete macro as string.
            Comments and redundant whitespace characters are expected to be removed already.
            Example:
            - "parallel(key(a),key(b).key($foo))"
            - "key(a)"
            - "a"
            - "key(b).key($foo)"
            - "b"
            - "key($foo)"
            - "$foo"
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

        # is it another macro?
        task_call_match = re.match(r"^(\w+)\(", code)
        task_name = task_call_match[1] if task_call_match else None

        if task_name is None:
            # It is probably either a key name like KEY_A or a variable name as in `set(var,1)`,
            # both won't contain special characters that can break macro syntax so they don't
            # have to be wrapped in quotes. The argument configuration of the tasks will
            # detemrine how to parse it.
            debug("%svalue %s", space, code)
            return RawValue(value=code)

        if macro_instance is None:
            # start a new chain
            macro_instance = Macro(code, context, mapping)
        else:
            # chain this call to the existing instance
            assert isinstance(macro_instance, Macro)

        task_class = Parser.TASK_CLASSES.get(task_name)
        if task_class is None:
            raise MacroError(code, f"Unknown function {task_name}")

        # get all the stuff inbetween
        closing_bracket_position = Parser._count_brackets(code) - 1
        inner = code[code.index("(") + 1 : closing_bracket_position]
        debug("%scalls %s with %s", space, task_name, inner)

        # split "3, foo=a(2, k(a).w(10))" into arguments
        raw_string_args = Parser._extract_args(inner)

        # parse and sort the params
        positional_args: List[RawValue] = []
        keyword_args: Dict[str, RawValue] = {}
        for param in raw_string_args:
            key, value = Parser._split_keyword_arg(param)
            parsed = Parser._parse_recurse(
                value.strip(),
                context,
                mapping,
                verbose,
                None,
                depth + 1,
            )
            if key is None:
                if len(keyword_args) > 0:
                    msg = f'Positional argument "{key}" follows keyword argument'
                    raise MacroError(code, msg)
                positional_args.append(parsed)
            else:
                if key in keyword_args:
                    raise MacroError(code, f'The "{key}" argument was specified twice')
                keyword_args[key] = parsed

        debug(
            "%sadd call to %s with %s, %s",
            space,
            task_name,
            positional_args,
            keyword_args,
        )

        Parser._validate_keyword_argument_names(
            keyword_args,
            task_class,
        )
        Parser._validate_num_args(
            code,
            task_name,
            task_class,
            raw_string_args,
        )

        try:
            task = task_class(
                positional_args,
                keyword_args,
                context,
                mapping,
            )
            macro_instance.add_task(task)
        except TypeError as exception:
            raise MacroError(msg=str(exception)) from exception

        # is after this another call? Chain it to the macro_instance
        more_code_exists = len(code) > closing_bracket_position + 1
        if more_code_exists:
            next_char = code[closing_bracket_position + 1]
            statement_closed = next_char == "."

            if statement_closed:
                # skip over the ")."
                chain = code[closing_bracket_position + 2 :]
                debug("%sfollowed by %s", space, chain)
                Parser._parse_recurse(
                    chain,
                    context,
                    mapping,
                    verbose,
                    macro_instance,
                    depth,
                )
            elif re.match(r"[a-zA-Z_]", next_char):
                # something like foo()bar
                raise MacroError(
                    code,
                    f'Expected a "." to follow after '
                    f"{code[:closing_bracket_position + 1]}",
                )

        return RawValue(value=macro_instance)

    @staticmethod
    def _validate_num_args(
        code: str,
        task_name: str,
        task_class: Type[Task],
        raw_string_args: List[str],
    ) -> None:
        min_args, max_args = task_class.get_num_parameters()
        num_provided_args = len(raw_string_args)
        if num_provided_args < min_args or num_provided_args > max_args:
            if min_args != max_args:
                msg = (
                    f"{task_name} takes between {min_args} and {max_args}, "
                    f"not {num_provided_args} parameters"
                )
            else:
                msg = (
                    f"{task_name} takes {min_args}, not {num_provided_args} parameters"
                )

            raise MacroError(code, msg)

    @staticmethod
    def handle_plus_syntax(macro):
        """Transform a + b + c to hold_keys(a,b,c)."""
        if "+" not in macro:
            return macro

        if "(" in macro or ")" in macro:
            raise MacroError(macro, f'Mixing "+" and macros is unsupported: "{ macro}"')

        chunks = [chunk.strip() for chunk in macro.split("+")]

        if "" in chunks:
            raise MacroError(f'Invalid syntax for "{macro}"')

        output = f"hold_keys({','.join(chunks)})"

        logger.debug('Transformed "%s" to "%s"', macro, output)
        return output

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    def clean(code):
        """Remove everything irrelevant for the macro."""
        return Parser.remove_whitespaces(
            Parser.remove_comments(code),
            '"',
        )

    @staticmethod
    def parse(macro: str, context=None, mapping=None, verbose: bool = True) -> Macro:
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
        macro = Parser.clean(macro)
        macro = Parser.handle_plus_syntax(macro)

        macro_obj = Parser._parse_recurse(
            macro,
            context,
            mapping,
            verbose,
        ).value
        if not isinstance(macro_obj, Macro):
            raise MacroError(macro, "The provided code was not a macro")

        return macro_obj
