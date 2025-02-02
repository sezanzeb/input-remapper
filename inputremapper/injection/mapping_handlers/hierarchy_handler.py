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

from typing import List, Dict

import evdev
from evdev.ecodes import EV_ABS, EV_REL

from inputremapper.configs.input_config import InputCombination, InputConfig
from inputremapper.injection.global_uinputs import GlobalUInputs
from inputremapper.injection.mapping_handlers.mapping_handler import (
    MappingHandler,
    InputEventHandler,
    HandlerEnums,
)
from inputremapper.input_event import InputEvent


class HierarchyHandler(MappingHandler):
    """Handler consisting of an ordered list of MappingHandler

    only the first handler which successfully handles the event will execute it,
    all other handlers will be notified, but suppressed
    """

    _input_config: InputConfig

    def __init__(
        self,
        handlers: List[MappingHandler],
        input_config: InputConfig,
        global_uinputs: GlobalUInputs,
    ) -> None:
        self.handlers = handlers
        self._input_config = input_config
        combination = InputCombination([input_config])
        # use the mapping from the first child TODO: find a better solution
        mapping = handlers[0].mapping
        super().__init__(combination, mapping, global_uinputs)

    def __str__(self):
        return f"HierarchyHandler for {self._input_config}"

    def __repr__(self):
        return f"<{str(self)} at {hex(id(self))}>"

    @property
    def child(self):  # used for logging
        return self.handlers

    def notify(
        self,
        event: InputEvent,
        source: evdev.InputDevice = None,
        suppress: bool = False,
    ) -> bool:
        if event.input_match_hash != self._input_config.input_match_hash:
            return False

        handled = False
        for handler in self.handlers:
            if handled:
                # We want to be able to map EV_REL to EV_ABS, and while moving the
                # gamepad, still trigger keys using EV_REL and an analog_threshold.
                # In this case, we have two combinations activated at the same time.
                handler.notify(
                    event,
                    source,
                    suppress=not handler.mapping.input_combination.defines_analog_input,
                )
                continue

            handled = handler.notify(event, source)

        return handled

    def reset(self) -> None:
        for sub_handler in self.handlers:
            sub_handler.reset()

    def wrap_with(self) -> Dict[InputCombination, HandlerEnums]:
        if (
            self._input_config.type == EV_ABS
            and not self._input_config.defines_analog_input
        ):
            return {InputCombination([self._input_config]): HandlerEnums.abs2btn}
        if (
            self._input_config.type == EV_REL
            and not self._input_config.defines_analog_input
        ):
            return {InputCombination([self._input_config]): HandlerEnums.rel2btn}
        return {}

    def set_sub_handler(self, handler: InputEventHandler) -> None:
        assert False
