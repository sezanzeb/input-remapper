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


"""Executes more complex patterns of keystrokes.

To keep it short on the UI, basic functions are one letter long.

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
import traceback
import copy
import multiprocessing
import atexit
import select

from evdev.ecodes import ecodes, EV_KEY, EV_REL, REL_X, REL_Y, REL_WHEEL, \
    REL_HWHEEL

from keymapper.logger import logger
from keymapper.state import system_mapping


class SharedDict:
    """Share a dictionary across processes."""
    # because unittests terminate all child processes in cleanup I can't use
    # multiprocessing.Manager
    def __init__(self):
        """Create a shared dictionary."""
        super().__init__()
        self.pipe = multiprocessing.Pipe()
        self.process = None
        atexit.register(self._stop)
        self._start()

        # To avoid blocking forever if something goes wrong. The maximum
        # observed time communication takes was 0.001 for me on a slow pc
        self._timeout = 0.02

    def _start(self):
        """Ensure the process to manage the dictionary is running."""
        if self.process is not None and self.process.is_alive():
            return

        # if the manager has already been running in the past but stopped
        # for some reason, the dictionary contents are lost
        self.process = multiprocessing.Process(target=self.manage)
        self.process.start()

    def manage(self):
        """Manage the dictionary, handle read and write requests."""
        shared_dict = dict()
        while True:
            message = self.pipe[0].recv()
            logger.spam('SharedDict got %s', message)

            if message[0] == 'stop':
                return

            if message[0] == 'set':
                shared_dict[message[1]] = message[2]

            if message[0] == 'get':
                self.pipe[0].send(shared_dict.get(message[1]))

            if message[0] == 'ping':
                self.pipe[0].send('pong')

    def _stop(self):
        """Stop the managing process."""
        self.pipe[1].send(('stop',))

    def get(self, key):
        """Get a value from the dictionary."""
        return self.__getitem__(key)

    def is_alive(self, timeout=None):
        """Check if the manager process is running."""
        self.pipe[1].send(('ping',))
        select.select([self.pipe[1]], [], [], timeout or self._timeout)
        if self.pipe[1].poll():
            return self.pipe[1].recv() == 'pong'

        return False

    def __setitem__(self, key, value):
        self.pipe[1].send(('set', key, value))

    def __getitem__(self, key):
        self.pipe[1].send(('get', key))

        select.select([self.pipe[1]], [], [], self._timeout)
        if self.pipe[1].poll():
            return self.pipe[1].recv()

        logger.error('select.select timed out')
        return None

    def __del__(self):
        self._stop()


macro_variables = SharedDict()


def is_this_a_macro(output):
    """Figure out if this is a macro."""
    if not isinstance(output, str):
        return False

    if '+' in output.strip():
        # for example "a + b"
        return True

    return '(' in output and ')' in output and len(output) >= 4


class _Macro:
    """Supports chaining and preparing actions.

    Calling functions like keycode on _Macro doesn't inject any events yet,
    it means that once .run is used it will be executed along with all other
    queued tasks.

    Those functions need to construct an asyncio coroutine and append it to
    self.tasks. This makes parameter checking during compile time possible.
    Coroutines receive a handler as argument, which is a function that can be
    used to inject input events into the system.
    """
    def __init__(self, code, mapping):
        """Create a macro instance that can be populated with tasks.

        Parameters
        ----------
        code : string or None
            The original parsed code, for logging purposes.
        mapping : Mapping
            The preset object, needed for some config stuff
        """
        self.code = code
        self.mapping = mapping

        # List of coroutines that will be called sequentially.
        # This is the compiled code
        self.tasks = []

        # is a lock so that h() can be realized
        self._holding_lock = asyncio.Lock()

        self.running = False

        # all required capabilities, without those of child macros
        self.capabilities = {
            EV_KEY: set(),
            EV_REL: set(),
        }

        self.child_macros = []
        
        self.keystroke_sleep_ms = None

    def is_holding(self):
        """Check if the macro is waiting for a key to be released."""
        return self._holding_lock.locked()

    def get_capabilities(self):
        """Resolve all capabilities of the macro and those of its children."""
        capabilities = copy.deepcopy(self.capabilities)

        for macro in self.child_macros:
            macro_capabilities = macro.get_capabilities()
            for ev_type in macro_capabilities:
                if ev_type not in capabilities:
                    capabilities[ev_type] = set()

                capabilities[ev_type].update(macro_capabilities[ev_type])

        return capabilities

    async def run(self, handler):
        """Run the macro.

        Parameters
        ----------
        handler : function
            Will receive int type, code and value for an event to write
        """
        if self.running:
            logger.error('Tried to run already running macro "%s"', self.code)
            return
        
        self.keystroke_sleep_ms = self.mapping.get('macros.keystroke_sleep_ms')

        self.running = True
        for task in self.tasks:
            # one could call tasks the compiled macros. it's lambda functions
            # that receive the handler as an argument, so that they know
            # where to send the event to.
            coroutine = task(handler)

            if (self.is_holding() == False and coroutine.__name__ == "sleep"):
                break

            if asyncio.iscoroutine(coroutine):
                await coroutine
                if (self.is_holding() == False and coroutine.__name__ == "sleep"):
                    break

        # done
        self.running = False

    def press_key(self):
        """The user pressed the key down."""
        if self.is_holding():
            logger.error('Already holding')
            return

        asyncio.ensure_future(self._holding_lock.acquire())

        for macro in self.child_macros:
            macro.press_key()

    def release_key(self):
        """The user released the key."""
        if self._holding_lock is not None:
            self._holding_lock.release()

        for macro in self.child_macros:
            macro.release_key()

    def hold(self, macro=None):
        """Loops the execution until key release."""
        async def hold_block(_):
            # wait until the key is released. Only then it will be
            # able to acquire the lock. Release it right after so that
            # it can be acquired by press_key again.
            try:
                await self._holding_lock.acquire()
                self._holding_lock.release()
            except RuntimeError as error:
                # The specific bug in question has been fixed already,
                # but lets keep this check here for the future. Not
                # catching errors here causes the macro to never be
                # released
                logger.error('Failed h(): %s', error)

        if macro is None:
            # no parameters: block until released
            self.tasks.append(hold_block)
            return

        if not isinstance(macro, _Macro):
            # if macro is a key name, hold down the key while the actual
            # keyboard key is held down
            symbol = str(macro)
            code = system_mapping.get(symbol)

            if code is None:
                raise KeyError(f'Unknown key "{symbol}"')

            self.capabilities[EV_KEY].add(code)
            self.tasks.append(lambda handler: handler(EV_KEY, code, 1))
            self.tasks.append(hold_block)
            self.tasks.append(lambda handler: handler(EV_KEY, code, 0))
            return

        if isinstance(macro, _Macro):
            # repeat the macro forever while the key is held down
            async def task(handler):
                while self.is_holding():
                    # run the child macro completely to avoid
                    # not-releasing any key
                    await macro.run(handler)

            self.tasks.append(task)
            self.child_macros.append(macro)

    def modify(self, modifier, macro):
        """Do stuff while a modifier is activated.

        Parameters
        ----------
        modifier : str
        macro : _Macro
        """
        if not isinstance(macro, _Macro):
            raise ValueError(
                'Expected the second param for m (modify) to be '
                f'a macro (like k(a)), but got {macro}'
            )

        modifier = str(modifier)
        code = system_mapping.get(modifier)

        if code is None:
            raise KeyError(f'Unknown modifier "{modifier}"')

        self.capabilities[EV_KEY].add(code)

        self.child_macros.append(macro)

        self.tasks.append(lambda handler: handler(EV_KEY, code, 1))
        self.tasks.append(self._keycode_pause)
        self.tasks.append(macro.run)
        self.tasks.append(self._keycode_pause)
        self.tasks.append(lambda handler: handler(EV_KEY, code, 0))
        self.tasks.append(self._keycode_pause)

    def repeat(self, repeats, macro):
        """Repeat actions.

        Parameters
        ----------
        repeats : int or _Macro
        macro : _Macro
        """
        if not isinstance(macro, _Macro):
            raise ValueError(
                'Expected the second param for r (repeat) to be '
                f'a macro (like k(a)), but got "{macro}"'
            )

        try:
            repeats = int(repeats)
        except ValueError as error:
            raise ValueError(
                'Expected the first param for r (repeat) to be '
                f'a number, but got "{repeats}"'
            ) from error

        async def repeat(handler):
            for _ in range(repeats):
                await macro.run(handler)

        self.tasks.append(repeat)
        self.child_macros.append(macro)

    async def _keycode_pause(self, _=None):
        """To add a pause between keystrokes."""
        await asyncio.sleep(self.keystroke_sleep_ms / 1000)

    def keycode(self, symbol):
        """Write the symbol."""
        symbol = str(symbol)
        code = system_mapping.get(symbol)

        if code is None:
            raise KeyError(f'Unknown key "{symbol}"')

        self.capabilities[EV_KEY].add(code)

        async def keycode(handler):
            handler(EV_KEY, code, 1)
            await self._keycode_pause()
            handler(EV_KEY, code, 0)
            await self._keycode_pause()

        self.tasks.append(keycode)

    def event(self, ev_type, code, value):
        """Write any event.

        Parameters
        ----------
        ev_type: str or int
            examples: 2, 'EV_KEY'
        code : int or int
            examples: 52, 'KEY_A'
        value : int
        """
        if isinstance(ev_type, str):
            ev_type = ecodes[ev_type.upper()]
        if isinstance(code, str):
            code = ecodes[code.upper()]

        if ev_type not in self.capabilities:
            self.capabilities[ev_type] = set()

        if ev_type == EV_REL:
            # add all capabilities that are required for the display server
            # to recognize the device as mouse
            self.capabilities[EV_REL].add(REL_X)
            self.capabilities[EV_REL].add(REL_Y)
            self.capabilities[EV_REL].add(REL_WHEEL)

        self.capabilities[ev_type].add(code)

        self.tasks.append(lambda handler: handler(ev_type, code, value))
        self.tasks.append(self._keycode_pause)

    def mouse(self, direction, speed):
        """Shortcut for h(e(...))."""
        code, value = {
            'up': (REL_Y, -1),
            'down': (REL_Y, 1),
            'left': (REL_X, -1),
            'right': (REL_X, 1),
        }[direction.lower()]
        value *= speed
        child_macro = _Macro(None, self.mapping)
        child_macro.event(EV_REL, code, value)
        self.hold(child_macro)

    def wheel(self, direction, speed):
        """Shortcut for h(e(...))."""
        code, value = {
            'up': (REL_WHEEL, 1),
            'down': (REL_WHEEL, -1),
            'left': (REL_HWHEEL, 1),
            'right': (REL_HWHEEL, -1),
        }[direction.lower()]
        child_macro = _Macro(None, self.mapping)
        child_macro.event(EV_REL, code, value)
        child_macro.wait(100 / speed)
        self.hold(child_macro)

    def wait(self, sleeptime):
        """Wait time in milliseconds."""
        try:
            sleeptime = int(sleeptime)
        except ValueError as error:
            raise ValueError(
                'Expected the param for w (wait) to be '
                f'a number, but got "{sleeptime}"'
            ) from error

       
        async def sleep(_):
            """ Wait in intervals of 10ms so the wait can be ended early if the key is released """
            for i in range(int(sleeptime/10)):
                await asyncio.sleep(0.01)
                if (self.is_holding() == False):
                    break
                

        self.tasks.append(sleep)

    def set(self, variable, value):
        """Set a variable to a certain value."""
        async def set(_):
            logger.debug('"%s" set to "%s"', variable, value)
            macro_variables[variable] = value

        self.tasks.append(set)

    def ifeq(self, variable, value, then, otherwise=None):
        """Perform an equality check.

        Parameters
        ----------
        variable : string
        value : string | number
        then : any
        otherwise : any
        """
        if not isinstance(then, _Macro):
            raise ValueError(
                'Expected the third param for ifeq to be '
                f'a macro (like k(a)), but got "{then}"'
            )

        if otherwise and not isinstance(otherwise, _Macro):
            raise ValueError(
                'Expected the fourth param for ifeq to be '
                f'a macro (like k(a)), but got "{otherwise}"'
            )

        async def ifeq(handler):
            set_value = macro_variables.get(variable)
            logger.debug('"%s" is "%s"', variable, set_value)
            if set_value == value:
                await then.run(handler)
            elif otherwise is not None:
                await otherwise.run(handler)

        self.child_macros.append(then)
        if isinstance(otherwise, _Macro):
            self.child_macros.append(otherwise)

        self.tasks.append(ifeq)


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
        if char == ',' and brackets == 0:
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
    openings = macro.count('(')
    closings = macro.count(')')
    if openings != closings:
        raise Exception(
            f'You entered {openings} opening and {closings} '
            'closing brackets'
        )

    brackets = 0
    position = 0
    for char in macro:
        position += 1
        if char == '(':
            brackets += 1
            continue

        if char == ')':
            brackets -= 1
            if brackets == 0:
                # the closing bracket of the call
                break

    return position


def _parse_recurse(macro, mapping, macro_instance=None, depth=0):
    """Handle a subset of the macro, e.g. one parameter or function call.

    Parameters
    ----------
    macro : string
        Just like parse
    mapping : Mapping
        The preset configuration
    macro_instance : _Macro or None
        A macro instance to add tasks to
    depth : int
    """
    # not using eval for security reasons
    assert isinstance(macro, str)
    assert isinstance(depth, int)

    if macro == '':
        return None

    if macro_instance is None:
        macro_instance = _Macro(macro, mapping)
    else:
        assert isinstance(macro_instance, _Macro)

    macro = macro.strip()
    space = '  ' * depth

    # is it another macro?
    call_match = re.match(r'^(\w+)\(', macro)
    call = call_match[1] if call_match else None
    if call is not None:
        # available functions in the macro and the minimum and maximum number
        # of their parameters
        functions = {
            'm': (macro_instance.modify, 2, 2),
            'r': (macro_instance.repeat, 2, 2),
            'k': (macro_instance.keycode, 1, 1),
            'e': (macro_instance.event, 3, 3),
            'w': (macro_instance.wait, 1, 1),
            'h': (macro_instance.hold, 0, 1),
            'mouse': (macro_instance.mouse, 2, 2),
            'wheel': (macro_instance.wheel, 2, 2),
            'ifeq': (macro_instance.ifeq, 3, 4),
            'set': (macro_instance.set, 2, 2),
        }

        function = functions.get(call)
        if function is None:
            raise Exception(f'Unknown function {call}')

        # get all the stuff inbetween
        position = _count_brackets(macro)

        inner = macro[macro.index('(') + 1:position - 1]

        # split "3, k(a).w(10)" into parameters
        string_params = _extract_params(inner)
        logger.spam('%scalls %s with %s', space, call, string_params)
        # evaluate the params
        params = [
            _parse_recurse(param.strip(), mapping, None, depth + 1)
            for param in string_params
        ]

        logger.spam('%sadd call to %s with %s', space, call, params)

        if len(params) < function[1] or len(params) > function[2]:
            if function[1] != function[2]:
                msg = (
                    f'{call} takes between {function[1]} and {function[2]}, '
                    f'not {len(params)} parameters'
                )
            else:
                msg = (
                    f'{call} takes {function[1]}, '
                    f'not {len(params)} parameters'
                )

            raise ValueError(msg)

        function[0](*params)

        # is after this another call? Chain it to the macro_instance
        if len(macro) > position and macro[position] == '.':
            chain = macro[position + 1:]
            logger.spam('%sfollowed by %s', space, chain)
            _parse_recurse(chain, mapping, macro_instance, depth)

        return macro_instance

    # probably a parameter for an outer function
    try:
        # if possible, parse as int
        macro = int(macro)
    except ValueError:
        # use as string instead
        pass

    logger.spam('%s%s %s', space, type(macro), macro)
    return macro


def handle_plus_syntax(macro):
    """transform a + b + c to m(a, m(b, m(c, h())))"""
    if '+' not in macro:
        return macro

    if '(' in macro or ')' in macro:
        logger.error('Mixing "+" and macros is unsupported: "%s"', macro)
        return macro

    chunks = [chunk.strip() for chunk in macro.split('+')]
    output = ''
    depth = 0
    for chunk in chunks:
        if chunk == '':
            # invalid syntax
            logger.error('Invalid syntax for "%s"', macro)
            return macro

        depth += 1
        output += f'm({chunk},'

    output += 'h()'
    output += depth * ')'

    logger.debug('Transformed "%s" to "%s"', macro, output)
    return output


def parse(macro, mapping, return_errors=False):
    """parse and generate a _Macro that can be run as often as you want.

    If it could not be parsed, possibly due to syntax errors, will log the
    error and return None.

    Parameters
    ----------
    macro : string
        "r(3, k(a).w(10))"
        "r(2, k(a).k(-)).k(b)"
        "w(1000).m(Shift_L, r(2, k(a))).w(10, 20).k(b)"
    mapping : Mapping
        The preset object, needed for some config stuff
    return_errors : bool
        If True, returns errors as a string or None if parsing worked.
        If False, returns the parsed macro.
    """
    macro = handle_plus_syntax(macro)

    # whitespaces, tabs, newlines and such don't serve a purpose. make
    # the log output clearer and the parsing easier.
    macro = re.sub(r'\s', '', macro)

    if '"' in macro or "'" in macro:
        logger.info('Quotation marks in macros are not needed')
        macro = macro.replace('"', '').replace("'", '')

    if return_errors:
        logger.spam('checking the syntax of %s', macro)
    else:
        logger.spam('preparing macro %s for later execution', macro)

    try:
        macro_object = _parse_recurse(macro, mapping)
        return macro_object if not return_errors else None
    except Exception as error:
        logger.error('Failed to parse macro "%s": %s', macro, error.__repr__())
        # print the traceback in case this is a bug of key-mapper
        logger.debug(''.join(traceback.format_tb(error.__traceback__)).strip())
        return str(error) if return_errors else None
