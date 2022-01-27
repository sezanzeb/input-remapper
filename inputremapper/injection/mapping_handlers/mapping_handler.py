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
"""provides protocols for mapping handlers


*** The architecture behind mapping handlers ***

Handling an InputEvent is done in 3 steps:
 1. Input Event Handling
    A MappingHandler that does Input event handling receives Input Events directly from the EventReader.
    To do so it must implement the InputEventHandler protocol.
    A InputEventHandler may handle multiple events (InputEvent.type_and_code)

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

Step 2 and 3:
 - KeyHandler
 - MacroHandler

"""

import evdev
from typing import Dict, Protocol, Set
from inputremapper.configs.preset import Preset
from inputremapper.input_event import InputEvent


class EventListener(Protocol):
    async def __call__(self, event: evdev.InputEvent) -> None:
        ...


class ContextProtocol(Protocol):
    """the parts from context needed for macros"""

    preset: Preset
    listeners: Set[EventListener]


class InputEventHandler(Protocol):
    """the protocol a mapping handler must follow"""

    async def notify(
        self,
        event: InputEvent,
        source: evdev.InputDevice = None,
        forward: evdev.UInput = None,
        supress: bool = False,
    ) -> bool:
        ...


class MappingHandler(InputEventHandler, Protocol):
    """"""
    def __init__(self, config: Dict[str, int], context: ContextProtocol):
        ...
