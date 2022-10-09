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
from typing import Optional

from gi.repository import Gtk

from inputremapper.gui.components.common import FlowBoxEntry, FlowBoxWrapper
from inputremapper.gui.components.editor import ICON_PRIORITIES, ICON_NAMES
from inputremapper.gui.components.main import Stack
from inputremapper.gui.controller import Controller
from inputremapper.gui.message_broker import (
    MessageBroker,
    DoStackSwitch,
    MessageType,
    GroupsData,
    GroupData,
)
from inputremapper.logger import logger


class DeviceGroupEntry(FlowBoxEntry):
    """A device that can be selected in the GUI.

    For example a keyboard or a mouse.
    """

    __gtype_name__ = "DeviceGroupEntry"

    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        icon_name: Optional[str],
        group_key: str,
    ):
        super().__init__(
            message_broker=message_broker,
            controller=controller,
            icon_name=icon_name,
            name=group_key,
        )
        self.group_key = group_key

    def _on_gtk_toggle(self, *_, **__):
        logger.debug('Selecting device "%s"', self.group_key)
        self._controller.load_group(self.group_key)
        self.message_broker.send(DoStackSwitch(Stack.presets_page))


class DeviceGroupSelection(FlowBoxWrapper):
    """A wrapper for the container with our groups.

    A group is a collection of devices.
    """

    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        flowbox: Gtk.FlowBox,
    ):
        self._message_broker = message_broker
        self._controller = controller
        self._gui = flowbox

        self._message_broker.subscribe(MessageType.groups, self._on_groups_changed)
        self._message_broker.subscribe(MessageType.group, self._on_group_changed)

    def _on_groups_changed(self, data: GroupsData):
        self._gui.foreach(lambda group: self._gui.remove(group))

        for group_key, types in data.groups.items():
            if len(types) > 0:
                device_type = sorted(types, key=ICON_PRIORITIES.index)[0]
                icon_name = ICON_NAMES[device_type]
            else:
                icon_name = None

            logger.debug(f"adding {group_key} to device selection")
            device_group_entry = DeviceGroupEntry(
                self._message_broker,
                self._controller,
                icon_name,
                group_key,
            )
            self._gui.insert(device_group_entry, -1)

    def _on_group_changed(self, data: GroupData):
        self.show_active_entry(data.group_key)
