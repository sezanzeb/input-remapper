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


"""Consumer base class.

Can be notified of new events so that inheriting classes can map them and
inject new events based on them.
"""
import asyncio
import copy
from abc import abstractmethod, ABC
from typing import Dict, Tuple, Type, List, Optional

import evdev

from inputremapper import utils
from inputremapper.logger import logger
from inputremapper.system_mapping import system_mapping
from inputremapper.key import Key
from inputremapper.injection.global_uinputs import global_uinputs


class MappingHandler(ABC):
    """Can be notified of new events to inject them. Base class."""
    # hierarchic mapping handlers e.g. KeysToKeyHandler will get sorted to make sure
    # only one handler will receive the event. This allows mapping of combinations
    # to override other combinations.
    # Non-hierarchic handlers will always receive all events they care about
    hierarchic = False
    _target: Optional[str]
    _config: Optional[Dict[str, any]]
    _key: Optional[Key]

    def __init__(self, config: Dict[str, any] = None) -> None:
        if config:
            self._config = copy.deepcopy(config)
            self._target = self._config["target"]
            self._key = Key(self._config["key"])
        else:
            self._config = None
            self._target = None
            self._key = None

    @abstractmethod
    async def notify(self,
                     event: evdev.InputEvent,
                     source: evdev.InputDevice = None,
                     forward: evdev.UInput = None,
                     supress: bool = False) -> bool:

        """A new event is ready.

        return if the event was actually taken care of

        Overwrite this function if the consumer should do something each time
        a new event arrives. E.g. mapping a single button once clicked.
        """

    @abstractmethod
    async def run(self) -> None:
        """Start doing things.

        Overwrite this function if the consumer should do something
        continuously even if no new event arrives. e.g. continuously injecting
        mouse movement events.
        """

    def inject(self, event_tuple: Tuple) -> None:
        logger.debug("injecting form new mapping handler: %s", event_tuple)
        global_uinputs.write(event_tuple, self._target)


class KeysToKeyHandler(MappingHandler):

    _key_map: Dict[Tuple[int, int], bool]
    _active: bool  # keep track if the target key is pressed down
    maps_to: Tuple[int, int]
    hierarchic = True

    def __init__(self, config: Dict[str, any]) -> None:
        super().__init__(config)
        self._active = False
        self._key_map = {}
        for sub_key in self._key:  # prepare key_map
            self._key_map[sub_key[:2]] = False

        self.maps_to = (evdev.ecodes.EV_KEY, system_mapping.get(self._config["symbol"]))

    async def notify(self,
                     event: evdev.InputEvent,
                     source: evdev.InputDevice = None,
                     forward: evdev.UInput = None,
                     supress: bool = False) -> bool:

        map_key = (event.type, event.code)
        if map_key not in self._key_map.keys():
            return False  # we are not responsible for the event

        self._key_map[map_key] = event.value == 1
        if self.get_active() == self._active:
            return False  # nothing changed ignore this event

        self._active = self.get_active() and not utils.is_key_up(event.value)
        if supress:
            return False

        if self._active:
            value = 1
            if forward:
                self.forward_release(forward)
        else:
            value = 0

        logger.key_spam(self._key, "maps to (%s)", [(*self.maps_to, value), self._target])
        self.inject((*self.maps_to, value))
        return True

    async def run(self) -> None:  # no debouncer or anything (yet)
        pass

    def get_active(self) -> bool:
        return False not in self._key_map.values()

    def forward_release(self, forward: evdev.UInput) -> None:
        """forward a button release for all keys if this is a combination

        this might cause duplicate key-up events but those are ignored by evdev anyway
        """
        if len(self._key) == 1:
            return
        for key in self._key:
            forward.write(*key[:2], 0)
        forward.syn()


class HierarchyHandler(MappingHandler):
    """handler consisting of an ordered list of KeysToKeyHandler

    only the first handler which successfully handles a key_down event will execute the key_down.
    Handlers receive key up events in reversed order.
    """
    hierarchic = False

    def __init__(self, handlers: List[MappingHandler]) -> None:
        self.handlers = handlers
        super().__init__()

    async def run(self) -> None:
        pass

    async def notify(self,
                     event: evdev.InputEvent,
                     source: evdev.InputDevice = None,
                     forward: evdev.UInput = None,
                     supress: bool = False) -> bool:

        if event.value == 1:
            return await self.handle_key_down(event, forward)
        else:
            return await self.handle_key_up(event)

    async def handle_key_down(self,
                              event: evdev.InputEvent,
                              forward: evdev.UInput) -> bool:
        success = False
        for handler in self.handlers:
            if not success:
                success = await handler.notify(event, forward=forward)
            else:
                asyncio.ensure_future(handler.notify(event, supress=True))
        return success

    async def handle_key_up(self, event: evdev.InputEvent) -> bool:
        success = False
        for handler in self.handlers[::-1]:
            if not success:
                success = await handler.notify(event)
            else:
                asyncio.ensure_future(handler.notify(event))

        return success


mapping_handler_classes: Dict[str, Type[MappingHandler]] = {
    # all available mapping_handlers
    "keys_to_key": KeysToKeyHandler,
}


def create_handler(config: Dict[str, any]) -> MappingHandler:
    """return the MappingHandler"""
    return mapping_handler_classes[config['type']](config)
