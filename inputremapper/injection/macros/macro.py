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
from typing import List, Callable, Tuple, Optional, TYPE_CHECKING

from inputremapper.ipc.shared_dict import SharedDict
from inputremapper.logging.logger import logger

if TYPE_CHECKING:
    from inputremapper.injection.macros.task import Task
    from inputremapper.injection.context import Context
    from inputremapper.configs.mapping import Mapping

Handler = Callable[[Tuple[int, int, int]], None]

macro_variables = SharedDict()


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

    TODO docstring wrong:
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
        mapping: Mapping = None,
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

        # List of coroutines that will be called sequentially.
        # This is the compiled code
        self.tasks: List[Task] = []

        self.running = False

        self.keystroke_sleep_ms = None

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
                coroutine = task.run(handler)
                if asyncio.iscoroutine(coroutine):
                    await coroutine
        except Exception:
            raise
        finally:
            # done
            self.running = False

    def press_trigger(self):
        """The user pressed the trigger key down."""
        for task in self.tasks:
            task.press_trigger()

    def release_trigger(self):
        """The user released the trigger key."""
        for task in self.tasks:
            task.release_trigger()

    async def _keycode_pause(self, _=None):
        """To add a pause between keystrokes.

        This was needed at some point because it appeared that injecting keys too
        fast will prevent them from working. It probably depends on the environment.
        """
        await asyncio.sleep(self.keystroke_sleep_ms / 1000)

    def __repr__(self):
        return f'<Macro "{self.code}" at {hex(id(self))}>'

    def add_task(self, task):
        self.tasks.append(task)
