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
from typing import Dict, Tuple, Type, List

import evdev

from inputremapper import utils
from inputremapper.logger import logger
from inputremapper.system_mapping import system_mapping
from inputremapper.key import Key
from inputremapper.injection.global_uinputs import global_uinputs


class MappingHandler:
    """Can be notified of new events to inject them. Base class."""
    _config: Dict[str, any]
    _key: Key
    target: str

    def __init__(self, config_dict: Dict[str, any]) -> None:
        """Initialize event consuming functionality."""
        self._config = copy.deepcopy(config_dict)
        self._key = Key(self._config['key'])
        self.target = self._config["target"]

    def might_handle(self, event_type: int, event_code: int) -> bool:
        """Check if the handler cares about this at all"""
        return self._key.contains_event(event_type, event_code)

    async def notify(self, event: evdev.InputEvent) -> bool:
        """A new event is ready.

        return if the event was actually taken care of

        Overwrite this function if the consumer should do something each time
        a new event arrives. E.g. mapping a single button once clicked.
        """
        raise NotImplementedError

    async def run(self) -> None:
        """Start doing things.

        Overwrite this function if the consumer should do something
        continuously even if no new event arrives. e.g. continuously injecting
        mouse movement events.
        """
        raise NotImplementedError

    def inject(self, event_tuple: Tuple) -> None:
        logger.debug("injecting form new mapping handler: %s", event_tuple)
        global_uinputs.write(event_tuple, self.target)


class KeysToKeyHandler(MappingHandler):

    _key_map: Dict[Tuple[int, int], bool]
    _active: bool  # keep track if the target key is pressed down
    maps_to: Tuple[int, int]

    def __init__(self, config: Dict[str, any]) -> None:
        super().__init__(config)

        self._active = False
        self._key_map = {}
        for sub_key in self._key:  # prepare key_map
            self._key_map[sub_key[:2]] = False

        self.maps_to = (evdev.ecodes.EV_KEY, system_mapping.get(self._config["symbol"]))

    async def notify(self, event: evdev.InputEvent) -> bool:
        map_key = (event.type, event.code)
        if map_key not in self._key_map.keys():
            return False  # we are not responsible for the event

        if not self.update_key_map(map_key, event.value == 1):
            return False  # nothing changed ignore this event

        if self.get_active() == self._active:
            return False

        self._active = self.get_active() and not utils.is_key_up(event.value)
        if self._active:
            value = 1
        else:
            value = 0

        print("warum kommt der folgende key_spam nicht immer an?")
        logger.key_spam(self._key, "maps to (%s)", self.maps_to)
        self.inject((*self.maps_to, value))
        return True

    async def run(self) -> None:  # no debouncer or anything (yet)
        pass

    def update_key_map(self, map_key: Tuple[int, int], value: bool) -> bool:
        """update the keymap and return if it changed"""
        old = self._key_map[map_key]
        self._key_map[map_key] = value
        return old != value

    def get_active(self) -> bool:
        return False not in self._key_map.values()


class HierarchyKeyHandler(MappingHandler):
    """handler consisting of an ordered list of KeysToKeyHandler

    only the first handler which successfully handles a key_down event will execute the key_down
    all other handlers will receive a key up event.
    All handlers receive key up events.
    """
    def __init__(self, target: str, handlers: List[KeysToKeyHandler]) -> None:
        cfg = {
            "key": None,
            "target": target,
        }
        super().__init__(cfg)
        self.handlers = handlers

    async def run(self) -> None:
        pass

    async def notify(self, event: evdev.InputEvent) -> bool:
        if event.value == 1:
            return self.handle_key_down(event)
        else:
            return self.handle_key_up(event)

    def handle_key_up(self, event: evdev.InputEvent) -> bool:
        success = False
        for handler in self.handlers:
            success = await handler.notify(event)
        return success

    def handle_key_down(self, event: evdev.InputEvent) -> bool:
        successful_handler = None
        success = False
        for handler in self.handlers:
            success = await handler.notify(event)
            if success:
                successful_handler = handler
                break

        event.value = 0
        for handler in self.handlers:
            if handler is successful_handler:
                continue
            asyncio.ensure_future(handler.notify(event))  # we don't care if they did anything with that
        return success


mapping_handler_classes: Dict[str, Type[MappingHandler]] = {
    # all available mapping_handlers
    "keys_to_key": KeysToKeyHandler,
}


def create_handler(config: Dict[str, any]) -> MappingHandler:
    """return the MappingHandler"""
    return mapping_handler_classes[config['type']](config)
