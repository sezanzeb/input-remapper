#!/usr/bin/python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2022 sezanzeb <proxima@sezanzeb.de>
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

from typing import Dict, Optional

from inputremapper.configs.mapping import Mapping
from inputremapper.event_combination import EventCombination
from inputremapper.logger import logger
from inputremapper.input_event import InputEvent
from inputremapper.injection.global_uinputs import global_uinputs
from inputremapper.injection.macros.parse import parse
from inputremapper.injection.macros.macro import Macro
from inputremapper.injection.mapping_handlers.mapping_handler import ContextProtocol, MappingHandler, HandlerEnums


class MacroHandler(MappingHandler):
    """runs the target macro if notified"""

    # TODO: replace this by the macro itself
    _macro: Macro
    _active: bool

    def __init__(
            self,
            combination: EventCombination,
            mapping: Mapping,
            context: ContextProtocol = None,
    ):
        super().__init__(combination, mapping)
        self._active = False
        self._macro = parse(self.mapping.output_symbol, context, mapping)

    def __str__(self):
        return f"MacroHandler <{id(self)}>:"

    def __repr__(self):
        return self.__str__()

    @property
    def child(self):  # used for logging
        return f"maps to {self._macro} on {self.mapping.target_uinput}"

    def notify(self, event: InputEvent, *_, **__) -> bool:

        if event.value == 1:
            self._active = True
            self._macro.press_trigger()
            if self._macro.running:
                return True

            def f(ev_type, code, value):
                """Handler for macros."""
                logger.debug_key(
                    (ev_type, code, value), "sending from macro to %s", self.mapping.target_uinput
                )
                global_uinputs.write((ev_type, code, value), self.mapping.target_uinput)

            asyncio.ensure_future(self._macro.run(f))
            return True
        else:
            self._active = False
            if self._macro.is_holding():
                self._macro.release_trigger()

            return True

    def needs_wrapping(self) -> bool:
        return True

    def wrap_with(self) -> Dict[EventCombination, HandlerEnums]:
        return {self.input_events: HandlerEnums.combination}
