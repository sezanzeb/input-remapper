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

import evdev
import time
import asyncio

from evdev.ecodes import EV_REL

from inputremapper.logger import logger
from inputremapper.key import Key
from inputremapper.injection.mapping_handlers.mapping_handler import (
    MappingHandler,
    copy_event,
)


class RelToBtnHandler:
    """
    Handler which transforms an EV_REL to a button event
    and sends that to a sub_handler

    adheres to the MappingHandler protocol
    """

    _handler: MappingHandler
    _trigger_point: int
    _active: bool
    _key: Key
    _last_activation: float

    def __init__(
        self, sub_handler: MappingHandler, trigger_point: int, key: Key
    ) -> None:
        if trigger_point == 0:
            raise ValueError("trigger_point can not be 0")

        self._handler = sub_handler
        self._trigger_point = trigger_point
        self._key = key
        self._active = False
        self._last_activation = time.time()

    def __str__(self):
        return f"RelToBtnHandler for {self._key[0]} <{id(self)}>:"

    def __repr__(self):
        return self.__str__()

    @property
    def child(self):  # used for logging
        return self._handler

    async def stage_release(self):
        while time.time() < self._last_activation + 0.05:
            await asyncio.sleep(1 / 60)

        event = evdev.InputEvent(0, 0, *self._key[0][:2], 0)
        asyncio.ensure_future(self._handler.notify(event))
        self._active = False

    async def notify(
        self,
        event: evdev.InputEvent,
        source: evdev.InputDevice = None,
        forward: evdev.UInput = None,
        supress: bool = False,
    ) -> bool:

        assert event.type == EV_REL
        if (event.type, event.code) != self._key[0][:2]:
            return False

        value = event.value
        if (value < self._trigger_point > 0) or (value > self._trigger_point < 0):
            return True

        if self._active:
            self._last_activation = time.time()
            return True

        ev_copy = copy_event(event)
        ev_copy.value = 1
        logger.debug_key(
            (ev_copy.type, ev_copy.code, ev_copy.value), "sending to sub_handler"
        )
        self._active = True
        self._last_activation = time.time()
        asyncio.ensure_future(self.stage_release())
        return await self._handler.notify(
            ev_copy,
            source=source,
            forward=forward,
            supress=supress,
        )
