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
import copy
import re

from evdev.ecodes import ecodes, EV_KEY, EV_REL, REL_X, REL_Y, REL_WHEEL, REL_HWHEEL

from keymapper.logger import logger
from keymapper.system_mapping import system_mapping
from keymapper.ipc.shared_dict import SharedDict
from keymapper.utils import PRESS, PRESS_NEGATIVE


macro_variables = SharedDict()


def _type_check(value, allowed_types, display_name=None, position=None):
    """Validate a parameter used in a macro.

    If the value starts with $, it will be returned and should be resolved
    during runtime with _resolve.
    """
    if isinstance(value, str) and value.startswith("$"):
        # it is a variable and will be read at runtime
        return value

    for allowed_type in allowed_types:
        if allowed_type is None:
            if value is None:
                return value

            continue

        # try to parse "1" as 1 if possible
        try:
            return allowed_type(value)
        except (TypeError, ValueError):
            pass

        if isinstance(value, allowed_type):
            return value

    if display_name is not None and position is not None:
        raise TypeError(
            f"Expected parameter {position} for {display_name} to be "
            f"one of {allowed_types}, but got {value}"
        )

    raise TypeError(f"Expected parameter to be one of {allowed_types}, but got {value}")


def _type_check_keyname(name):
    """Same as _type_check, but checks if the key-name is valid."""
    if isinstance(name, str) and name.startswith("$"):
        # it is a variable and will be read at runtime
        return name

    symbol = str(name)
    code = system_mapping.get(symbol)

    if code is None:
        raise KeyError(f'Unknown key "{symbol}"')

    return code


def _type_check_variablename(name):
    """Check if this is a legit variable name.

    Because they could clash with language features. If the macro is able to be
    parsed at all due to a problematic choice of a variable name.

    Allowed examples: "foo", "Foo1234_", "_foo_1234"
    Not allowed: "1_foo", "foo=blub", "$foo", "foo,1234", "foo()"
    """
    if not isinstance(name, str) or not re.match(r"^[A-Za-z_][A-Za-z_0-9]*$", name):
        raise SyntaxError(f'"{name}" is not a legit variable name')


def _resolve(argument, allowed_types=None):
    """If the argument starts with a $, then figure out its value.

    Use this just-in-time when you need the actual value of the variable
    during runtime.
    """
    if isinstance(argument, str) and argument.startswith("$"):
        variable_name = argument.split("$", 1)[1]
        value = macro_variables.get(variable_name)
        logger.debug('"%s" is "%s"', argument, value)
        if allowed_types:
            return _type_check(value, allowed_types)
        else:
            return value

    return argument


class Macro:
    """Supports chaining and preparing actions.

    Calling functions like keycode on Macro doesn't inject any events yet,
    it means that once .run is used it will be executed along with all other
    queued tasks.

    Those functions need to construct an asyncio coroutine and append it to
    self.tasks. This makes parameter checking during compile time possible, as long
    as they are not variables that are resolved durig runtime. Coroutines receive a
    handler as argument, which is a function that can be used to inject input events
    into the system.

    1. A few parameters of any time are thrown into a macro function like `repeat`
    2. `Macro.repeat` will verify the parameter types if possible using `_type_check`
       (it can't for $variables). This helps debugging macros before the injection
       starts, but is not mandatory to make things work.
    3. `Macro.repeat`
       - adds a task to self.tasks. This task resolves any variables with `_resolve`
         and does what the macro is supposed to do once `macro.run` is called.
       - also adds the child macro to self.child_macros.
       - adds the used keys to the capabilities
    4. `Macro.run` will run all tasks in self.tasks
    """

    def __init__(self, code, context):
        """Create a macro instance that can be populated with tasks.

        Parameters
        ----------
        code : string or None
            The original parsed code, for logging purposes.
        context : Context
        """
        self.code = code
        self.context = context

        # List of coroutines that will be called sequentially.
        # This is the compiled code
        self.tasks = []

        # can be used to wait for the release of the event
        self._holding_event = asyncio.Event()
        self._holding_event.set()  # released by default

        self.running = False

        # all required capabilities, without those of child macros
        self.capabilities = {
            EV_KEY: set(),
            EV_REL: set(),
        }

        self.child_macros = []

        self.keystroke_sleep_ms = None

        self._new_event_arrived = asyncio.Event()
        self._newest_event = None
        self._newest_action = None

    def notify(self, event, action):
        """Tell the macro about the newest event."""
        for macro in self.child_macros:
            macro.notify(event, action)

        self._newest_event = event
        self._newest_action = action
        self._new_event_arrived.set()

    async def wait_for_event(self, filter=None):
        """Wait until a specific event arrives.

        The parameters can be used to provide a filter. It will block
        until an event arrives that matches them.

        Parameters
        ----------
        filter : function
            Receives the event. Stop waiting if it returns true.
        """
        while True:
            await self._new_event_arrived.wait()
            self._new_event_arrived.clear()

            if filter is not None:
                if not filter(self._newest_event, self._newest_action):
                    continue

            break

    def is_holding(self):
        """Check if the macro is waiting for a key to be released."""
        return not self._holding_event.is_set()

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

        # newly arriving events are only interesting if they arrive after the
        # macro started
        self._new_event_arrived.clear()

        self.keystroke_sleep_ms = self.context.mapping.get("macros.keystroke_sleep_ms")

        self.running = True
        for task in self.tasks:
            try:
                coroutine = task(handler)
                if asyncio.iscoroutine(coroutine):
                    await coroutine
            except Exception as e:
                logger.error(f'Macro "%s" failed: %s', self.code, e)
                break

        # done
        self.running = False

    def press_key(self):
        """The user pressed the key down."""
        if self.is_holding():
            logger.error("Already holding")
            return

        self._holding_event.clear()

        for macro in self.child_macros:
            macro.press_key()

    def release_key(self):
        """The user released the key."""
        self._holding_event.set()

        for macro in self.child_macros:
            macro.release_key()

    async def _keycode_pause(self, _=None):
        """To add a pause between keystrokes."""
        await asyncio.sleep(self.keystroke_sleep_ms / 1000)

    def add_mouse_capabilities(self):
        """Add all capabilities that are required to recognize the device as mouse."""
        self.capabilities[EV_REL].add(REL_X)
        self.capabilities[EV_REL].add(REL_Y)
        self.capabilities[EV_REL].add(REL_WHEEL)
        self.capabilities[EV_REL].add(REL_HWHEEL)

    def __repr__(self):
        return f'<Macro "{self.code}">'

    """Functions that prepare the macro"""

    def add_hold(self, macro=None):
        """Loops the execution until key release."""
        _type_check(macro, [Macro, str, None], "h (hold)", 1)

        if macro is None:
            self.tasks.append(lambda _: self._holding_event.wait())
            return

        if not isinstance(macro, Macro):
            # if macro is a key name, hold down the key while the
            # keyboard key is physically held down
            code = _type_check_keyname(macro)

            async def task(handler):
                resolved_code = _resolve(code, [int])
                self.capabilities[EV_KEY].add(resolved_code)
                handler(EV_KEY, resolved_code, 1)
                await self._holding_event.wait()
                handler(EV_KEY, resolved_code, 0)

            self.capabilities[EV_KEY].add(code)
            self.tasks.append(task)

        if isinstance(macro, Macro):
            # repeat the macro forever while the key is held down
            async def task(handler):
                while self.is_holding():
                    # run the child macro completely to avoid
                    # not-releasing any key
                    await macro.run(handler)

            self.tasks.append(task)
            self.child_macros.append(macro)

    def add_modify(self, modifier, macro):
        """Do stuff while a modifier is activated.

        Parameters
        ----------
        modifier : str
        macro : Macro
        """
        _type_check(macro, [Macro], "m (modify)", 2)

        modifier = str(modifier)
        code = system_mapping.get(modifier)

        if code is None:
            raise KeyError(f'Unknown modifier "{modifier}"')

        self.capabilities[EV_KEY].add(code)

        self.child_macros.append(macro)

        async def task(handler):
            resolved_code = _resolve(code, [int])
            self.capabilities[EV_KEY].add(resolved_code)
            await self._keycode_pause()
            handler(EV_KEY, resolved_code, 1)
            await self._keycode_pause()
            await macro.run(handler)
            await self._keycode_pause()
            handler(EV_KEY, resolved_code, 0)
            await self._keycode_pause()

        self.tasks.append(task)

    def add_repeat(self, repeats, macro):
        """Repeat actions.

        Parameters
        ----------
        repeats : int or Macro
        macro : Macro
        """
        repeats = _type_check(repeats, [int], "r (repeat)", 1)
        _type_check(macro, [Macro], "r (repeat)", 2)

        async def task(handler):
            for _ in range(_resolve(repeats, [int])):
                await macro.run(handler)

        self.tasks.append(task)
        self.child_macros.append(macro)

    def add_key(self, symbol):
        """Write the symbol."""
        _type_check_keyname(symbol)

        symbol = str(symbol)
        code = system_mapping.get(symbol)
        self.capabilities[EV_KEY].add(code)

        async def task(handler):
            handler(EV_KEY, code, 1)
            await self._keycode_pause()
            handler(EV_KEY, code, 0)
            await self._keycode_pause()

        self.tasks.append(task)

    def add_event(self, _type, code, value):
        """Write any event.

        Parameters
        ----------
        _type: str or int
            examples: 2, 'EV_KEY'
        code : int or int
            examples: 52, 'KEY_A'
        value : int
        """
        if isinstance(_type, str):
            _type = ecodes[_type.upper()]
        if isinstance(code, str):
            code = ecodes[code.upper()]

        if _type not in self.capabilities:
            self.capabilities[_type] = set()

        if _type == EV_REL:
            # add all capabilities that are required for the display server
            # to recognize the device as mouse
            self.capabilities[EV_REL].add(REL_X)
            self.capabilities[EV_REL].add(REL_Y)
            self.capabilities[EV_REL].add(REL_WHEEL)

        self.capabilities[_type].add(code)

        self.tasks.append(lambda handler: handler(_type, code, value))
        self.tasks.append(self._keycode_pause)

    def add_mouse(self, direction, speed):
        """Move the mouse cursor."""
        _type_check(direction, [str], "mouse", 1)
        speed = _type_check(speed, [int], "mouse", 2)

        code, value = {
            "up": (REL_Y, -1),
            "down": (REL_Y, 1),
            "left": (REL_X, -1),
            "right": (REL_X, 1),
        }[direction.lower()]

        self.add_mouse_capabilities()

        async def task(handler):
            resolved_speed = value * _resolve(speed, [int])
            while self.is_holding():
                handler(EV_REL, code, resolved_speed)
                await self._keycode_pause()

        self.tasks.append(task)

    def add_wheel(self, direction, speed):
        """Move the scroll wheel."""
        _type_check(direction, [str], "wheel", 1)
        speed = _type_check(speed, [int], "wheel", 2)

        code, value = {
            "up": (REL_WHEEL, 1),
            "down": (REL_WHEEL, -1),
            "left": (REL_HWHEEL, 1),
            "right": (REL_HWHEEL, -1),
        }[direction.lower()]

        self.add_mouse_capabilities()

        async def task(handler):
            resolved_speed = _resolve(speed, [int])
            while self.is_holding():
                handler(EV_REL, code, value)
                # scrolling moves much faster than mouse, so this
                # waits between injections instead to make it slower
                await asyncio.sleep(100 / resolved_speed)

        self.tasks.append(task)

    def add_wait(self, time):
        """Wait time in milliseconds."""
        time = _type_check(time, [int, float], "wait", 1)

        async def task(_):
            await asyncio.sleep(_resolve(time, [int, float]) / 1000)

        self.tasks.append(task)

    def add_set(self, variable, value):
        """Set a variable to a certain value."""
        _type_check_variablename(variable)

        async def task(_):
            # can also copy with set(a, $b)
            resolved_value = _resolve(value)
            logger.debug('"%s" set to "%s"', variable, resolved_value)
            macro_variables[variable] = value

        self.tasks.append(task)

    def add_ifeq(self, variable, value, then=None, otherwise=None):
        """Old version of if_eq, kept for compatibility reasons.

        This can't support a comparison like ifeq("foo", $blub) with blub containing
        "foo" without breaking old functionality, because "foo" is treated as a
        variable name.
        """
        _type_check(then, [Macro, None], "ifeq", 3)
        _type_check(otherwise, [Macro, None], "ifeq", 4)

        async def task(handler):
            set_value = macro_variables.get(variable)
            logger.debug('"%s" is "%s"', variable, set_value)
            if set_value == value:
                if then is not None:
                    await then.run(handler)
            elif otherwise is not None:
                await otherwise.run(handler)

        if isinstance(then, Macro):
            self.child_macros.append(then)
        if isinstance(otherwise, Macro):
            self.child_macros.append(otherwise)

        self.tasks.append(task)

    def add_if_eq(self, value_1, value_2, then=None, _else=None):
        """Compare two values."""
        _type_check(then, [Macro, None], "if_eq", 3)
        _type_check(_else, [Macro, None], "if_eq", 4)

        async def task(handler):
            resolved_value_1 = _resolve(value_1)
            resolved_value_2 = _resolve(value_2)
            if resolved_value_1 == resolved_value_2:
                if then is not None:
                    await then.run(handler)
            elif _else is not None:
                await _else.run(handler)

        if isinstance(then, Macro):
            self.child_macros.append(then)
        if isinstance(_else, Macro):
            self.child_macros.append(_else)

        self.tasks.append(task)

    def add_if_tap(self, then=None, _else=None, timeout=300):
        """If a key was pressed quickly."""
        _type_check(then, [Macro, None], "if_tap", 1)
        _type_check(_else, [Macro, None], "if_tap", 2)
        timeout = _type_check(timeout, [int, float], "if_tap", 3)

        if isinstance(then, Macro):
            self.child_macros.append(then)
        if isinstance(_else, Macro):
            self.child_macros.append(_else)

        async def task(handler):
            coroutine = self._holding_event.wait()
            resolved_timeout = _resolve(timeout, [int, float]) / 1000
            try:
                await asyncio.wait_for(coroutine, resolved_timeout)
                if then:
                    await then.run(handler)
            except asyncio.TimeoutError:
                if _else:
                    await _else.run(handler)

        self.tasks.append(task)

    def add_if_single(self, then, otherwise, timeout=None):
        """If a key was pressed without combining it."""
        _type_check(then, [Macro, None], "if_single", 1)
        _type_check(otherwise, [Macro, None], "if_single", 2)

        if isinstance(then, Macro):
            self.child_macros.append(then)
        if isinstance(otherwise, Macro):
            self.child_macros.append(otherwise)

        async def task(handler):
            mappable_event_1 = (self._newest_event.type, self._newest_event.code)

            def event_filter(event, action):
                """Which event may wake if_tap up."""
                # release event of the actual key
                if (event.type, event.code) == mappable_event_1:
                    return True

                # press event of another key
                if action in (PRESS, PRESS_NEGATIVE):
                    return True

            coroutine = self.wait_for_event(event_filter)
            resolved_timeout = _resolve(timeout, allowed_types=[int, float, None])
            try:
                if resolved_timeout is not None:
                    await asyncio.wait_for(coroutine, resolved_timeout / 1000)
                else:
                    await coroutine

                mappable_event_2 = (self._newest_event.type, self._newest_event.code)
                combined = mappable_event_1 != mappable_event_2
                if not combined:
                    # no timeout and not combined
                    if then:
                        await then.run(handler)
                    return
            except asyncio.TimeoutError:
                pass

            if otherwise:
                await otherwise.run(handler)

        self.tasks.append(task)
