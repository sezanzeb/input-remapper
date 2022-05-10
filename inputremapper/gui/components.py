from __future__ import annotations

from typing import List, Tuple, Optional, Dict

from gi.repository import Gtk, GtkSource, Gdk, GLib, GObject

from inputremapper.event_combination import EventCombination
from inputremapper.groups import (
    _Groups,
    GAMEPAD,
    KEYBOARD,
    UNKNOWN,
    GRAPHICS_TABLET,
    TOUCHPAD,
    MOUSE,
)
from inputremapper.gui.event_handler import EventHandler, EventEnum
from inputremapper.gui.utils import HandlerDisabled
from inputremapper.logger import logger


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


class DeviceSelection:
    def __init__(self, event_handler: EventHandler, combobox: Gtk.ComboBox):
        self.event_handler = event_handler
        self.device_store = Gtk.ListStore(str, str, str)
        self.gui = combobox

        # https://python-gtk-3-tutorial.readthedocs.io/en/latest/treeview.html#the-view
        combobox.set_model(self.device_store)
        renderer_icon = Gtk.CellRendererPixbuf()
        renderer_text = Gtk.CellRendererText()
        renderer_text.set_padding(5, 0)
        combobox.pack_start(renderer_icon, False)
        combobox.pack_start(renderer_text, False)
        combobox.add_attribute(renderer_icon, "icon-name", 1)
        combobox.add_attribute(renderer_text, "text", 2)
        combobox.set_id_column(0)

        self.attach_to_events()
        combobox.connect("changed", self.on_gtk_select_device)

    def attach_to_events(self):
        self.event_handler.subscribe(EventEnum.groups_changed, self.on_groups_changed)
        self.event_handler.subscribe(EventEnum.group_changed, self.on_group_changed)

    def on_groups_changed(self, groups: List[Tuple[str, Optional[str]]]):
        with HandlerDisabled(self.gui, self.on_gtk_select_device):
            self.device_store.clear()
            for group in groups:
                logger.debug(f"adding {group[0]} to device dropdown ")
                self.device_store.append([group[0], group[1], group[0]])

    def on_group_changed(self, group_key: str, **_):
        with HandlerDisabled(self.gui, self.on_gtk_select_device):
            self.gui.set_active_id(group_key)

    def on_gtk_select_device(self, *_, **__):
        group_key = self.gui.get_active_id()
        logger.debug('Selecting device "%s"', group_key)
        self.event_handler.emit(EventEnum.load_group, group_key=group_key)


class PresetSelection:
    def __init__(self, event_handler: EventHandler, combobox: Gtk.ComboBoxText):
        self.event_handler = event_handler
        self.gui = combobox

        self.attach_to_events()
        combobox.connect("changed", self.on_gtk_select_preset)

    def attach_to_events(self):
        self.event_handler.subscribe(EventEnum.group_changed, self.on_group_changed)
        self.event_handler.subscribe(EventEnum.preset_changed, self.on_preset_changed)

    def on_group_changed(self, group_key: str, presets: List[str]):
        with HandlerDisabled(self.gui, self.on_gtk_select_preset):
            self.gui.remove_all()
            for preset in presets:
                self.gui.append(preset, preset)

    def on_preset_changed(self, name, **_):
        with HandlerDisabled(self.gui, self.on_gtk_select_preset):
            self.gui.set_active_id(name)

    def on_gtk_select_preset(self, *_, **__):
        name = self.gui.get_active_id()
        logger.debug('Selecting preset "%s"', name)
        self.event_handler.emit(EventEnum.load_preset, name=name)


class MappingListBox:
    def __init__(self, event_handler: EventHandler, listbox: Gtk.ListBox):
        self.event_handler = event_handler
        self.gui = listbox
        self.gui.set_sort_func(self.sort_func)
        self.gui.connect("row-selected", self.on_gtk_mapping_selected)
        self.attach_to_events()

    @staticmethod
    def sort_func(row1: SelectionLabel, row2: SelectionLabel) -> int:
        """sort alphanumerical by name"""
        return 0 if row1.name < row2.name else 1

    def attach_to_events(self):
        self.event_handler.subscribe(EventEnum.preset_changed, self.on_preset_changed)

    def on_preset_changed(
        self, *, mappings: Optional[List[Tuple[str, EventCombination]]], **_
    ):
        self.gui.forall(self.gui.remove)
        if not mappings:
            return

        for name, combination in mappings:
            selection_label = SelectionLabel(self.event_handler, name, combination)
            self.gui.insert(selection_label, -1)

    def on_mapping_loaded(self, mapping: Dict):
        with HandlerDisabled(self.gui, self.on_gtk_mapping_selected):
            if not mapping:
                self.gui.do_unselect_all()
                return

            combination = mapping["combination"]

            def set_active(row: SelectionLabel):
                if row.combination == combination:
                    self.gui.select_row(row)

            self.gui.foreach(set_active)

    def on_gtk_mapping_selected(self, _, row: SelectionLabel):
        self.event_handler.emit(EventEnum.load_mapping, combination=row.combination)


class SelectionLabel(Gtk.ListBoxRow):

    __gtype_name__ = "SelectionLabel"

    def __init__(
        self,
        event_handler: EventHandler,
        name: Optional[str],
        combination: EventCombination,
    ):
        super().__init__()
        self.event_handler = event_handler
        self.combination = combination
        self._name = name

        self.label = Gtk.Label()
        # Make the child label widget break lines, important for
        # long combinations
        self.label.set_line_wrap(True)
        self.label.set_line_wrap_mode(Gtk.WrapMode.WORD)
        self.label.set_justify(Gtk.Justification.CENTER)
        # set the name or combination.beautify as label
        self.label.set_label(self.name)
        self.add(self.label)

        self.attach_to_events()
        self.show_all()

    def __repr__(self):
        return f"SelectionLabel for {self.combination} as {self.name}"

    @property
    def name(self) -> str:
        return self._name or self.combination.beautify()

    def attach_to_events(self):
        self.event_handler.subscribe(EventEnum.mapping_changed, self.on_mapping_changed)

    def on_mapping_changed(self, mapping: Dict):
        if not self.is_selected():
            return

        self._name = mapping["name"]
        self.combination = mapping["combination"]
