#!/usr/bin/env python3
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

from __future__ import annotations

import asyncio
from itertools import chain
from typing import Callable, List, Dict, TYPE_CHECKING, Optional

from inputremapper.injection.macros.argument import (
    Argument,
    ArgumentConfig,
    ArgumentFlags,
)
from inputremapper.injection.macros.macro import Macro
from inputremapper.logging.logger import logger

if TYPE_CHECKING:
    from inputremapper.injection.macros.raw_value import RawValue
    from inputremapper.injection.context import Context
    from inputremapper.configs.mapping import Mapping


class Task:
    """Base Class for functions like `if_eq` or `key`

    A macro like `key(a).key(b)` will contain two instances of this class.
    """

    argument_configs: List[ArgumentConfig]
    arguments: Dict[str, Argument]
    mapping: Mapping

    # The context is None during frontend-parsing/validation I believe
    context: Optional[Context]

    child_macros: List[Macro]

    def __init__(
        self,
        positional_args: List[RawValue],
        keyword_args: Dict[str, RawValue],
        context: Optional[Context],
        mapping: Mapping,
    ) -> None:
        self.context = context
        self.mapping = mapping
        self.child_macros = []

        self.arguments = {
            argument_config.name: Argument(argument_config, mapping)
            for argument_config in self.argument_configs
        }

        self._setup_asyncio_events()

        for argument in self.arguments.values():
            self._initialize_argument(argument, keyword_args, positional_args)

        self._initialize_spread_arg(positional_args)

        for raw_value in chain(keyword_args.values(), positional_args):
            if isinstance(raw_value.value, Macro):
                self.child_macros.append(raw_value.value)

    async def run(self, handler: Callable) -> None:
        raise NotImplementedError()

    def get_argument(self, argument_name) -> Argument:
        return self.arguments[argument_name]

    def press_trigger(self) -> None:
        """The user pressed the trigger key down."""
        for macro in self.child_macros:
            macro.press_trigger()

        if self.is_holding():
            logger.error("Already holding")
            return

        self._trigger_release_event.clear()
        self._trigger_press_event.set()

    def release_trigger(self) -> None:
        """The user released the trigger key."""
        if not self.is_holding():
            return

        self._trigger_release_event.set()
        self._trigger_press_event.clear()

        for macro in self.child_macros:
            macro.release_trigger()

    def is_holding(self) -> bool:
        """Check if the macro is waiting for a key to be released."""
        return not self._trigger_release_event.is_set()

    async def keycode_pause(self, _=None) -> None:
        """To add a pause between keystrokes.

        This was needed at some point because it appeared that injecting keys too
        fast will prevent them from working. It probably depends on the environment.
        """
        await asyncio.sleep(self.mapping.macro_key_sleep_ms / 1000)

    def _initialize_spread_arg(
        self,
        positional_args: List[RawValue],
    ) -> None:
        """Put all positional arguments that aren't used into the spread argument."""
        spread_argument: Optional[Argument] = None
        for argument in self.arguments.values():
            if argument.position == ArgumentFlags.spread:
                spread_argument = argument
                break

        if spread_argument is None:
            return

        remaining_positional_args = [*positional_args]

        for argument in self.arguments.values():
            if argument.position != ArgumentFlags.spread and argument.position < len(
                remaining_positional_args
            ):
                del remaining_positional_args[argument.position]

        spread_argument.initialize_variables(remaining_positional_args)

    def _find_argument_by_position(self, position: int) -> Optional[Argument]:
        for argument in self.arguments.values():
            if argument.position == position:
                return argument

        return None

    def _setup_asyncio_events(self) -> None:
        # Can be used to wait for the press and release of the input event/key, that is
        # configured as the trigger of the macro, via asyncio.
        self._trigger_release_event = asyncio.Event()
        self._trigger_press_event = asyncio.Event()
        # released by default
        self._trigger_release_event.set()
        self._trigger_press_event.clear()

    def _initialize_argument(
        self,
        argument: Argument,
        keyword_args: Dict[str, RawValue],
        positional_args: List[RawValue],
    ) -> None:
        if argument.position == ArgumentFlags.spread:
            # Will get all the remaining positional arguments afterward.
            return

        for name, value in keyword_args.items():
            if argument.name == name:
                argument.initialize_variable(value)
                return

        if argument.position < len(positional_args):
            argument.initialize_variable(positional_args[argument.position])
            return

        if not argument.is_required():
            argument.initialize_default()
            return

        # This shouldn't be possible, the parser should have ensured things are valid
        # already.
        raise Exception(f"Could not initialize argument {argument.name}")
