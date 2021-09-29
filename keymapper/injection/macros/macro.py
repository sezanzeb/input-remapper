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

from evdev.ecodes import ecodes, EV_KEY, EV_REL, REL_X, REL_Y, REL_WHEEL, REL_HWHEEL

from keymapper.logger import logger
from keymapper.system_mapping import system_mapping
from keymapper.ipc.shared_dict import SharedDict
from keymapper.utils import PRESS, PRESS_NEGATIVE


macro_variables = SharedDict()


def type_check(display_name, value, allowed_types, position):
    """Validate a parameter used in a macro."""
    for allowed_type in allowed_types:
        if allowed_type is None:
            if value is None:
                return value
            else:
                continue

        # try to parse "1" as 1 if possible
        try:
            return allowed_type(value)
        except (TypeError, ValueError):
            pass

        if isinstance(value, allowed_type):
            return value

    raise TypeError(
        f"Expected parameter {position} for {display_name} to be "
        f"one of {allowed_types}, but got {value}"
    )


class Macro:
    """Supports chaining and preparing actions.

    Calling functions like keycode on Macro doesn't inject any events yet,
    it means that once .run is used it will be executed along with all other
    queued tasks.

    Those functions need to construct an asyncio coroutine and append it to
    self.tasks. This makes parameter checking during compile time possible.
    Coroutines receive a handler as argument, which is a function that can be
    used to inject input events into the system.
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
            # one could call tasks the compiled macros. it's lambda functions
            # that receive the handler as an argument, so that they know
            # where to send the event to.
            coroutine = task(handler)
            if asyncio.iscoroutine(coroutine):
                await coroutine

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

    def hold(self, macro=None):
        """Loops the execution until key release."""
        if macro is None:
            self.tasks.append(lambda _: self._holding_event.wait())
            return

        if not isinstance(macro, Macro):
            # if macro is a key name, hold down the key while the
            # keyboard key is physically held down
            symbol = str(macro)
            code = system_mapping.get(symbol)

            if code is None:
                raise KeyError(f'Unknown key "{symbol}"')

            self.capabilities[EV_KEY].add(code)
            self.tasks.append(lambda handler: handler(EV_KEY, code, 1))
            self.tasks.append(lambda _: self._holding_event.wait())
            self.tasks.append(lambda handler: handler(EV_KEY, code, 0))
            return

        if isinstance(macro, Macro):
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
        macro : Macro
        """
        type_check("m (modify)", macro, [Macro], 2)

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
        repeats : int or Macro
        macro : Macro
        """
        repeats = type_check("r (repeat)", repeats, [int], 1)
        type_check("r (repeat)", macro, [Macro], 2)

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
        type_check("mouse", direction, [str], 1)
        speed = type_check("mouse", speed, [int], 2)

        code, value = {
            "up": (REL_Y, -1),
            "down": (REL_Y, 1),
            "left": (REL_X, -1),
            "right": (REL_X, 1),
        }[direction.lower()]
        value *= speed
        child_macro = Macro(None, self.context)
        child_macro.event(EV_REL, code, value)
        self.hold(child_macro)

    def wheel(self, direction, speed):
        """Shortcut for h(e(...))."""
        type_check("wheel", direction, [str], 1)
        speed = type_check("wheel", speed, [int], 2)

        code, value = {
            "up": (REL_WHEEL, 1),
            "down": (REL_WHEEL, -1),
            "left": (REL_HWHEEL, 1),
            "right": (REL_HWHEEL, -1),
        }[direction.lower()]
        child_macro = Macro(None, self.context)
        child_macro.event(EV_REL, code, value)
        child_macro.wait(100 / speed)
        self.hold(child_macro)

    def wait(self, sleeptime):
        """Wait time in milliseconds."""
        sleeptime = type_check("wait", sleeptime, [int, float], 1) / 1000

        async def sleep(_):
            await asyncio.sleep(sleeptime)

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
        then : Macro | None
        otherwise : Macro | None
        """
        type_check("ifeq", then, [Macro, None], 1)
        type_check("ifeq", otherwise, [Macro, None], 2)

        async def ifeq(handler):
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

        self.tasks.append(ifeq)

    def if_tap(self, then=None, otherwise=None, timeout=300):
        """If a key was pressed quickly.

        Parameters
        ----------
        then : Macro | None
        otherwise : Macro | None
        timeout : int
        """
        type_check("if_tap", then, [Macro, None], 1)
        type_check("if_tap", otherwise, [Macro, None], 2)
        timeout = type_check("if_tap", timeout, [int], 3)

        if isinstance(then, Macro):
            self.child_macros.append(then)
        if isinstance(otherwise, Macro):
            self.child_macros.append(otherwise)

        async def if_tap(handler):
            try:
                coroutine = self._holding_event.wait()
                await asyncio.wait_for(coroutine, timeout / 1000)
                if then:
                    await then.run(handler)
            except asyncio.TimeoutError:
                if otherwise:
                    await otherwise.run(handler)

        self.tasks.append(if_tap)

    def if_single(self, then, otherwise):
        """If a key was pressed without combining it.

        Parameters
        ----------
        then : Macro | None
        otherwise : Macro | None
        """
        type_check("if_single", then, [Macro, None], 1)
        type_check("if_single", otherwise, [Macro, None], 2)

        if isinstance(then, Macro):
            self.child_macros.append(then)
        if isinstance(otherwise, Macro):
            self.child_macros.append(otherwise)

        async def if_single(handler):
            mappable_event_1 = (self._newest_event.type, self._newest_event.code)

            def event_filter(event, action):
                """Which event may wake if_tap up."""
                # release event of the actual key
                if (event.type, event.code) == mappable_event_1:
                    return True

                # press event of another key
                if action in (PRESS, PRESS_NEGATIVE):
                    return True

            await self.wait_for_event(event_filter)

            mappable_event_2 = (self._newest_event.type, self._newest_event.code)

            combined = mappable_event_1 != mappable_event_2
            if then and not combined:
                await then.run(handler)
            elif otherwise:
                await otherwise.run(handler)

        self.tasks.append(if_single)
