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
from ..configs.preset import find_newest_preset
from ..injection.global_uinputs import global_uinputs


class Controller:
    """implements the behaviour of the gui"""

    def __init__(self, event_handler: EventHandler):
        self.event_handler = event_handler
        self.data_manager = DataManager(event_handler)

        self.attach_to_events()

    def attach_to_events(self) -> None:
        self.event_handler.subscribe(EventEnum.init, self.on_init)

    def on_init(self):
        self.event_handler.emit(EventEnum.load_groups)
        self.select_newest_preset()

    def select_newest_preset(self):
        group_key, preset = find_newest_preset()
        self.event_handler.emit(EventEnum.load_group, group_key=group_key)
        self.event_handler.emit(EventEnum.load_preset, name=preset)
