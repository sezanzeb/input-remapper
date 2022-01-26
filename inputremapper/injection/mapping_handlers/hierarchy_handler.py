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
import asyncio
import evdev

from typing import Tuple, List

from inputremapper.injection.mapping_handlers.mapping_handler import MappingHandler


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
