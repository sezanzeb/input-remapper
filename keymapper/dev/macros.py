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

The outermost macro (in the examples below the one created by 'r',
'r' and 'w') will be started, which triggers a chain reaction to execute
all of the configured stuff.

Examples
--------
r(3, k(a).w(10)): a <10ms> a <10ms> a
r(2, k(a).k(-)).k(b): a - a - b
w(1000).m(Shift_L, r(2, k(a))).w(10).k(b): <1s> A A <10ms> b
"""


import asyncio
import re

from keymapper.logger import logger
from keymapper.config import config


# for debugging purposes
MODIFIER = 1
CHILD_MACRO = 2
SLEEP = 3
REPEAT = 4
KEYSTROKE = 5
DEBUG = 6


class _Macro:
    """Supports chaining and preparing actions."""
    def __init__(self, handler, depth):
        """Create a macro instance that can be populated with tasks.

        Parameters
        ----------
        handler : func
            A function that accepts keycodes as the first parameter and the
            key-press state as the second. 1 for down and 0 for up. The
            macro will write to this function once executed with `.run()`.
        depth : int
            0 for the outermost parent macro, 1 or greater for child macros,
            like the second argument of repeat.
        """
        self.tasks = []
        self.handler = handler
        self.depth = depth

    async def run(self):
        """Run the macro."""
        for _, task in self.tasks:
            coroutine = task()
            if asyncio.iscoroutine(coroutine):
                await coroutine

    def stop(self):
        """Stop the macro."""
        # TODO

    def modify(self, modifier, macro):
        """Do stuff while a modifier is activated.

        Parameters
        ----------
        modifier : str
        macro : _Macro
        """
        self.tasks.append((MODIFIER, lambda: self.handler(modifier, 1)))
        self.add_keycode_pause()
        self.tasks.append((CHILD_MACRO, macro.run))
        self.add_keycode_pause()
        self.tasks.append((MODIFIER, lambda: self.handler(modifier, 0)))
        self.add_keycode_pause()
        return self

    def repeat(self, repeats, macro):
        """Repeat actions.

        Parameters
        ----------
        repeats : int
        macro : _Macro
        """
        for _ in range(repeats):
            self.tasks.append((CHILD_MACRO, macro.run))
        return self

    def add_keycode_pause(self):
        """To add a pause between keystrokes."""
        sleeptime = config.get('macros.keystroke_sleep_ms', 10) / 1000

        async def sleep():
            await asyncio.sleep(sleeptime)

        self.tasks.append((SLEEP, sleep))

    def keycode(self, character):
        """Write the character."""
        self.tasks.append((KEYSTROKE, lambda: self.handler(character, 1)))
        self.add_keycode_pause()
        self.tasks.append((KEYSTROKE, lambda: self.handler(character, 0)))
        self.add_keycode_pause()
        return self

    def wait(self, sleeptime):
        """Wait time in milliseconds."""
        sleeptime /= 1000

        async def sleep():
            await asyncio.sleep(sleeptime)

        self.tasks.append((SLEEP, sleep))
        return self


def _extract_params(inner):
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


def _count_brackets(macro):
    """Find where the first opening bracket closes."""
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
                raise Exception(f'There is one ")" too much at {position}')
            if brackets == 0:
                # the closing bracket of the call
                break

    if brackets != 0:
        raise Exception(f'There are {brackets} closing brackets missing')

    return position


def _parse_recurse(macro, handler, macro_instance=None, depth=0):
    """Handle a subset of the macro, e.g. one parameter or function call.

    Parameters
    ----------
    macro : string
        Just like parse
    handler : function
        passed to _Macro constructors
    macro_instance : _Macro or None
        A macro instance to add tasks to
    depth : int
    """
    # to anyone who knows better about compilers and thinks this is horrible:
    # please make a pull request. Because it probably is.
    # not using eval for security reasons ofc. And this syntax doesn't need
    # string quotes for its params.
    # If this gets more complicated than that I'd rather make a macro
    # editor GUI and store them as json.
    assert isinstance(macro, str)
    assert callable(handler)
    assert isinstance(depth, int)

    if macro_instance is None:
        macro_instance = _Macro(handler, depth)
    else:
        assert isinstance(macro_instance, _Macro)

    macro = macro.strip()
    space = '  ' * depth

    # is it another macro?
    call_match = re.match(r'^(\w+)\(', macro)
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
            raise Exception(f'Unknown function {call}')

        # get all the stuff inbetween
        position = _count_brackets(macro)

        inner = macro[2:position - 1]

        # split "3, k(a).w(10)" into parameters
        string_params = _extract_params(inner)
        logger.spam('%scalls %s with %s', space, call, string_params)
        # evaluate the params
        params = [
            _parse_recurse(param.strip(), handler, None, depth + 1)
            for param in string_params
        ]

        logger.spam('%sadd call to %s with %s', space, call, params)
        functions[call](*params)

        # is after this another call? Chain it to the macro_instance
        if len(macro) > position and macro[position] == '.':
            chain = macro[position + 1:]
            logger.spam('%sfollowed by %s', space, chain)
            _parse_recurse(chain, handler, macro_instance, depth)

        return macro_instance

    # probably a parameter for an outer function
    try:
        macro = int(macro)
    except ValueError:
        pass
    logger.spam('%s%s %s', space, type(macro), macro)
    return macro


def parse(macro, handler):
    """parse and generate a _Macro that can be run as often as you want.

    Parameters
    ----------
    macro : string
        "r(3, k(a).w(10))"
        "r(2, k(a).k(-)).k(b)"
        "w(1000).m(Shift_L, r(2, k(a))).w(10, 20).k(b)"
    handler : func
        A function that accepts keycodes as the first parameter and the
        key-press state as the second. 1 for down and 0 for up. The
        macro will write to this function once executed with `.run()`.
    """
    # whitespaces, tabs, newlines and such don't serve a purpose. make
    # the log output clearer and the parsing easier.
    macro = re.sub(r'\s', '', macro)
    logger.spam('preparing macro %s for later execution', macro)
    try:
        return _parse_recurse(macro, handler)
    except Exception as error:
        logger.error('Failed to parse macro "%s": %s', macro, error)
        return None
