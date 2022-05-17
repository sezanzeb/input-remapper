from __future__ import annotations

from typing import List, Tuple, Optional, Dict, Any

from gi.repository import Gtk, GtkSource, Gdk, GLib, GObject

from inputremapper.configs.system_mapping import SystemMapping
from inputremapper.event_combination import EventCombination
from inputremapper.groups import (
    GAMEPAD,
    KEYBOARD,
    UNKNOWN,
    GRAPHICS_TABLET,
    TOUCHPAD,
    MOUSE,
)
from inputremapper.gui.gettext import _
from inputremapper.gui.event_handler import EventHandler, EventEnum
from inputremapper.gui.utils import HandlerDisabled
from inputremapper.injection.global_uinputs import FrontendUInput
from inputremapper.logger import logger


Capabilities = Dict[int, List]

SET_KEY_FIRST = _("Set the key first")

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

    def on_groups_changed(self, groups: List[Tuple[str, List[str]]]):
        with HandlerDisabled(self.gui, self.on_gtk_select_device):
            self.device_store.clear()
            for group_key, types in groups:
                if len(types) > 0:
                    device_type = sorted(types, key=ICON_PRIORITIES.index)[0]
                    icon_name = ICON_NAMES[device_type]
                else:
                    icon_name = None

                logger.debug(f"adding {group_key} to device dropdown ")
                self.device_store.append([group_key, icon_name, group_key])

    def on_group_changed(self, group_key: str, **_):
        with HandlerDisabled(self.gui, self.on_gtk_select_device):
            self.gui.set_active_id(group_key)

    def on_gtk_select_device(self, *_, **__):
        group_key = self.gui.get_active_id()
        logger.debug('Selecting device "%s"', group_key)
        self.event_handler.emit(EventEnum.load_group, group_key=group_key)


class TargetSelection:
    def __init__(self, event_handler: EventHandler, combobox: Gtk.ComboBox):
        self.event_handler = event_handler
        self.gui = combobox

        self.attach_to_events()
        self.gui.connect("changed", self.on_gtk_target_selected)

    def attach_to_events(self):
        self.event_handler.subscribe(EventEnum.uinputs_changed, self.on_uinputs_changed)
        self.event_handler.subscribe(EventEnum.mapping_loaded, self.on_mapping_loaded)
        self.event_handler.subscribe(EventEnum.mapping_changed, self.on_mapping_changed)

    def on_uinputs_changed(self, uinputs: Dict[str, Capabilities]):
        logger.error("got uinputs")
        target_store = Gtk.ListStore(str)
        for uinput in uinputs.keys():
            target_store.append([uinput])

        self.gui.set_model(target_store)
        renderer_text = Gtk.CellRendererText()
        self.gui.pack_start(renderer_text, False)
        self.gui.add_attribute(renderer_text, "text", 0)
        self.gui.set_id_column(0)

    def on_mapping_loaded(self, mapping: Dict[str, Any]):
        if mapping:
            target = mapping["target_uinput"]
            self.enable()
        else:
            target = "keyboard"
            self.disable()

        with HandlerDisabled(self.gui, self.on_gtk_target_selected):
            self.gui.set_active_id(target)

    def on_mapping_changed(self, target_uinput=None, **_):
        if not target_uinput:
            return
        with HandlerDisabled(self.gui, self.on_gtk_target_selected):
            self.gui.set_active_id(target_uinput)

    def enable(self):
        self.gui.set_sensitive(True)
        self.gui.set_opacity(1)

    def disable(self):
        self.gui.set_sensitive(False)
        self.gui.set_opacity(0.5)

    def on_gtk_target_selected(self, *_):
        target = self.gui.get_active_id()
        self.event_handler.emit(EventEnum.update_mapping, target_uinput=target)


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
        self.event_handler.emit(
            EventEnum.load_mapping, event_combination=row.combination
        )


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
        self.combination = mapping["event_combination"]


class CodeEditor:
    def __init__(
        self,
        event_handler: EventHandler,
        system_mapping: SystemMapping,
        editor: GtkSource.View,
    ):
        self.evnet_handler = event_handler
        self.system_mapping = system_mapping
        self.gui = editor

        # without this the wrapping ScrolledWindow acts weird when new lines are added,
        # not offering enough space to the text editor so the whole thing is suddenly
        # scrollable by a few pixels.
        # Found this after making blind guesses with settings in glade, and then
        # actually looking at the snaphot preview! In glades editor this didn have an
        # effect.
        self.gui.set_resize_mode(Gtk.ResizeMode.IMMEDIATE)
        # Syntax Highlighting
        # Thanks to https://github.com/wolfthefallen/py-GtkSourceCompletion-example
        # language_manager = GtkSource.LanguageManager()
        # fun fact: without saving LanguageManager into its own variable it doesn't work
        #  python = language_manager.get_language("python")
        # source_view.get_buffer().set_language(python)
        # TODO there are some similarities with python, but overall it's quite useless.
        #  commented out until there is proper highlighting for input-remappers syntax.

        # todo: setup autocompletion here

        self.gui.connect("focus-out-event", self.on_gtk_focus_out)
        self.gui.get_buffer().connect("changed", self.on_gtk_changed)
        self.attach_to_events()

    @property
    def code(self) -> str:
        buffer = self.gui.get_buffer()
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)

    @code.setter
    def code(self, code: str) -> None:
        if code == self.code:
            return

        buffer = self.gui.get_buffer()
        with HandlerDisabled(buffer, self.on_gtk_changed):
            buffer.set_text(code)
            self.gui.do_move_cursor(self.gui, Gtk.MovementStep.BUFFER_ENDS, -1, False)

    def attach_to_events(self):
        self.evnet_handler.subscribe(EventEnum.mapping_loaded, self.on_mapping_loaded)
        self.evnet_handler.subscribe(EventEnum.mapping_changed, self.on_mapping_changed)

    def toggle_line_numbers(self):
        """Show line numbers if multiline, otherwise remove them"""
        if "\n" in self.code:
            self.gui.set_show_line_numbers(True)
            self.gui.set_monospace(True)
            self.gui.get_style_context().add_class("multiline")
        else:
            self.gui.set_show_line_numbers(False)
            self.gui.set_monospace(False)
            self.gui.get_style_context().remove_class("multiline")

    def enable(self):
        logger.debug("Enabling the code editor")
        self.gui.set_sensitive(True)
        self.gui.set_opacity(1)

        if self.code == SET_KEY_FIRST:
            # don't overwrite user input
            self.code = ""

    def disable(self):
        logger.debug("Disabling the code editor")

        # beware that this also appeared to disable event listeners like
        # focus-out-event:
        self.gui.set_sensitive(False)
        self.gui.set_opacity(0.5)

        if self.code == "":
            # don't overwrite user input
            self.code = SET_KEY_FIRST

    def on_gtk_focus_out(self, *_):
        self.evnet_handler.emit(EventEnum.save)

    def on_gtk_changed(self, *_):
        code = self.system_mapping.correct_case(self.code)
        self.evnet_handler.emit(EventEnum.update_mapping, output_symbol=code)

    def on_mapping_loaded(self, mapping=None):
        code = ""
        if mapping and mapping["output_symbol"]:
            code = mapping["output_symbol"]
        self.code = code
        if mapping:
            self.enable()
        else:
            self.disable()
        self.toggle_line_numbers()

    def on_mapping_changed(self, mapping):
        self.on_mapping_loaded(mapping)