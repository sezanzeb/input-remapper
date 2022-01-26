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

from evdev.ecodes import EV_ABS

from inputremapper.logger import logger
from inputremapper.key import Key
from inputremapper.injection.mapping_handlers.mapping_handler import (
    MappingHandler,
    copy_event,
)


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

    def __init__(
        self, sub_handler: MappingHandler, trigger_percent: int, key: Key
    ) -> None:
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

        if (ev_copy.value == 1 and self._active) or (
            ev_copy.value != 1 and not self._active
        ):
            return True

        self._active = bool(ev_copy.value)
        logger.debug_key(
            (ev_copy.type, ev_copy.code, ev_copy.value), "sending to sub_handler"
        )
        return await self._handler.notify(
            ev_copy,
            source=source,
            forward=forward,
            supress=supress,
        )
