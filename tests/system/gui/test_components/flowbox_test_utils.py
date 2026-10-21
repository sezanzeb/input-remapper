# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2026 sezanzeb <4t1pzast9@mozmail.com>
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


import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GLib", "2.0")
gi.require_version("GtkSource", "4")
from gi.repository import Gtk

from inputremapper.gui.components.common import FlowBoxEntry
from inputremapper.gui.components.device_groups import (
    DeviceGroupEntry,
)


class FlowBoxTestUtils:
    """Methods to test the FlowBoxes that contain presets and devices.

    Those are only used in tests, so I moved them here instead.
    """

    @staticmethod
    def set_active(flow_box: Gtk.FlowBox, name: str):
        """Change the currently selected group."""
        for child in flow_box.get_children():
            flow_box_entry: FlowBoxEntry = child.get_children()[0]
            flow_box_entry.set_active(flow_box_entry.name == name)

    @staticmethod
    def get_active_entry(flow_box: Gtk.FlowBox) -> DeviceGroupEntry | None:
        """Find the currently selected DeviceGroupEntry."""
        children = flow_box.get_children()

        if len(children) == 0:
            return None

        for child in children:
            flow_box_entry: FlowBoxEntry = child.get_children()[0]

            if flow_box_entry.get_active():
                return flow_box_entry

        raise AssertionError("Expected one entry to be selected.")

    @staticmethod
    def get_child_names(flow_box: Gtk.FlowBox):
        names = []
        for child in flow_box.get_children():
            flow_box_entry: FlowBoxEntry = child.get_children()[0]
            names.append(flow_box_entry.name)

        return names

    @staticmethod
    def get_child_icons(flow_box: Gtk.FlowBox):
        icon_names = []
        for child in flow_box.get_children():
            flow_box_entry: FlowBoxEntry = child.get_children()[0]
            icon_names.append(flow_box_entry.icon_name)

        return icon_names
