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
import evdev

from typing import Dict, Tuple, List, Protocol, Set
from evdev.ecodes import EV_ABS

from inputremapper import utils
from inputremapper import exceptions
from inputremapper.logger import logger
from inputremapper.key import Key
from inputremapper.mapping import Mapping
from inputremapper.system_mapping import system_mapping
from inputremapper.injection.macros.macro import Macro
from inputremapper.injection.macros.parse import parse, is_this_a_macro
from inputremapper.injection.global_uinputs import global_uinputs


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

    mapping: Mapping
    listeners: Set[EventListener]


class CombinationSubHandler(Protocol):
    """Protocol any handler which can be triggered by a combination must implement"""

    @property
    def active(self) -> bool:
        ...

    async def notify(self, event: evdev.InputEvent) -> bool:
        ...

    async def run(self) -> None:
        ...


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

    async def run(self) -> None:
        ...


class CombinationHandler:
    """keeps track of a combination and notifies a sub handler

    adheres to the MappingHandler protocol
    """

    _key: Key
    _key_map: Dict[Tuple[int, int], bool]
    _sub_handler: CombinationSubHandler

    def __init__(self, config: Dict[str, any], context: ContextProtocol) -> None:
        """initialize the handler

        Parameters
        ----------
        config : Dict = {
            "key": str
            "target": str
            "symbol": str
        }
        context : Context
        """
        super().__init__()
        self._key = Key(config["key"])
        self._key_map = {}
        for sub_key in self._key:  # prepare key_map
            self._key_map[sub_key[:2]] = False

        if is_this_a_macro(config["symbol"]):
            self._sub_handler = MacroHandler(config, context)
        else:
            self._sub_handler = KeyHandler(config)

    def __str__(self):
        return f"CombinationHandler for {self._key[:]} <{id(self)}>:"

    def __repr__(self):
        return self.__str__()

    @property
    def child(self):  # used for logging
        return self._sub_handler

    async def notify(
        self,
        event: evdev.InputEvent,
        source: evdev.InputDevice = None,
        forward: evdev.UInput = None,
        supress: bool = False,
    ) -> bool:

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
        logger.debug_key(self._key, "triggered: sending to sub-handler")
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


class KeyHandler:
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
        config : Dict = {
            "target": str
            "symbol": str
        }
        """
        super().__init__()
        self._target = config["target"]
        self._maps_to = (evdev.ecodes.EV_KEY, system_mapping.get(config["symbol"]))
        self._active = False

    def __str__(self):
        return f"KeyHandler <{id(self)}>:"

    def __repr__(self):
        return self.__str__()

    @property
    def child(self):  # used for logging
        return f"maps to: {self._maps_to} on {self._target}"

    async def run(self) -> None:
        pass

    async def notify(self, event: evdev.InputEvent) -> bool:
        """inject event.value to the target key"""

        event_tuple = (*self._maps_to, event.value)
        try:
            global_uinputs.write(event_tuple, self._target)
            logger.debug_key(event_tuple, "sending to %s", self._target)
            self._active = event.value == 1
            return True
        except exceptions.Error:
            return False

    @property
    def active(self) -> bool:
        return self._active


class MacroHandler:
    """runs the target macro if notified

    adheres to the CombinationSubHandler protocol
    """

    # TODO: replace this by the macro itself
    _target: str
    _macro: Macro
    _active: bool

    def __init__(self, config: Dict[str, any], context: ContextProtocol):
        """initialize the handler

        Parameters
        ----------
        config : Dict = {
            "target": str
            "symbol": str
        }
        """
        super().__init__()
        self._target = config["target"]
        self._active = False
        self._macro = parse(config["symbol"], context)

    def __str__(self):
        return f"MacroHandler <{id(self)}>:"

    def __repr__(self):
        return self.__str__()

    @property
    def child(self):  # used for logging
        return f"maps to {self._macro} on {self._target}"

    async def notify(self, event: evdev.InputEvent) -> bool:

        if event.value == 1:
            self._active = True
            self._macro.press_trigger(event)
            if self._macro.running:
                return True

            def f(ev_type, code, value):
                """Handler for macros."""
                logger.debug_key(
                    (ev_type, code, value), "sending from macro to %s", self._target
                )
                global_uinputs.write((ev_type, code, value), self._target)

            asyncio.ensure_future(self._macro.run(f))
            return True
        else:
            self._active = False
            if self._macro.is_holding():
                self._macro.release_trigger()

            return True

    async def run(self) -> None:
        pass

    @property
    def active(self) -> bool:
        return self._active


class HierarchyHandler:
    """handler consisting of an ordered list of MappingHandler

    only the first handler which successfully handles the event will execute it,
    all other handlers will be notified, but suppressed

    adheres to the MappingHandler protocol
    """
    _key: Tuple[int, int]

    def __init__(self, handlers: List[MappingHandler], key: Tuple[int, int]) -> None:
        self.handlers = handlers
        self._key = key

    def __str__(self):
        return f"HierarchyHandler for {self._key} <{id(self)}>:"

    def __repr__(self):
        return self.__str__()

    @property
    def child(self):  # used for logging
        return self.handlers

    async def run(self) -> None:
        for handler in self.handlers:
            asyncio.ensure_future(handler.run())

    async def notify(
        self,
        event: evdev.InputEvent,
        source: evdev.InputDevice = None,
        forward: evdev.UInput = None,
        supress: bool = False,
    ) -> bool:
        if (event.type, event.code) != self._key:
            return False

        success = False
        for handler in self.handlers:
            if not success:
                success = await handler.notify(event, forward=forward)
            else:
                asyncio.ensure_future(
                    handler.notify(event, forward=forward, supress=True)
                )
        return success


class AbsToBtnHandler:
    """
    Handler which transforms an EV_ABS to a button event
    and sends that to a sub_handler

    adheres to the MappingHandler protocol
    """
    _handler: MappingHandler
    _trigger_percent: int
    _active: bool
    _key: Key

    def __init__(self, sub_handler: MappingHandler, trigger_percent: int, key: Key) -> None:
        self._handler = sub_handler
        if trigger_percent not in range(-99, 100):
            raise ValueError(f"trigger_percent must be between -100 and 100")
        if trigger_percent == 0:
            raise ValueError(f"trigger_percent can not be 0")

        self._trigger_percent = trigger_percent
        self._key = key
        self._active = False

    def __str__(self):
        return f"AbsToBtnHandler for {self._key[0]} <{id(self)}>:"

    def __repr__(self):
        return self.__str__()

    @property
    def child(self):  # used for logging
        return self._handler

    async def run(self) -> None:
        asyncio.ensure_future(self._handler.run())

    def _trigger_point(self, abs_min: int, abs_max: int) -> int:
        #  TODO: potentially cash this function
        if abs_min == -1 and abs_max == 1:
            return 0  # this is a hat switch

        half_range = (abs_max - abs_min) / 2
        middle = half_range + abs_min
        trigger_offset = half_range * self._trigger_percent / 100
        return int(middle + trigger_offset)

    async def notify(
            self,
            event: evdev.InputEvent,
            source: evdev.InputDevice = None,
            forward: evdev.UInput = None,
            supress: bool = False,
            ) -> bool:

        assert event.type == EV_ABS
        if (event.type, event.code) != self._key[0][:2]:
            return False

        absinfo = source.absinfo(event.code)
        ev_copy = copy_event(event)
        trigger_point = self._trigger_point(absinfo.min, absinfo.max)

        if self._trigger_percent > 0:
            if event.value > trigger_point:
                ev_copy.value = 1
            else:
                ev_copy.value = 0
        else:
            if event.value < trigger_point:
                ev_copy.value = 1
            else:
                ev_copy.value = 0

        if (ev_copy.value == 1 and self._active) or (ev_copy.value != 1 and not self._active):
            return True

        self._active = bool(ev_copy.value)
        logger.debug_key((ev_copy.type, ev_copy.code, ev_copy.value), "sending to sub_handler")
        return await self._handler.notify(
            ev_copy,
            source=source,
            forward=forward,
            supress=supress,
            )
