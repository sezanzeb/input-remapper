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


"""Stores injection-process wide information."""
from typing import Awaitable, List, Dict, Tuple, Protocol, Set

import evdev

from inputremapper.configs.preset import Preset
from inputremapper.input_event import InputEvent
from inputremapper.injection.mapping_handlers.mapping_parser import parse_mappings
from inputremapper.injection.mapping_handlers.mapping_handler import (
    InputEventHandler,
    EventListener,
)


class NotifyCallback(Protocol):
    """type signature of MappingHandler.notify

    return True if the event was actually taken care of
    """

    def __call__(
        self,
        event: evdev.InputEvent,
        source: evdev.InputDevice = None,
        forward: evdev.UInput = None,
        supress: bool = False,
    ) -> bool:
        ...


class Context:
    """Stores injection-process wide information.

    In some ways this is a wrapper for the preset that derives some
    information that is specifically important to the injection.

    The information in the context does not change during the injection.

    One Context exists for each injection process, which is shared
    with all coroutines and used objects.

    Benefits of the context:
    - less redundant passing around of parameters
    - easier to add new process wide information without having to adjust
      all function calls in unittests
    - makes the injection class shorter and more specific to a certain task,
      which is actually spinning up the injection.

    Members
    -------
    preset : Preset
        The preset that is the source of key_to_code and macros,
        only used to query config values.
    """

    preset: Preset
    listeners: Set[EventListener]
    callbacks: Dict[Tuple[int, int], List[NotifyCallback]]
    _handlers: Dict[InputEvent, List[InputEventHandler]]

    def __init__(self, preset: Preset):
        self.preset = preset
        self.listeners = set()
        self.callbacks = {}
        self._handlers = parse_mappings(preset, self)

        self.create_callbacks()

    def create_callbacks(self) -> None:
        """add the notify method from all _handlers to self.callbacks"""
        for event, handler_list in self._handlers.items():
            if event.type_and_code not in self.callbacks.keys():
                self.callbacks[event.type_and_code] = []
            for handler in handler_list:
                self.callbacks[event.type_and_code].append(handler.notify)

