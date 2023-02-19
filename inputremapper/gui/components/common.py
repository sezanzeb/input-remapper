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

from gi.repository import Gtk

from typing import (
    Optional,
    Iterator,
)

from inputremapper.configs.mapping import MappingData

from inputremapper.gui.controller import Controller
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


class ListFilterControl:
    """Implements UI-side filtering of list widgets.

    The following example creates a new ``ListFilterControl`` for a given
    ``Gtk.ListBox`` and a given ``Gtk.Entry`` for text input. It also sets all
    optional arguments to override some default behavior.

    >>> ListFilterControl(
    >>>     my_gtk_listbox,
    >>>     my_gtk_entry,
    >>>     clear_button=my_gtk_button,  # use an optional clear button
    >>>     case_sensitive=True,         # change default behavior
    >>>     get_row_name=MyRow.get_name  # custom row name getter
    >>> )

    """

    MAX_WIDGET_TREE_TEXT_SEARCH_DEPTH = 10

    def __init__(
        self,
        # message_broker: MessageBroker,
        controlled_listbox: Gtk.ListBox,
        filter_entry: Gtk.GtkEntry,
        clear_button: Gtk.Button = None,
        case_sensitive=False,
        get_row_name=None,
    ):
        self._controlled_listbox: Gtk.ListBox = controlled_listbox
        self._filter_entry: Gtk.Entry = filter_entry
        self._clear_button: Gtk.Button = clear_button

        self._filter_value: str = ""
        self._case_sensitive: bool = bool(case_sensitive)
        self._get_row_name = get_row_name or self.get_row_name

        self._connect_gtk_signals()

    @classmethod
    def get_row_name(T, row: Gtk.ListBoxRow) -> str:
        """
        Returns the visible text of a Gtk.ListBoxRow from both the row's `name`
        attribute or the row's text in the UI.
        """
        text = getattr(row, "name", "")

        # find and join all text in the ListBoxRow
        text += " ".join(v for v in T.get_widget_tree_text(row) if v != "")

        return text.strip()

    @classmethod
    def get_widget_tree_text(T, widget: Gtk.Widget, level=0) -> Iterator[str]:
        """
        Recursively traverses the tree of child widgets starting from the given
        widget, and yields the text of all text-containing widgets.
        """
        if level > T.MAX_WIDGET_TREE_TEXT_SEARCH_DEPTH:
            return

        if hasattr(widget, "get_label"):
            yield (widget.get_label() or "").strip()
        if hasattr(widget, "get_text"):
            yield (widget.get_text() or "").strip()
        if isinstance(widget, Gtk.Container):
            for t in widget.get_children():
                yield from T.get_widget_tree_text(t, level=level + 1)

    def _connect_gtk_signals(self):
        if self._clear_button:
            self._clear_button.connect("clicked", self.on_gtk_clear_button_clicked)
        self._filter_entry.connect("key-release-event", self.on_gtk_filter_entry_input)

    # apply defined filter by sending out the corresponding events
    def apply_filter(self):
        self._apply_filter_to_listbox_children()

    # matches the current filter_value and filter_options with the given value
    def match_filter(self, value: str):
        value = (value or "").strip()

        # if filter is not set, all rows need to match
        if self._filter_value == "":
            return True

        print(f"matching filter: {self._filter_value} with value: {value}")

        if self._case_sensitive:
            return self._filter_value in value
        else:
            return self._filter_value.lower() in value.lower()

    def _apply_filter_to_listbox_children(self):
        value = self._filter_value.lower()
        selected: Gtk.ListBoxRow = None
        row: Gtk.ListBoxRow = None
        for row in self._controlled_listbox.get_children():
            if self.match_filter(self._get_row_name(row)):
                # show matching rows, then select the first row
                row.show()
                if selected is None:
                    selected = row
                    self._controlled_listbox.select_row(selected)
            else:
                # hide non-matching rows
                row.hide()

    def on_gtk_filter_entry_input(self, _, event: Gdk.EventKey):
        self._filter_value = (self._filter_entry.get_text() or "").strip()
        self.apply_filter()

    def on_gtk_clear_button_clicked(self, *_):
        self._filter_entry.set_text("")
        self._filter_value = ""
        self.apply_filter()
