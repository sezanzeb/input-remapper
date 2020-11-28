#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2020 sezanzeb <proxima@hip70890b.de>
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


"""Executes more complex patterns of keystrokes.

To keep it short on the UI, the available functions are one-letter long.

The global functions actually perform the stuff and always return macro
instances that can then be further chained.

the outermost macro (in the examples below the one created by 'r',
'r' and 'w') will be started, which triggers a chain reaction to execute
all of the configured stuff.

Examples
--------
r(3, k('a').w(10)): 'a' <10ms> 'a' <10ms> 'a'
r(2, k('a').k('-')).k('b'): 'a' '-' 'a' '-' 'b'
w(1000).m('SHIFT_L', r(2, k('a'))).w(10).k('b'): <1s> 'A' 'A' <10ms> 'b'
"""


import time
import re
import random

try:
    from rich.traceback import install
    install(show_locals=True)
except ImportError:
    pass

from keymapper.logger import logger

logger.setLevel(5)

class Macro:
    """Supports chaining and preparing actions."""
    def __init__(self):
        self.tasks = []

    def run(self):
        """Run the macro."""
        for task in self.tasks:
            # TODO async, don't block the rest of the application
            task()

    def stop(self):
        """Stop the macro."""
        # TODO

    def modify(self, modifier, macro):
        """Do stuff while a modifier is activated.

        Parameters
        ----------
        modifier : str
        macro : Macro
        """
        # TODO press modifier down
        self.tasks.append(macro.run)
        # TODO release modifier
        return self

    def repeat(self, repeats, macro):
        """Repeat actions.

        Parameters
        ----------
        repeats : int
        macro : Macro
        """
        for _ in range(repeats):
            self.tasks.append(macro.run)
        return self

    def keycode(self, character):
        """Write the character."""
        # TODO write character
        self.tasks.append(lambda: print(character))
        return self

    def wait(self, min, max=None):
        """Wait a random time in milliseconds"""
        # TODO random
        self.tasks.append(lambda: time.sleep(min / 1000))
        return self


def parse(macro):
    """parse and generate a Macro that can be run as often as you want.

    Parameters
    ----------
    macro : string
        "r(3, k(a).w(10))"
        "r(2, k(a).k(-)).k(b)"
        "w(1000).m(SHIFT_L, r(2, k(a))).w(10, 20).k(b)"
    """
    try:
        return parse_recurse(macro)
    except Exception as e:
        logger.error(e)
    # parsing unsuccessful
    return None


def extract_params(inner):
    """Extract parameters from the inner contents of a call.

    Parameters
    ----------
    inner : string
        for example 'r, r(2, k(a))' should result in ['r', 'r(2, k(a)']
    """
    inner = inner.strip()
    brackets = 0
    params = []
    start = 0
    for position, char in enumerate(inner):
        if char == '(':
            brackets += 1
        if char == ')':
            brackets -= 1
        if (char == ',') and brackets == 0:
            # , potentially starts another parameter, but only if
            # the current brackets are all closed.
            params.append(inner[start:position].strip())
            # skip the comma
            start = position + 1

    if brackets == 0 and start != len(inner):
        # one last parameter
        params.append(inner[start:].strip())

    return params


def parse_recurse(macro, macro_instance=None, depth=0):
    """Handle a subset of the macro, e.g. one parameter or function call.

    Parameters
    ----------
    macro : string
        Just like parse
    macro_instance : Macro or None
        A macro instance to add tasks to
    depth : int
        For logging and debugging purposes
    """
    # to anyone who knows better about compilers and thinks this is horrible:
    # please make a pull request. Because it probably is.
    # not using eval for security reasons ofc. And this syntax doesn't need
    # string quotes for its params.
    if macro_instance is None:
        macro_instance = Macro()

    macro = macro.strip()
    logger.spam('%sinput %s', '  ' * depth, macro)
    space = '  ' * depth

    # is it another macro?
    call_match = re.match(r'^(\w+)\(.+?', macro)
    call = call_match[1] if call_match else None
    if call is not None:
        # available functions in the macro
        functions = {
            'm': macro_instance.modify,
            'r': macro_instance.repeat,
            'k': macro_instance.keycode,
            'w': macro_instance.wait
        }

        if functions.get(call) is None:
            logger.error(f'Unknown function %s', call)

        # get all the stuff inbetween
        brackets = 0
        position = 0
        for char in macro:
            position += 1

            if char == '(':
                brackets += 1
                continue

            if char == ')':
                brackets -= 1
                if brackets < 0:
                    logger.error(f'There is one ")" too much at %s', position)
                    return
                if brackets == 0:
                    # the closing bracket of the call
                    break

        if brackets != 0:
            logger.error(f'There are %s closing brackets missing', brackets)

        inner = macro[2:position - 1]

        # split "3, k(a).w(10)" into parameters
        string_params = extract_params(inner)
        logger.spam('%scalls %s with %s', space, call, string_params)
        # evaluate the params
        params = [
            parse_recurse(param.strip(), None, depth + 1)
            for param in string_params
        ]

        logger.spam('%scalling %s with %s', space, call, params)
        functions[call](*params)

        # is after this another call? Chain it to the macro_instance
        if len(macro) > position and macro[position] == '.':
            chain = macro[position + 1:]
            logger.spam('%sfollowed by %s', space, chain)
            parse_recurse(chain, macro_instance, depth)

        return macro_instance
    else:
        # probably a parameter for an outer function
        try:
            macro = int(macro)
        except ValueError:
            pass
        return macro


parse("k(1).k(2).k(3)").run()
parse("r(1, k(2))").run()
parse("r(3, k(a).w(10))").run()
parse("r(2, k(a).k(-)).k(b)").run()
parse("w(1000).m(SHIFT_L, r(2, k(a))).w(10, 20).k(b)").run()
