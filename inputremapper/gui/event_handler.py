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
from __future__ import annotations

import enum
from typing import Callable, Dict, Set, TypedDict, overload

from inputremapper.logger import logger


class EventEnum(str, enum.Enum):
    # emit to load a group. Parameter: group_key
    load_group = "load_group"
    # emit to provide all presets in the loaded group. Parameter: presets
    group_loaded = "group_loaded"

    # emit to request a preset. Parameter: name
    load_preset = "load_preset"
    # emit to rename a preset. Parameter: new_name
    rename_preset = "rename_preset"
    # emit to add a preset the current group. Parameter: name
    add_preset = "add_preset"
    # emit to delete the current preset
    delete_preset = "delete_preset"
    # emit to provide a preset. Parameter: name, mappings
    preset_loaded = "preset_loaded"

    # emit to request a mapping. Parameter: combination
    load_mapping = "load_mapping"
    # emit to create a empty mapping
    create_mapping = "create_mapping"
    # update the current mapping. Parameter: mapping fields as keyword arguments
    update_mapping = "update_mapping"
    # delete the current mapping
    delete_mapping = "delete_mapping"
    # emit to provide a mapping. Parameter: mapping
    mapping_loaded = "mapping_loaded"

    # emit to request to autoload status for the current preset.
    get_autoload = "get_autoload"
    # emit to set to autoload status for the current preset. Parameter: autoload
    set_autoload = "set_autoload"
    # emit to provide to autoload status. Parameters: autoload
    autoload_status = "autoload_status"

    # emit to save all data
    save = "save"

    # two events for unit tests
    test_ev1 = "test_event1"
    test_ev2 = "test_event2"


EventListener = Callable[[...], None]


class EventHandler:
    def __init__(self):
        self._listeners: Dict[EventEnum, Set[EventListener]] = {
            event: set() for event in EventEnum
        }

    def emit(self, event: EventEnum, **kwargs) -> EventHandler:
        for listener in self._listeners[event]:
            listener(**kwargs)
        return self

    def subscribe(self, event: EventEnum, listener: EventListener) -> EventHandler:
        if event not in self._listeners:
            raise KeyError(event)
        logger.debug("adding new EventListener: %s", listener)
        self._listeners[event].add(listener)
        return self

    def unsubscribe(self, listener: EventListener) -> None:
        for listeners in self._listeners.values():
            try:
                listeners.remove(listener)
            except KeyError:
                pass