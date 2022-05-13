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
from typing import List, Tuple, Optional

from .data_manager import DataManager
from .event_handler import EventHandler, EventEnum
from .utils import gtk_iteration
from ..configs.global_config import global_config
from ..configs.preset import find_newest_preset
from ..event_combination import EventCombination
from ..groups import (
    _Groups,
    GAMEPAD,
    KEYBOARD,
    UNKNOWN,
    GRAPHICS_TABLET,
    TOUCHPAD,
    MOUSE,
)
from ..injection.global_uinputs import global_uinputs
from ..logger import logger

ICON_NAMES = {
    GAMEPAD: "input-gaming",
    MOUSE: "input-mouse",
    KEYBOARD: "input-keyboard",
    GRAPHICS_TABLET: "input-tablet",
    TOUCHPAD: "input-touchpad",
    UNKNOWN: None,
}

# sort types that most devices would fall in easily to the right.
ICON_PRIORITIES = [GRAPHICS_TABLET, TOUCHPAD, GAMEPAD, MOUSE, KEYBOARD, UNKNOWN]


class Controller:
    """implements the behaviour of the gui"""

    def __init__(self, event_handler: EventHandler, data_manager: DataManager):
        self.event_handler = event_handler
        self.reader = data_manager.reader
        self.data_manager = data_manager

        self.attach_to_events()
        self.on_init()

    def attach_to_events(self) -> None:
        (
            self.event_handler.subscribe(EventEnum.init, self.on_init)
            .subscribe(EventEnum.load_groups, self.on_load_groups)
            .subscribe(EventEnum.load_group, self.on_load_group)
            .subscribe(EventEnum.load_preset, self.on_load_preset)
            .subscribe(EventEnum.rename_preset, self.on_rename_preset)
            .subscribe(EventEnum.add_preset, self.on_add_preset)
            .subscribe(EventEnum.delete_preset, self.on_delete_preset)
            .subscribe(EventEnum.load_mapping, self.on_load_mapping)
            .subscribe(EventEnum.create_mapping, self.on_create_mapping)
            .subscribe(EventEnum.delete_mapping, self.on_delete_mapping)
            .subscribe(EventEnum.update_mapping, self.on_update_mapping)
            .subscribe(EventEnum.get_autoload, self.on_get_autoload)
            .subscribe(EventEnum.set_autoload, self.on_set_autoload)
            .subscribe(EventEnum.get_uinputs, self.on_get_uinputs)
            .subscribe(EventEnum.save, self.on_save)
        )

    def on_init(self):
        # provide all possible groups
        # self.data_manager.groups.refresh()
        self.reader.refresh_groups()
        while not self.reader.are_new_groups_available():
            gtk_iteration()

        groups: List[Tuple[str, Optional[str]]] = []
        for group in self.data_manager.groups.filter(include_inputremapper=False):
            types = group.types
            if len(types) > 0:
                device_type = sorted(types, key=ICON_PRIORITIES.index)[0]
                icon_name = ICON_NAMES[device_type]
            else:
                icon_name = None

            groups.append((group.key, icon_name))
        self.event_handler.emit(EventEnum.groups_changed, groups=groups)

        # load the newest group and preset
        self.data_manager.load_group(self.data_manager.newest_group())
        self.data_manager.load_preset(self.data_manager.newest_preset())
        # Todo: load a mapping

    def on_load_groups(self):
        self.event_handler.emit(EventEnum.reset_gui)
        self.on_init()

    def on_load_group(self, group_key: str):
        self.data_manager.load_group(group_key)
        self.data_manager.load_preset(self.data_manager.newest_preset())

    def on_load_preset(self, name: str):
        self.data_manager.load_preset(name)

    def on_rename_preset(self, new_name: str):
        self.data_manager.rename_preset(new_name)

    def on_add_preset(self, name: str):
        self.data_manager.add_preset(name)

    def on_delete_preset(self):
        self.data_manager.delete_preset()

    def on_load_mapping(self, combination: EventCombination):
        self.data_manager.load_mapping(combination)

    def on_update_mapping(self, **kwargs):
        self.data_manager.update_mapping(**kwargs)

    def on_create_mapping(self):
        self.data_manager.create_mapping()
        self.data_manager.load_mapping(combination=EventCombination.empty_combination())

    def on_delete_mapping(self):
        self.data_manager.delete_mapping()

    def on_get_autoload(self):
        self.data_manager.emit_autoload_changed()

    def on_set_autoload(self, autoload: bool):
        self.data_manager.set_autoload(autoload)

    def on_get_uinputs(self):
        self.data_manager.get_uinputs()

    def on_save(self):
        self.data_manager.save()
