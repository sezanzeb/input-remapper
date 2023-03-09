# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2023 sezanzeb <proxima@sezanzeb.de>
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
"""Provides protocols for mapping handlers

*** The architecture behind mapping handlers ***

Handling an InputEvent is done in 3 steps:
 1. Input Event Handling
    A MappingHandler that does Input event handling receives Input Events directly
    from the EventReader.
    To do so it must implement the InputEventHandler protocol.
    An InputEventHandler may handle multiple events (InputEvent.type_and_code)

 2. Event Transformation
    The event gets transformed as described by the mapping.
    e.g.: combining multiple events to a single one
        transforming EV_ABS to EV_REL
        macros
        ...
    Multiple transformations may get chained

 3. Event Injection
    The transformed event gets injected to a global_uinput

MappingHandlers can implement one or more of these steps.

Overview of implemented handlers and the steps they implement:

Step 1:
 - HierarchyHandler

Step 1 and 2:
 - CombinationHandler
 - AbsToBtnHandler
 - RelToBtnHandler

Step 1, 2 and 3:
 - AbsToRelHandler
 - NullHandler

Step 2 and 3:
 - KeyHandler
 - MacroHandler
"""
from __future__ import annotations

import enum
from typing import Dict, Protocol, Set, Optional, List

import evdev

from inputremapper.configs.input_config import InputCombination, InputConfig
from inputremapper.configs.mapping import Mapping
from inputremapper.exceptions import MappingParsingError
from inputremapper.input_event import InputEvent
from inputremapper.logger import logger


class EventListener(Protocol):
    async def __call__(self, event: evdev.InputEvent) -> None:
        ...


class ContextProtocol(Protocol):
    """The parts from context needed for handlers."""

    listeners: Set[EventListener]

    def get_forward_uinput(self, origin_hash) -> evdev.UInput:
        pass


class NotifyCallback(Protocol):
    """Type signature of InputEventHandler.notify

    return True if the event was actually taken care of
    """

    def __call__(
        self,
        event: InputEvent,
        source: evdev.InputDevice,
        suppress: bool = False,
    ) -> bool:
        ...


class InputEventHandler(Protocol):
    """The protocol any handler, which can be part of an event pipeline, must follow."""

    def notify(
        self,
        event: InputEvent,
        source: evdev.InputDevice,
        suppress: bool = False,
    ) -> bool:
        ...

    def reset(self) -> None:
        """Reset the state of the handler e.g. release any buttons."""
        ...


class HandlerEnums(enum.Enum):
    # converting to btn
    abs2btn = enum.auto()
    rel2btn = enum.auto()

    macro = enum.auto()
    key = enum.auto()

    # converting to "analog"
    btn2rel = enum.auto()
    rel2rel = enum.auto()
    abs2rel = enum.auto()

    btn2abs = enum.auto()
    rel2abs = enum.auto()
    abs2abs = enum.auto()

    # special handlers
    combination = enum.auto()
    hierarchy = enum.auto()
    axisswitch = enum.auto()
    disable = enum.auto()


class MappingHandler:
    """The protocol an InputEventHandler must follow if it should be
    dynamically integrated in an event-pipeline by the mapping parser
    """

    mapping: Mapping
    # all input events this handler cares about
    # should always be a subset of mapping.input_combination
    input_configs: List[InputConfig]
    _sub_handler: Optional[InputEventHandler]

    # https://bugs.python.org/issue44807
    def __init__(
        self,
        combination: InputCombination,
        mapping: Mapping,
        **_,
    ) -> None:
        """Initialize the handler

        Parameters
        ----------
        combination
            the combination from sub_handler.wrap_with()
        mapping
        """
        self.mapping = mapping
        self.input_configs = list(combination)
        self._sub_handler = None

    def notify(
        self,
        event: InputEvent,
        source: evdev.InputDevice,
        suppress: bool = False,
    ) -> bool:
        """Notify this handler about an incoming event.

        Parameters
        ----------
        event
            The newest event that came from `source`, and that should be mapped to
            something else
        source
            Where `event` comes from
        """
        raise NotImplementedError

    def reset(self) -> None:
        """Reset the state of the handler e.g. release any buttons."""
        raise NotImplementedError

    def needs_wrapping(self) -> bool:
        """If this handler needs to be wrapped in another MappingHandler."""
        return len(self.wrap_with()) > 0

    def needs_ranking(self) -> bool:
        """If this handler needs ranking and wrapping with a HierarchyHandler."""
        return False

    def rank_by(self) -> Optional[InputCombination]:
        """The combination for which this handler needs ranking."""

    def wrap_with(self) -> Dict[InputCombination, HandlerEnums]:
        """A dict of InputCombination -> HandlerEnums.

        for each InputCombination this handler should be wrapped
        with the given MappingHandler.
        """
        return {}

    def set_sub_handler(self, handler: InputEventHandler) -> None:
        """Give this handler a sub_handler."""
        self._sub_handler = handler

    def occlude_input_event(self, input_config: InputConfig) -> None:
        """Remove the config from self.input_configs."""
        if not self.input_configs:
            logger.debug_mapping_handler(self)
            raise MappingParsingError(
                "Cannot remove a non existing config", mapping_handler=self
            )

        # should be called for each event a wrapping-handler
        # has in its input_configs InputCombination
        self.input_configs.remove(input_config)
