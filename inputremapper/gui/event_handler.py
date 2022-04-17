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
import enum
from typing import Callable, Dict, Set


from inputremapper.logger import logger


class GuiEvents(str, enum.Enum):

    # two events for unit tests
    test_ev1 = "test_event1"
    test_ev2 = "test_event2"


GuiEventListener = Callable[[...], None]


class GuiEventHandler:
    def __init__(self):
        self._listeners: Dict[GuiEvents, Set[GuiEventListener]] = {
            event: set() for event in GuiEvents
        }

    def emit(self, event: GuiEvents, **kwargs) -> None:
        for listener in self._listeners[event]:
            listener(**kwargs)

    def subscribe(self, event: GuiEvents, listener: GuiEventListener) -> None:
        if event not in self._listeners:
            raise KeyError(event)
        logger.debug("adding new GuiEventListener: %s", listener)
        self._listeners[event].add(listener)

    def unsubscribe(self, listener: GuiEventListener) -> None:
        for listeners in self._listeners.values():
            try:
                listeners.remove(listener)
            except KeyError:
                pass
