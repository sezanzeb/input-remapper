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

"""Executes more complex patterns of keystrokes."""

from __future__ import annotations

import asyncio
from typing import List, Callable, Optional, TYPE_CHECKING

from inputremapper.ipc.shared_dict import SharedDict
from inputremapper.logging.logger import logger

if TYPE_CHECKING:
    from inputremapper.injection.macros.task import Task
    from inputremapper.injection.context import Context
    from inputremapper.configs.mapping import Mapping

InjectEventCallback = Callable[[int, int, int], None]

macro_variables = SharedDict()


class Macro:
    """Chains tasks (like `modify` or `repeat`).

    Tasks may have child_macros. Running a Macro runs Tasks, which in turn may run
    their child_macros based on certain conditions (depending on the Task).
    """

    def __init__(
        self,
        code: Optional[str],
        context: Optional[Context] = None,
        mapping: Optional[Mapping] = None,
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

    async def run(self, callback: InjectEventCallback):
        """Run the macro.

        Parameters
        ----------
        callback
            Will receive int type, code and value for an event to write
        """
        if not callable(callback):
            raise ValueError("handler is not callable")

        if self.running:
            logger.error('Tried to run already running macro "%s"', self.code)
            return

        self.keystroke_sleep_ms = self.mapping.macro_key_sleep_ms

        self.running = True

        try:
            for task in self.tasks:
                coroutine = task.run(callback)
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
