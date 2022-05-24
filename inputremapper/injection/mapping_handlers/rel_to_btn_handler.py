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

from typing import Optional, Dict
from evdev.ecodes import EV_REL

from inputremapper.configs.mapping import Mapping
from inputremapper.logger import logger
from inputremapper.input_event import InputEvent, EventActions
from inputremapper.event_combination import EventCombination
from inputremapper.injection.mapping_handlers.mapping_handler import (
    MappingHandler,
    ContextProtocol,
    HandlerEnums,
    InputEventHandler,
)


class RelToBtnHandler(MappingHandler):
    """Handler which transforms an EV_REL to a button event
    and sends that to a sub_handler

    adheres to the MappingHandler protocol
    """

    _active: bool
    _input_event: InputEvent
    _last_activation: float
    _sub_handler: InputEventHandler

    def __init__(
        self,
        combination: EventCombination,
        mapping: Mapping,
        **_,
    ) -> None:
        super().__init__(combination, mapping)

        self._active = False
        self._input_event = combination[0]
        self._last_activation = time.time()
        self._abort_release = False
        assert self._input_event.value != 0
        assert len(combination) == 1

    def __str__(self):
        return f"RelToBtnHandler for {self._input_event.event_tuple} <{id(self)}>:"

    def __repr__(self):
        return self.__str__()

    @property
    def child(self):  # used for logging
        return self._sub_handler

    async def _stage_release(self, source, forward, supress):
        while time.time() < self._last_activation + self.mapping.release_timeout:
            await asyncio.sleep(1 / self.mapping.rate)

        if self._abort_release:
            self._abort_release = False
            return

        event = self._input_event.modify(value=0, actions=(EventActions.as_key,))
        logger.debug_key(event.event_tuple, "sending to sub_handler")
        self._sub_handler.notify(event, source, forward, supress)
        self._active = False

    def notify(
        self,
        event: InputEvent,
        source: evdev.InputDevice,
        forward: evdev.UInput,
        supress: bool = False,
    ) -> bool:

        assert event.type == EV_REL
        if event.type_and_code != self._input_event.type_and_code:
            return False

        threshold = self._input_event.value
        value = event.value
        if (value < threshold > 0) or (value > threshold < 0):
            if self._active:
                # the axis is below the threshold and the stage_release
                # function is running
                event = event.modify(value=0, actions=(EventActions.as_key,))
                logger.debug_key(event.event_tuple, "sending to sub_handler")
                self._abort_release = True
            else:
                # don't consume the event.
                # We could return True to consume events
                return False
        else:
            # the axis is above the threshold
            if not self._active:
                asyncio.ensure_future(self._stage_release(source, forward, supress))
            if value > threshold:
                direction = EventActions.positive_trigger
            else:
                direction = EventActions.negative_trigger
            self._last_activation = time.time()
            event = event.modify(value=1, actions=(EventActions.as_key, direction))

        self._active = bool(event.value)
        # logger.debug_key(event.event_tuple, "sending to sub_handler")
        return self._sub_handler.notify(
            event, source=source, forward=forward, supress=supress
        )

    def reset(self) -> None:
        if self._active:
            self._abort_release = True

        self._active = False
        self._sub_handler.reset()
