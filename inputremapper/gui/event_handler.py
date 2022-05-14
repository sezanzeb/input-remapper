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

import re
import enum
import traceback
from typing import Callable, Dict, Set, TypedDict, overload, Any, Optional, Tuple

from inputremapper.logger import logger


class EventEnum(str, enum.Enum):
    # emit to reset the gui
    reset_gui = "reset_gui"
    # emit to load all groups
    load_groups = "load_groups"
    # emit to provide all groups. Parameter: groups
    groups_changed = "groups_changed"

    # emit to load a group. Parameter: group_key
    load_group = "load_group"
    # emit to provide all presets in the loaded group. Parameter: group_key, presets
    group_changed = "group_changed"

    # emit to request a preset. Parameter: name
    load_preset = "load_preset"
    # emit to rename a preset. Parameter: new_name
    rename_preset = "rename_preset"
    # emit to add a preset the current group. Parameter: name
    add_preset = "add_preset"
    # emit to delete the current preset
    delete_preset = "delete_preset"
    # emit to provide a preset. Parameter: name, mappings
    preset_changed = "preset_changed"

    # emit to request a mapping. Parameter: combination
    load_mapping = "load_mapping"
    # emit to create a empty mapping
    create_mapping = "create_mapping"
    # update the current mapping. Parameter: mapping fields as keyword arguments
    update_mapping = "update_mapping"
    # delete the current mapping
    delete_mapping = "delete_mapping"
    # emit to provide a updated mapping. Parameter: mapping
    mapping_changed = "mapping_changed"
    # emit to provide a new active mapping. Parameter: mapping
    mapping_loaded = "mapping_loaded"

    # emit to request to autoload status for the current preset.
    get_autoload = "get_autoload"
    # emit to set to autoload status for the current preset. Parameter: autoload
    set_autoload = "set_autoload"
    # emit to provide to autoload status. Parameters: autoload
    autoload_changed = "autoload_changed"

    # emit to request available uinputs
    get_uinputs = "get_uinputs"
    # emit to provide available uinputs. Parameter: uinputs
    uinputs_changed = "uinputs_changed"

    # emit to save all data
    save = "save"

    # initialize the data, should be emitted once all event listeners are attached
    # and the GUI is ready to receive data
    init = "init"
    # two events for unit tests
    test_ev1 = "test_event1"
    test_ev2 = "test_event2"


EventListener = Callable[[Any], Optional[Callable]]


class EventHandler:
    def __init__(self):
        self._listeners: Dict[EventEnum, Set[EventListener]] = {
            event: set() for event in EventEnum
        }
        self.shorten_path = re.compile("inputremapper/")

    def emit(self, event: EventEnum, **kwargs) -> EventHandler:
        file, line = self.get_caller()
        logger.debug(f"{file}:{line}: emitting {event} with {kwargs}")
        call_later = {listener(**kwargs) for listener in self._listeners[event]}
        try:
            call_later.remove(None)
        except KeyError:
            pass

        for callback in call_later:
            callback()
        return self

    def get_caller(self, position: int = 3) -> Tuple[str, int]:
        """extract a file and line from current stack and format for logging"""
        tb = traceback.extract_stack(limit=position)[0]
        filename = tb.filename
        match = self.shorten_path.search(filename)
        if match:
            filename = tb.filename[match.regs[0][1] :]
        return filename, tb.lineno

    def subscribe(self, event: EventEnum, listener: EventListener) -> EventHandler:
        """attach a listener to an event.
        The listener can optionally return a callable which
        will be called after all other listeners have been called"""
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
