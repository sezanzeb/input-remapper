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

import asyncio
import traceback
from typing import Dict, Callable, Tuple

from inputremapper.configs.input_config import InputCombination
from inputremapper.configs.mapping import Mapping
from inputremapper.injection.global_uinputs import GlobalUInputs
from inputremapper.injection.macros.macro import Macro
from inputremapper.injection.macros.parse import Parser
from inputremapper.injection.mapping_handlers.mapping_handler import (
    ContextProtocol,
    MappingHandler,
    HandlerEnums,
)
from inputremapper.input_event import InputEvent
from inputremapper.logging.logger import logger


class MacroHandler(MappingHandler):
    """Runs the target macro if notified."""

    # TODO: replace this by the macro itself
    _macro: Macro
    _active: bool

    def __init__(
        self,
        combination: InputCombination,
        mapping: Mapping,
        global_uinputs: GlobalUInputs,
        *,
        context: ContextProtocol,
    ):
        super().__init__(combination, mapping, global_uinputs)
        self._pressed_keys: Dict[Tuple[int, int], int] = {}
        self._active = False
        assert self.mapping.output_symbol is not None
        self._macro = Parser.parse(self.mapping.output_symbol, context, mapping)

    def __str__(self):
        return f"MacroHandler"

    def __repr__(self):
        return f"<{str(self)} at {hex(id(self))}>"

    @property
    def child(self):  # used for logging
        return f"maps to {self._macro} on {self.mapping.target_uinput}"

    async def run_macro(self, handler: Callable):
        """Run the macro with the provided function."""
        try:
            await self._macro.run(handler)
        except Exception as exception:
            logger.error('Macro "%s" failed with %s', self._macro.code, type(exception))
            traceback.print_exc()

    def notify(self, event: InputEvent, *_, **__) -> bool:
        if event.value == 1:
            self._active = True
            self._macro.press_trigger()
            if self._macro.running:
                return True

            def handler(type_, code, value) -> None:
                """Handler for macros."""
                self._remember_pressed_keys((type_, code, value))

                self.global_uinputs.write(
                    (type_, code, value),
                    self.mapping.target_uinput,
                )

            asyncio.ensure_future(self.run_macro(handler))
            return True
        else:
            self._active = False
            self._macro.release_trigger()

            return True

    def reset(self) -> None:
        self._active = False

        # To avoid a key hanging forever. Can be pretty annoying, especially if it is
        # a modifier that makes you unable to interact with your system.
        for (type, code), value in self._pressed_keys.items():
            if value == 1:
                logger.debug("Releasing key %s", (type, code, value))
                self.global_uinputs.write(
                    (type, code, 0),
                    self.mapping.target_uinput,
                )

    def needs_wrapping(self) -> bool:
        return True

    def wrap_with(self) -> Dict[InputCombination, HandlerEnums]:
        return {InputCombination(self.input_configs): HandlerEnums.combination}

    def _remember_pressed_keys(self, event: Tuple[int, int, int]) -> None:
        type, code, value = event
        self._pressed_keys[(type, code)] = value
