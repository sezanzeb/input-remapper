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
from inputremapper.input_event import InputEvent
from inputremapper.event_combination import EventCombination
from inputremapper.injection.mapping_handlers.mapping_handler import MappingHandler


class RelToBtnHandler:
    """
    Handler which transforms an EV_REL to a button event
    and sends that to a sub_handler

    adheres to the MappingHandler protocol
    """

    _handler: MappingHandler
    _trigger_point: int
    _active: bool
    _event: InputEvent
    _last_activation: float

    def __init__(
        self, sub_handler: MappingHandler, trigger_point: int, event: InputEvent
    ) -> None:
        if trigger_point == 0:
            raise ValueError("trigger_point can not be 0")

        self._handler = sub_handler
        self._trigger_point = trigger_point
        self._event = event
        self._active = False
        self._last_activation = time.time()

    def __str__(self):
        return f"RelToBtnHandler for {self._event} <{id(self)}>:"

    def __repr__(self):
        return self.__str__()

    @property
    def child(self):  # used for logging
        return self._handler

    async def stage_release(self):
        while time.time() < self._last_activation + 0.05:
            await asyncio.sleep(1 / 60)

        event = self._event.modify(value=0)
        asyncio.ensure_future(self._handler.notify(event))
        self._active = False

    async def notify(
        self,
        event: InputEvent,
        source: evdev.InputDevice = None,
        forward: evdev.UInput = None,
        supress: bool = False,
    ) -> bool:

        assert event.type == EV_REL
        if event.type_and_code != self._event.type_and_code:
            return False

        value = event.value
        if (value < self._trigger_point > 0) or (value > self._trigger_point < 0):
            return True

        if self._active:
            self._last_activation = time.time()
            return True

        event = event.modify(value=1)
        logger.debug_key(event.event_tuple, "sending to sub_handler")
        self._active = True
        self._last_activation = time.time()
        asyncio.ensure_future(self.stage_release())
        return await self._handler.notify(
            event,
            source=source,
            forward=forward,
            supress=supress,
        )
