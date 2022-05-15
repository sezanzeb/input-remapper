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

from .data_manager import DataManager
from .event_handler import EventHandler, EventEnum
from ..event_combination import EventCombination


class Controller:
    """implements the behaviour of the gui"""

    def __init__(self, event_handler: EventHandler, data_manager: DataManager):
        self.event_handler = event_handler
        self.data_manager = data_manager

        self.attach_to_events()

    def attach_to_events(self) -> None:
        (
            self.event_handler.subscribe(EventEnum.init, self.on_init)
            .subscribe(EventEnum.load_groups, self.on_load_groups)
            .subscribe(EventEnum.groups_changed, self.on_groups_changed)
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
        # make sure we get a groups_changed event when everything is ready
        # this might not be necessary if the helper takes longer to provide the
        # initial groups
        self.data_manager.backend.emit_groups()
        self.data_manager.get_uinputs()

    def on_groups_changed(self, **_):
        """load the newest group as soon as everyone got notified
        about the updated groups"""

        def callback():
            # this will run after all other listeners where executed
            self.on_load_group(self.data_manager.newest_group())

        return callback

    def on_load_groups(self):
        self.event_handler.emit(EventEnum.reset_gui)
        self.data_manager.backend.refresh_groups()

    def on_load_group(self, group_key: str):
        self.data_manager.load_group(group_key)
        try:
            self.data_manager.load_preset(self.data_manager.newest_preset())
        except FileNotFoundError:
            # todo: create empty preset
            pass

    def on_load_preset(self, name: str):
        self.data_manager.load_preset(name)

    def on_rename_preset(self, new_name: str):
        self.data_manager.rename_preset(new_name)

    def on_add_preset(self, name: str):
        self.data_manager.add_preset(name)

    def on_delete_preset(self):
        self.data_manager.delete_preset()

    def on_load_mapping(self, event_combination: EventCombination):
        self.data_manager.load_mapping(event_combination)

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
