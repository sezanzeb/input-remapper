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
import evdev

from evdev.ecodes import EV_KEY, EV_ABS, EV_REL
from typing import List, Optional, Dict

from inputremapper.event_combination import EventCombination

from inputremapper.input_event import InputEvent
from inputremapper.injection.mapping_handlers.mapping_handler import (
    MappingHandler,
    InputEventHandler,
    HandlerEnums,
)


class HierarchyHandler(MappingHandler):
    """
    handler consisting of an ordered list of MappingHandler

    only the first handler which successfully handles the event will execute it,
    all other handlers will be notified, but suppressed
    """

    _input_event: InputEvent

    def __init__(self, handlers: List[MappingHandler], event: InputEvent) -> None:
        self.handlers = handlers
        self._input_event = event
        combination = EventCombination(event)
        # use the mapping from the first child TODO: find a better solution
        mapping = handlers[0].mapping
        super().__init__(combination, mapping)

    def __str__(self):
        return f"HierarchyHandler for {self._input_event} <{id(self)}>:"

    def __repr__(self):
        return self.__str__()

    @property
    def child(self):  # used for logging
        return self.handlers

    def notify(
        self,
        event: InputEvent,
        source: evdev.InputDevice = None,
        forward: evdev.UInput = None,
        supress: bool = False,
    ) -> bool:
        if event.type_and_code != self._input_event.type_and_code:
            return False

        success = False
        for handler in self.handlers:
            if not success:
                success = handler.notify(event, source, forward)
            else:
                handler.notify(event, source, forward, supress=True)
        return success

    def wrap_with(self) -> Dict[EventCombination, HandlerEnums]:
        if self._input_event.type == EV_ABS and self._input_event.value != 0:
            return {EventCombination(self._input_event): HandlerEnums.abs2btn}
        if self._input_event.type == EV_REL and self._input_event.value != 0:
            return {EventCombination(self._input_event): HandlerEnums.rel2btn}
        return {}

    def set_sub_handler(self, handler: InputEventHandler) -> None:
        assert False
