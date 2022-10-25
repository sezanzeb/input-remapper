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


"""Components used in multiple places."""


from __future__ import annotations

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from typing import Optional

from inputremapper.configs.mapping import MappingData
from inputremapper.event_combination import EventCombination

from inputremapper.gui.controller import Controller
from inputremapper.gui.gettext import _
from inputremapper.gui.messages.message_broker import (
    MessageBroker,
    MessageType,
)
from inputremapper.gui.messages.message_data import GroupData, PresetData
from inputremapper.gui.utils import HandlerDisabled


class FlowBoxEntry(Gtk.ToggleButton):
    """A device that can be selected in the GUI.

    For example a keyboard or a mouse.
    """

    __gtype_name__ = "FlowBoxEntry"

    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        name: str,
        icon_name: Optional[str] = None,
    ):
        super().__init__()
        self.icon_name = icon_name
        self.message_broker = message_broker
        self._controller = controller

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        if icon_name:
            icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.DIALOG)
            box.add(icon)

        label = Gtk.Label()
        label.set_label(name)
        self.name = name

        # wrap very long names properly
        label.set_line_wrap(True)
        label.set_line_wrap_mode(2)
        # this affeects how many device entries fit next to each other
        label.set_width_chars(28)
        label.set_max_width_chars(28)

        box.add(label)

        box.set_margin_top(18)
        box.set_margin_bottom(18)
        box.set_homogeneous(True)
        box.set_spacing(12)

        # self.set_relief(Gtk.ReliefStyle.NONE)

        self.add(box)

        self.show_all()

        self.connect("toggled", self._on_gtk_toggle)

    def _on_gtk_toggle(self):
        raise NotImplementedError

    def show_active(self, active):
        """Show the active state without triggering anything."""
        with HandlerDisabled(self, self._on_gtk_toggle):
            self.set_active(active)


class FlowBoxWrapper:
    """A wrapper for a flowbox that contains FlowBoxEntry widgets."""

    def __init__(self, flowbox: Gtk.FlowBox):
        self._gui = flowbox

    def show_active_entry(self, name: Optional[str]):
        """Activate the togglebutton that matches the name."""
        for child in self._gui.get_children():
            flow_box_entry: FlowBoxEntry = child.get_children()[0]
            flow_box_entry.show_active(flow_box_entry.name == name)


class Breadcrumbs:
    """Writes a breadcrumbs string into a given label."""

    def __init__(
        self,
        message_broker: MessageBroker,
        label: Gtk.Label,
        show_device_group: bool = False,
        show_preset: bool = False,
        show_mapping: bool = False,
    ):
        self._message_broker = message_broker
        self._gui = label
        self._connect_message_listener()

        self.show_device_group = show_device_group
        self.show_preset = show_preset
        self.show_mapping = show_mapping

        self._group_key: str = ""
        self._preset_name: str = ""
        self._mapping_name: str = ""

        label.set_max_width_chars(50)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(2)

        self._render()

    def _connect_message_listener(self):
        self._message_broker.subscribe(MessageType.group, self._on_group_changed)
        self._message_broker.subscribe(MessageType.preset, self._on_preset_changed)
        self._message_broker.subscribe(MessageType.mapping, self._on_mapping_changed)

    def _on_preset_changed(self, data: PresetData):
        self._preset_name = data.name or ""
        self._render()

    def _on_group_changed(self, data: GroupData):
        self._group_key = data.group_key
        self._render()

    def _on_mapping_changed(self, mapping_data: MappingData):
        self._mapping_name = mapping_data.format_name()
        self._render()

    def _render(self):
        label = []

        if self.show_device_group:
            label.append(self._group_key or "?")

        if self.show_preset:
            label.append(self._preset_name or "?")

        if self.show_mapping:
            label.append(self._mapping_name or "?")

        self._gui.set_label("  /  ".join(label))
