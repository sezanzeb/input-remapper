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


"""All components that are visible on the page that shows all the presets."""


from __future__ import annotations

from gi.repository import Gtk

from inputremapper.gui.components.common import FlowBoxEntry, FlowBoxWrapper
from inputremapper.gui.components.main import Stack
from inputremapper.gui.controller import Controller
from inputremapper.gui.messages.message_broker import (
    MessageBroker,
    MessageType,
)
from inputremapper.gui.messages.message_data import (
    GroupData,
    PresetData,
    DoStackSwitch,
)
from inputremapper.logger import logger


class PresetEntry(FlowBoxEntry):
    """A preset that can be selected in the GUI."""

    __gtype_name__ = "PresetEntry"

    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        preset_name: str,
    ):
        super().__init__(
            message_broker=message_broker, controller=controller, name=preset_name
        )
        self.preset_name = preset_name

    def _on_gtk_toggle(self, *_, **__):
        logger.debug('Selecting preset "%s"', self.preset_name)
        self._controller.load_preset(self.preset_name)
        self.message_broker.send(DoStackSwitch(Stack.editor_page))


class PresetSelection(FlowBoxWrapper):
    """A wrapper for the container with our presets.

    Selectes the active_preset.
    """

    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        flowbox: Gtk.FlowBox,
    ):
        super().__init__(flowbox)

        self._message_broker = message_broker
        self._controller = controller
        self._gui = flowbox
        self._connect_message_listener()

    def _connect_message_listener(self):
        self._message_broker.subscribe(MessageType.group, self._on_group_changed)
        self._message_broker.subscribe(MessageType.preset, self._on_preset_changed)

    def _on_group_changed(self, data: GroupData):
        self._gui.foreach(lambda preset: self._gui.remove(preset))
        for preset_name in data.presets:
            preset_entry = PresetEntry(
                self._message_broker,
                self._controller,
                preset_name,
            )
            self._gui.insert(preset_entry, -1)

    def _on_preset_changed(self, data: PresetData):
        self.show_active_entry(data.name)

    def set_active_preset(self, preset_name: str):
        """Change the currently selected preset."""
        # TODO might only be needed in tests
        for child in self._gui.get_children():
            preset_entry: PresetEntry = child.get_children()[0]
            preset_entry.set_active(preset_entry.preset_name == preset_name)
