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
from abc import abstractmethod, ABC
from typing import Dict, Tuple, Type, List, Protocol

import evdev
from inputremapper.injection.macros.parse import is_this_a_macro

from inputremapper import utils
from inputremapper.logger import logger
from inputremapper.system_mapping import system_mapping
from inputremapper.key import Key
from inputremapper.injection.global_uinputs import global_uinputs
from inputremapper import exceptions


def copy_event(event: evdev.InputEvent) -> evdev.InputEvent:
    return evdev.InputEvent(
        sec=event.sec,
        usec=event.usec,
        type=event.type,
        code=event.code,
        value=event.value,
    )


class CombinationSubHandler(Protocol):
    """Protocol any handler which can be triggered by a combination must implement"""
    @property
    def active(self) -> bool: ...
    async def notify(self, event: evdev.InputEvent) -> bool: ...
    async def run(self) -> None: ...


class MappingHandler(ABC):
    """Can be notified of new events to inject them. Base class."""
    # hierarchic mapping handlers e.g. KeysToKeyHandler will get sorted to make sure
    # only one handler will receive the event. This allows mapping of combinations
    # to override other combinations.
    # Non-hierarchic handlers will always receive all events they care about
    hierarchic = False

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


class CombinationHandler(MappingHandler):
    """keeps track of a combination and notifies a sub handler"""

    _key: Key
    _key_map: Dict[Tuple[int, int], bool]
    _sub_handler: CombinationSubHandler
    hierarchic = True

    def __init__(self, config: Dict[str, any]) -> None:
        """initialize the handler

        Parameters
        ----------
        config : Dict = {
            "key": Key
            "target": str
            "symbol": str
        }
        """
        super().__init__()
        self._key = Key(config["key"])
        self._key_map = {}
        for sub_key in self._key:  # prepare key_map
            self._key_map[sub_key[:2]] = False

        if is_this_a_macro(config['symbol']):
            raise NotImplementedError
        else:
            self._sub_handler = KeyHandler(config)

    async def notify(self,
                     event: evdev.InputEvent,
                     source: evdev.InputDevice = None,
                     forward: evdev.UInput = None,
                     supress: bool = False) -> bool:

        map_key = (event.type, event.code)
        if map_key not in self._key_map.keys():
            return False  # we are not responsible for the event

        self._key_map[map_key] = event.value == 1
        if self.get_active() == self._sub_handler.active:
            return False  # nothing changed ignore this event

        if self.get_active() and not utils.is_key_up(event.value) and forward:
            self.forward_release(forward)

        if supress:
            return False

        is_key_down = self.get_active() and not utils.is_key_up(event.value)
        if is_key_down:
            value = 1
        else:
            value = 0
        ev = copy_event(event)
        ev.value = value
        logger.key_spam(self._key, "triggered: sending to sub-handler")
        return await self._sub_handler.notify(ev)

    async def run(self) -> None:  # no debouncer or anything (yet)
        asyncio.ensure_future(self._sub_handler.run())

    def get_active(self) -> bool:
        """return if all keys in the keymap are set to True"""
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


class KeyHandler(MappingHandler):
    """injects the target key if notified

    adheres to the CombinationSubHandler protocol
    """
    _target: str
    _maps_to: Tuple[int, int]
    _active: bool

    def __init__(self, config: Dict[str, any]):
        """initialize the handler

        Parameters
        ----------
        config : Dict[str, any]
            configuration dict with the keys:
            "target", "symbol"
        """
        super().__init__()
        self._target = config['target']
        self._maps_to = (evdev.ecodes.EV_KEY, system_mapping.get(config["symbol"]))
        self._active = False

    async def run(self) -> None:
        pass

    async def notify(self,
                     event: evdev.InputEvent,
                     source: evdev.InputDevice = None,
                     forward: evdev.UInput = None,
                     supress: bool = False) -> bool:
        """inject event.value to the target key"""

        event_tuple = (*self._maps_to, event.value)
        try:
            global_uinputs.write(event_tuple, self._target)
            logger.key_spam(event_tuple, "sending to %s", self._target)
            self._active = event.value == 1
            return True
        except exceptions.Error:
            return False

    @property
    def active(self) -> bool:
        return self._active


class HierarchyHandler(MappingHandler):
    """handler consisting of an ordered list of MappingHandler

    only the first handler which successfully handles the event will execute it,
    all other handlers will be notified, but suppressed
    """
    hierarchic = False

    def __init__(self, handlers: List[MappingHandler]) -> None:
        self.handlers = handlers
        super().__init__()

    async def run(self) -> None:
        for handler in self.handlers:
            asyncio.ensure_future(handler.run())

    async def notify(self,
                     event: evdev.InputEvent,
                     source: evdev.InputDevice = None,
                     forward: evdev.UInput = None,
                     supress: bool = False) -> bool:

        success = False
        for handler in self.handlers:
            if not success:
                success = await handler.notify(event, forward=forward)
            else:
                asyncio.ensure_future(handler.notify(event,
                                                     forward=forward,
                                                     supress=True))
        return success


mapping_handler_classes: Dict[str, Type[MappingHandler]] = {
    # all available mapping_handlers
    "keys_to_key": CombinationHandler,
}


def create_handler(config: Dict[str, any]) -> MappingHandler:
    """return the MappingHandler"""
    return mapping_handler_classes[config['type']](config)
