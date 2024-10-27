# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2024 sezanzeb <b8x45ygc9@mozmail.com>
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


"""Executes more complex patterns of keystrokes.

To keep it short on the UI, basic functions are one letter long.

The outermost macro (in the examples below the one created by 'r',
'r' and 'w') will be started, which triggers a chain reaction to execute
all of the configured stuff.

Examples
--------
r(3, k(a).w(10)): a <10ms> a <10ms> a
r(2, k(a).k(KEY_A)).k(b): a - a - b
w(1000).m(Shift_L, r(2, k(a))).w(10).k(b): <1s> A A <10ms> b
"""


from __future__ import annotations

import asyncio
import copy
import math
import re
import random
from typing import List, Callable, Awaitable, Tuple, Optional, Union, Any, TYPE_CHECKING

from evdev.ecodes import (
    ecodes,
    EV_KEY,
    EV_REL,
    REL_X,
    REL_Y,
    REL_WHEEL_HI_RES,
    REL_HWHEEL_HI_RES,
    REL_WHEEL,
    REL_HWHEEL,
    LED_NUML,
    LED_CAPSL,
)

from inputremapper.configs.keyboard_layout import keyboard_layout
from inputremapper.configs.validation_errors import (
    SymbolNotAvailableInTargetError,
    MacroParsingError,
)
from inputremapper.injection.global_uinputs import GlobalUInputs
from inputremapper.ipc.shared_dict import SharedDict
from inputremapper.logging.logger import logger

if TYPE_CHECKING:
    from inputremapper.injection.context import Context

Handler = Callable[[Tuple[int, int, int]], None]
MacroTask = Callable[[Handler], Awaitable]

macro_variables = SharedDict()


class Variable:
    """Can be used as function parameter in the various add_... functions.

    Parsed from strings like `$foo` in `repeat($foo, key(KEY_A))`

    Its value is unknown during construction and needs to be set using the `set` macro
    during runtime.
    """

    def __init__(self, name: str):
        self.name = name

    def resolve(self):
        """Get the variables value from memory."""
        return macro_variables.get(self.name)

    def __repr__(self):
        return f'<Variable "{self.name}" at {hex(id(self))}>'


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

    def __init__(
        self,
        code: Optional[str],
        context: Optional[Context] = None,
        mapping=None,
    ):
        """Create a macro instance that can be populated with tasks.

        Parameters
        ----------
        code
            The original parsed code, for logging purposes.
        context : Context
        mapping : UIMapping
        """
        self.code = code
        self.context = context
        self.mapping = mapping

        # TODO check if mapping is ever none by throwing an error

        # List of coroutines that will be called sequentially.
        # This is the compiled code
        self.tasks: List[MacroTask] = []

        # can be used to wait for the release of the event
        self._trigger_release_event = asyncio.Event()
        self._trigger_press_event = asyncio.Event()
        # released by default
        self._trigger_release_event.set()
        self._trigger_press_event.clear()

        self.running = False

        self.child_macros: List[Macro] = []
        self.keystroke_sleep_ms = None

    def is_holding(self):
        """Check if the macro is waiting for a key to be released."""
        return not self._trigger_release_event.is_set()

    def get_capabilities(self):
        """Get the merged capabilities of the macro and its children."""
        capabilities = copy.deepcopy(self.capabilities)

        for macro in self.child_macros:
            macro_capabilities = macro.get_capabilities()
            for type_ in macro_capabilities:
                if type_ not in capabilities:
                    capabilities[type_] = set()

                capabilities[type_].update(macro_capabilities[type_])

        return capabilities

    async def run(self, handler: Callable):
        """Run the macro.

        Parameters
        ----------
        handler
            Will receive int type, code and value for an event to write
        """
        if not callable(handler):
            raise ValueError("handler is not callable")

        if self.running:
            logger.error('Tried to run already running macro "%s"', self.code)
            return

        self.keystroke_sleep_ms = self.mapping.macro_key_sleep_ms

        self.running = True

        try:
            for task in self.tasks:
                coroutine = task(handler)
                if asyncio.iscoroutine(coroutine):
                    await coroutine
        except Exception:
            raise
        finally:
            # done
            self.running = False

    def press_trigger(self):
        """The user pressed the trigger key down."""
        if self.is_holding():
            logger.error("Already holding")
            return

        self._trigger_release_event.clear()
        self._trigger_press_event.set()

        for macro in self.child_macros:
            macro.press_trigger()

    def release_trigger(self):
        """The user released the trigger key."""
        self._trigger_release_event.set()
        self._trigger_press_event.clear()

        for macro in self.child_macros:
            macro.release_trigger()

    async def _keycode_pause(self, _=None):
        """To add a pause between keystrokes.

        This was needed at some point because it appeared that injecting keys too
        fast will prevent them from working. It probably depends on the environment.
        """
        await asyncio.sleep(self.keystroke_sleep_ms / 1000)

    def __repr__(self):
        return f'<Macro "{self.code}" at {hex(id(self))}>'

    """Functions that prepare the macro."""

    def add_key(self, symbol: str):
        """Write the symbol."""
        # This is done to figure out if the macro is broken at compile time, because
        # if KEY_A was unknown we can show this in the gui before the injection starts.
        self._type_check_symbol(symbol)

        async def task(handler: Callable):
            # if the code is $foo, figure out the correct code now.
            resolved_symbol = self._resolve(symbol, [str])
            code = self._type_check_symbol(resolved_symbol)

            resolved_code = self._resolve(code, [int])
            handler(EV_KEY, resolved_code, 1)
            await self._keycode_pause()
            handler(EV_KEY, resolved_code, 0)
            await self._keycode_pause()

        self.tasks.append(task)

    def add_key_down(self, symbol: str):
        """Press the symbol."""
        self._type_check_symbol(symbol)

        async def task(handler: Callable):
            resolved_symbol = self._resolve(symbol, [str])
            code = self._type_check_symbol(resolved_symbol)

            resolved_code = self._resolve(code, [int])
            handler(EV_KEY, resolved_code, 1)

        self.tasks.append(task)

    def add_key_up(self, symbol: str):
        """Release the symbol."""
        self._type_check_symbol(symbol)

        async def task(handler: Callable):
            resolved_symbol = self._resolve(symbol, [str])
            code = self._type_check_symbol(resolved_symbol)

            resolved_code = self._resolve(code, [int])
            handler(EV_KEY, resolved_code, 0)

        self.tasks.append(task)

    def add_hold(self, macro=None):
        """Loops the execution until key release."""
        self._type_check(macro, [Macro, str, None], "hold", 1)

        if macro is None:
            self.tasks.append(lambda _: self._trigger_release_event.wait())
            return

        if not isinstance(macro, Macro):
            # if macro is a key name, hold down the key while the
            # keyboard key is physically held down
            symbol = macro
            self._type_check_symbol(symbol)

            async def task(handler: Callable):
                resolved_symbol = self._resolve(symbol, [str])
                code = self._type_check_symbol(resolved_symbol)

                resolved_code = self._resolve(code, [int])
                handler(EV_KEY, resolved_code, 1)
                await self._trigger_release_event.wait()
                handler(EV_KEY, resolved_code, 0)

            self.tasks.append(task)

        if isinstance(macro, Macro):
            # repeat the macro forever while the key is held down
            async def task(handler: Callable):
                while self.is_holding():
                    # run the child macro completely to avoid
                    # not-releasing any key
                    await macro.run(handler)
                    # give some other code a chance to run
                    await asyncio.sleep(1 / 1000)

            self.tasks.append(task)
            self.child_macros.append(macro)

    def add_modify(self, modifier: str, macro: Macro):
        """Do stuff while a modifier is activated.

        Parameters
        ----------
        modifier
        macro
        """
        self._type_check(macro, [Macro], "modify", 2)
        self._type_check_symbol(modifier)

        self.child_macros.append(macro)

        async def task(handler: Callable):
            # TODO test var
            resolved_modifier = self._resolve(modifier, [str])
            code = self._type_check_symbol(resolved_modifier)

            handler(EV_KEY, code, 1)
            await self._keycode_pause()
            await macro.run(handler)
            handler(EV_KEY, code, 0)
            await self._keycode_pause()

        self.tasks.append(task)

    def add_hold_keys(self, *symbols):
        """Hold down multiple keys, equivalent to `a + b + c + ...`."""
        for symbol in symbols:
            self._type_check_symbol(symbol)

        async def task(handler: Callable):
            resolved_symbols = [self._resolve(symbol, [str]) for symbol in symbols]
            codes = [self._type_check_symbol(symbol) for symbol in resolved_symbols]

            for code in codes:
                handler(EV_KEY, code, 1)
                await self._keycode_pause()

            await self._trigger_release_event.wait()

            for code in codes[::-1]:
                handler(EV_KEY, code, 0)
                await self._keycode_pause()

        self.tasks.append(task)

    def add_repeat(self, repeats: Union[str, int], macro: Macro):
        """Repeat actions."""
        repeats = self._type_check(repeats, [int], "repeat", 1)
        self._type_check(macro, [Macro], "repeat", 2)

        async def task(handler: Callable):
            for _ in range(self._resolve(repeats, [int])):
                await macro.run(handler)

        self.tasks.append(task)
        self.child_macros.append(macro)

    def add_event(self, type_: Union[str, int], code: Union[str, int], value: int):
        """Write any event.

        Parameters
        ----------
        type_
            examples: 2, 'EV_KEY'
        code
            examples: 52, 'KEY_A'
        value
        """
        type_ = self._type_check(type_, [int, str], "event", 1)
        code = self._type_check(code, [int, str], "event", 2)
        value = self._type_check(value, [int, str], "event", 3)

        if isinstance(type_, str):
            type_ = ecodes[type_.upper()]
        if isinstance(code, str):
            code = ecodes[code.upper()]

        self.tasks.append(lambda handler: handler(type_, code, value))
        self.tasks.append(self._keycode_pause)

    def add_mouse(
        self,
        direction: str,
        speed: int,
        acceleration: Optional[float] = None,
    ):
        """Move the mouse cursor."""
        self._type_check(direction, [str], "mouse", 1)
        speed = self._type_check(speed, [int], "mouse", 2)
        acceleration = self._type_check(acceleration, [float, None], "mouse", 3)

        code, value = {
            "up": (REL_Y, -1),
            "down": (REL_Y, 1),
            "left": (REL_X, -1),
            "right": (REL_X, 1),
        }[direction.lower()]

        async def task(handler: Callable):
            resolved_speed = self._resolve(speed, [int])
            resolved_accel = self._resolve(acceleration, [float, None])

            if resolved_accel:
                current_speed = 0.0
                displacement_accumulator = 0.0
                displacement = 0
            else:
                displacement = resolved_speed

            while self.is_holding():
                # Cursors can only move by integers. To get smooth acceleration for
                # small acceleration values, the cursor needs to move by a pixel every
                # few iterations. This can be achieved by remembering the decimal
                # places that were cast away, and using them for the next iteration.
                if resolved_accel and current_speed < resolved_speed:
                    current_speed += resolved_accel
                    current_speed = min(current_speed, resolved_speed)
                    displacement_accumulator += current_speed
                    displacement = int(displacement_accumulator)
                    displacement_accumulator -= displacement

                handler(EV_REL, code, value * displacement)
                await asyncio.sleep(1 / self.mapping.rel_rate)

        self.tasks.append(task)

    def add_wheel(self, direction: str, speed: int):
        """Move the scroll wheel."""
        self._type_check(direction, [str], "wheel", 1)
        speed = self._type_check(speed, [int], "wheel", 2)

        code, value = {
            "up": ([REL_WHEEL, REL_WHEEL_HI_RES], [1 / 120, 1]),
            "down": ([REL_WHEEL, REL_WHEEL_HI_RES], [-1 / 120, -1]),
            "left": ([REL_HWHEEL, REL_HWHEEL_HI_RES], [1 / 120, 1]),
            "right": ([REL_HWHEEL, REL_HWHEEL_HI_RES], [-1 / 120, -1]),
        }[direction.lower()]

        async def task(handler: Callable):
            resolved_speed = self._resolve(speed, [int])
            remainder = [0.0, 0.0]
            while self.is_holding():
                for i in range(0, 2):
                    float_value = value[i] * resolved_speed + remainder[i]
                    remainder[i] = math.fmod(float_value, 1)
                    if abs(float_value) >= 1:
                        handler(EV_REL, code[i], int(float_value))
                await asyncio.sleep(1 / self.mapping.rel_rate)

        self.tasks.append(task)

    def add_wait(self, time: Union[str, float, int], max_time=None):
        """Wait time in milliseconds."""
        time = self._type_check(time, [float, int], "wait", 1)
        max_time = self._type_check(max_time, [float, int, None], "wait", 2)

        async def task(_):
            resolved_time = self._resolve(time, [float, int])
            resolved_max_time = self._resolve(max_time, [float, int])

            if resolved_max_time is not None and resolved_max_time > resolved_time:
                resolved_time = random.uniform(resolved_time, resolved_max_time)

            await asyncio.sleep(resolved_time / 1000)

        self.tasks.append(task)

    def add_set(self, variable: str, value):
        """Set a variable to a certain value."""
        self._type_check_variablename(variable)

        async def task(_):
            # can also copy with set(a, $b)
            resolved_value = self._resolve(value)
            logger.debug('"%s" set to "%s"', variable, resolved_value)
            macro_variables[variable] = value

        self.tasks.append(task)

    def add_add(self, variable: str, value: Union[int, float]):
        """Add a number to a variable."""
        self._type_check_variablename(variable)
        self._type_check(value, [int, float], "value", 1)

        async def task(_):
            current = macro_variables[variable]
            if current is None:
                logger.debug('"%s" initialized with 0', variable)
                macro_variables[variable] = 0
                current = 0

            resolved_value = self._resolve(value)
            if not isinstance(resolved_value, (int, float)):
                logger.error('Expected delta "%s" to be a number', resolved_value)
                return

            if not isinstance(current, (int, float)):
                logger.error(
                    'Expected variable "%s" to contain a number, but got "%s"',
                    variable,
                    current,
                )
                return

            logger.debug('"%s" += "%s"', variable, resolved_value)
            macro_variables[variable] += value

        self.tasks.append(task)

    def add_ifeq(self, variable, value, then=None, else_=None):
        """Old version of if_eq, kept for compatibility reasons.

        This can't support a comparison like ifeq("foo", $blub) with blub containing
        "foo" without breaking old functionality, because "foo" is treated as a
        variable name.
        """
        self._type_check(then, [Macro, None], "ifeq", 3)
        self._type_check(else_, [Macro, None], "ifeq", 4)

        async def task(handler: Callable):
            set_value = macro_variables.get(variable)
            logger.debug('"%s" is "%s"', variable, set_value)
            if set_value == value:
                if then is not None:
                    await then.run(handler)
            elif else_ is not None:
                await else_.run(handler)

        if isinstance(then, Macro):
            self.child_macros.append(then)
        if isinstance(else_, Macro):
            self.child_macros.append(else_)

        self.tasks.append(task)

    def add_if_eq(self, value_1, value_2, then=None, else_=None):
        """Compare two values."""
        self._type_check(then, [Macro, None], "if_eq", 3)
        self._type_check(else_, [Macro, None], "if_eq", 4)

        async def task(handler: Callable):
            resolved_value_1 = self._resolve(value_1)
            resolved_value_2 = self._resolve(value_2)
            if resolved_value_1 == resolved_value_2:
                if then is not None:
                    await then.run(handler)
            elif else_ is not None:
                await else_.run(handler)

        if isinstance(then, Macro):
            self.child_macros.append(then)
        if isinstance(else_, Macro):
            self.child_macros.append(else_)

        self.tasks.append(task)

    def _add_if_led(self, code: int, then: Optional[Macro], else_: Optional[Macro]):
        async def task(handler: Callable):
            # self.context is only None when the frontend is parsing the macro
            assert self.context is not None
            is_numlock_on = code in self.context.get_leds()

            if is_numlock_on:
                if then is not None:
                    await then.run(handler)
            elif else_ is not None:
                await else_.run(handler)

        if isinstance(then, Macro):
            self.child_macros.append(then)
        if isinstance(else_, Macro):
            self.child_macros.append(else_)

        self.tasks.append(task)

    def add_if_numlock(self, then=None, else_=None):
        self._type_check(then, [Macro, None], "if_numlock", 1)
        self._type_check(else_, [Macro, None], "if_numlock", 2)
        self._add_if_led(LED_NUML, then, else_)

    def add_if_capslock(self, then=None, else_=None):
        self._type_check(then, [Macro, None], "if_capslock", 1)
        self._type_check(else_, [Macro, None], "if_capslock", 2)
        self._add_if_led(LED_CAPSL, then, else_)

    def add_if_tap(self, then=None, else_=None, timeout=300):
        """If a key was pressed quickly.

        macro key pressed -> if_tap starts -> key released -> then

        macro key pressed -> released (does other stuff in the meantime)
        -> if_tap starts -> pressed -> released -> then
        """
        self._type_check(then, [Macro, None], "if_tap", 1)
        self._type_check(else_, [Macro, None], "if_tap", 2)
        timeout = self._type_check(timeout, [int, float], "if_tap", 3)

        if isinstance(then, Macro):
            self.child_macros.append(then)
        if isinstance(else_, Macro):
            self.child_macros.append(else_)

        async def wait():
            """Wait for a release, or if nothing pressed yet, a press and release."""
            if self.is_holding():
                await self._trigger_release_event.wait()
            else:
                await self._trigger_press_event.wait()
                await self._trigger_release_event.wait()

        async def task(handler: Callable):
            resolved_timeout = self._resolve(timeout, [int, float]) / 1000
            try:
                await asyncio.wait_for(wait(), resolved_timeout)
                if then:
                    await then.run(handler)
            except asyncio.TimeoutError:
                if else_:
                    await else_.run(handler)

        self.tasks.append(task)

    def add_if_single(self, then, else_, timeout=None):
        """If a key was pressed without combining it."""
        self._type_check(then, [Macro, None], "if_single", 1)
        self._type_check(else_, [Macro, None], "if_single", 2)

        if isinstance(then, Macro):
            self.child_macros.append(then)
        if isinstance(else_, Macro):
            self.child_macros.append(else_)

        async def task(handler: Callable):
            listener_done = asyncio.Event()

            async def listener(event):
                if event.type != EV_KEY:
                    # ignore anything that is not a key
                    return

                if event.value == 1:
                    # another key was pressed, trigger else
                    listener_done.set()
                    return

            self.context.listeners.add(listener)

            resolved_timeout = Macro._resolve(timeout, allowed_types=[int, float, None])
            await asyncio.wait(
                [
                    asyncio.Task(listener_done.wait()),
                    asyncio.Task(self._trigger_release_event.wait()),
                ],
                timeout=resolved_timeout / 1000 if resolved_timeout else None,
                return_when=asyncio.FIRST_COMPLETED,
            )

            self.context.listeners.remove(listener)

            if not listener_done.is_set() and self._trigger_release_event.is_set():
                if then:
                    await then.run(handler)  # was trigger release
            else:
                if else_:
                    await else_.run(handler)

        self.tasks.append(task)

    def _type_check_symbol(self, keyname: Union[str, Variable]) -> Union[Variable, int]:
        """Same as _type_check, but checks if the key-name is valid."""
        if isinstance(keyname, Variable):
            # it is a variable and will be read at runtime
            return keyname

        symbol = str(keyname)
        code = keyboard_layout.get(symbol)

        if code is None:
            raise MacroParsingError(msg=f'Unknown key "{symbol}"')

        if self.mapping is not None:
            target = self.mapping.target_uinput
            if target is not None and not GlobalUInputs.can_default_uinput_emit(
                target, EV_KEY, code
            ):
                raise SymbolNotAvailableInTargetError(symbol, target)

        return code

    @staticmethod
    def _type_check(value: Any, allowed_types, display_name=None, position=None) -> Any:
        """Validate a parameter used in a macro.

        If the value is a Variable, it will be returned and should be resolved
        during runtime with _resolve.
        """
        if isinstance(value, Variable):
            # it is a variable and will be read at runtime
            return value

        for allowed_type in allowed_types:
            if allowed_type is None:
                if value is None:
                    return value

                continue

            # try to parse "1" as 1 if possible
            if allowed_type != Macro:
                # the macro constructor with a single argument always succeeds,
                # but will definitely not result in the correct macro
                try:
                    return allowed_type(value)
                except (TypeError, ValueError):
                    pass

            if isinstance(value, allowed_type):
                return value

        if display_name is not None and position is not None:
            raise MacroParsingError(
                msg=f"Expected parameter {position} for {display_name} to be "
                f"one of {allowed_types}, but got {value}"
            )

        raise MacroParsingError(
            msg=f"Expected parameter to be one of {allowed_types}, but got {value}"
        )

    @staticmethod
    def _type_check_variablename(name: str):
        """Check if this is a legit variable name.

        Because they could clash with language features. If the macro is able to be
        parsed at all due to a problematic choice of a variable name.

        Allowed examples: "foo", "Foo1234_", "_foo_1234"
        Not allowed: "1_foo", "foo=blub", "$foo", "foo,1234", "foo()"
        """
        if not isinstance(name, str) or not re.match(r"^[A-Za-z_][A-Za-z_0-9]*$", name):
            raise MacroParsingError(msg=f'"{name}" is not a legit variable name')

    @staticmethod
    def _resolve(argument, allowed_types=None):
        """If the argument is a variable, figure out its value and cast it.

        Variables are prefixed with `$` in the syntax.

        Use this just-in-time when you need the actual value of the variable
        during runtime.
        """
        if isinstance(argument, Variable):
            value = argument.resolve()
            logger.debug('"%s" is "%s"', argument, value)
            if allowed_types:
                return Macro._type_check(value, allowed_types)
            else:
                return value

        return argument
