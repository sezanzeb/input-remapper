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
"""provides protocols for mapping handlers"""
import evdev
from typing import Dict, Protocol, Set
from inputremapper.configs.preset import Preset


def copy_event(event: evdev.InputEvent) -> evdev.InputEvent:
    return evdev.InputEvent(
        sec=event.sec,
        usec=event.usec,
        type=event.type,
        code=event.code,
        value=event.value,
    )


class EventListener(Protocol):
    async def __call__(self, event: evdev.InputEvent) -> None:
        ...


class ContextProtocol(Protocol):
    """the parts from context needed for macros"""

    preset: Preset
    listeners: Set[EventListener]


class MappingHandler(Protocol):
    """the protocol a mapping handler must follow"""

    def __init__(self, config: Dict[str, int], context: ContextProtocol):
        ...

    async def notify(
        self,
        event: evdev.InputEvent,
        source: evdev.InputDevice = None,
        forward: evdev.UInput = None,
        supress: bool = False,
    ) -> bool:
        ...
