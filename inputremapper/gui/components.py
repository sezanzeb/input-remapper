from __future__ import annotations

from typing import List, Tuple, Optional, Dict, Any

from gi.repository import Gtk, GtkSource, Gdk, GLib, GObject

from inputremapper.configs.mapping import MappingData
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
from inputremapper.gui.controller import Controller
from inputremapper.gui.gettext import _
from inputremapper.gui.data_bus import (
    DataBus,
    MessageType,
    GroupsData,
    GroupData,
    UInputsData,
    PresetData,
    CombinationRecorded,
)
from inputremapper.gui.utils import HandlerDisabled
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
    def __init__(
        self, data_bus: DataBus, controller: Controller, combobox: Gtk.ComboBox
    ):
        self.data_bus = data_bus
        self.controller = controller
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
        self.data_bus.subscribe(MessageType.groups, self.on_groups_changed)
        self.data_bus.subscribe(MessageType.group, self.on_group_changed)

    def on_groups_changed(self, data: GroupsData):
        with HandlerDisabled(self.gui, self.on_gtk_select_device):
            self.device_store.clear()
            for group_key, types in data.groups.items():
                if len(types) > 0:
                    device_type = sorted(types, key=ICON_PRIORITIES.index)[0]
                    icon_name = ICON_NAMES[device_type]
                else:
                    icon_name = None

                logger.debug(f"adding {group_key} to device dropdown ")
                self.device_store.append([group_key, icon_name, group_key])

    def on_group_changed(self, data: GroupData):
        with HandlerDisabled(self.gui, self.on_gtk_select_device):
            self.gui.set_active_id(data.group_key)

    def on_gtk_select_device(self, *_, **__):
        group_key = self.gui.get_active_id()
        logger.debug('Selecting device "%s"', group_key)
        self.controller.load_group(group_key)


class TargetSelection:
    def __init__(
        self, data_bus: DataBus, controller: Controller, combobox: Gtk.ComboBox
    ):
        self.data_bus = data_bus
        self.controller = controller
        self.gui = combobox

        self.attach_to_events()
        self.gui.connect("changed", self.on_gtk_target_selected)

    def attach_to_events(self):
        self.data_bus.subscribe(MessageType.uinputs, self.on_uinputs_changed)
        self.data_bus.subscribe(MessageType.mapping, self.on_mapping_loaded)

    def on_uinputs_changed(self, data: UInputsData):
        target_store = Gtk.ListStore(str)
        for uinput in data.uinputs.keys():
            target_store.append([uinput])

        self.gui.set_model(target_store)
        renderer_text = Gtk.CellRendererText()
        self.gui.pack_start(renderer_text, False)
        self.gui.add_attribute(renderer_text, "text", 0)
        self.gui.set_id_column(0)

    def on_mapping_loaded(self, mapping: MappingData):
        if not mapping.is_default():
            self.enable()
        else:
            self.disable()

        with HandlerDisabled(self.gui, self.on_gtk_target_selected):
            self.gui.set_active_id(mapping.target_uinput or "keyboard")

    def enable(self):
        self.gui.set_sensitive(True)
        self.gui.set_opacity(1)

    def disable(self):
        self.gui.set_sensitive(False)
        self.gui.set_opacity(0.5)

    def on_gtk_target_selected(self, *_):
        target = self.gui.get_active_id()
        self.controller.update_mapping(target_uinput=target)


class PresetSelection:
    def __init__(
        self, data_bus: DataBus, controller: Controller, combobox: Gtk.ComboBoxText
    ):
        self.data_bus = data_bus
        self.controller = controller
        self.gui = combobox

        self.attach_to_events()
        combobox.connect("changed", self.on_gtk_select_preset)

    def attach_to_events(self):
        self.data_bus.subscribe(MessageType.group, self.on_group_changed)
        self.data_bus.subscribe(MessageType.preset, self.on_preset_changed)

    def on_group_changed(self, data: GroupData):
        with HandlerDisabled(self.gui, self.on_gtk_select_preset):
            self.gui.remove_all()
            for preset in data.presets:
                self.gui.append(preset, preset)

    def on_preset_changed(self, data: PresetData):
        with HandlerDisabled(self.gui, self.on_gtk_select_preset):
            self.gui.set_active_id(data.name)

    def on_gtk_select_preset(self, *_, **__):
        name = self.gui.get_active_id()
        logger.debug('Selecting preset "%s"', name)
        self.controller.load_preset(name)


class MappingListBox:
    def __init__(self, data_bus: DataBus, controller: Controller, listbox: Gtk.ListBox):
        self.data_bus = data_bus
        self.controller = controller
        self.gui = listbox
        self.gui.set_sort_func(self.sort_func)
        self.gui.connect("row-selected", self.on_gtk_mapping_selected)
        self.attach_to_events()

    @staticmethod
    def sort_func(row1: SelectionLabel, row2: SelectionLabel) -> int:
        """sort alphanumerical by name"""
        return 0 if row1.name < row2.name else 1

    def attach_to_events(self):
        self.data_bus.subscribe(MessageType.preset, self.on_preset_changed)
        self.data_bus.subscribe(MessageType.mapping, self.on_mapping_loaded)

    def on_preset_changed(self, data: PresetData):
        self.gui.forall(self.gui.remove)
        if not data.mappings:
            return

        for name, combination in data.mappings:
            selection_label = SelectionLabel(
                self.data_bus, self.controller, name, combination
            )
            self.gui.insert(selection_label, -1)

    def on_mapping_loaded(self, mapping: MappingData):
        with HandlerDisabled(self.gui, self.on_gtk_mapping_selected):
            if mapping.is_default():
                self.gui.do_unselect_all(self.gui)
                return

            combination = mapping.event_combination

            def set_active(row: SelectionLabel):
                if row.combination == combination:
                    self.gui.select_row(row)

            self.gui.foreach(set_active)

    def on_gtk_mapping_selected(self, _, row: SelectionLabel):
        self.controller.load_mapping(row.combination)


class SelectionLabel(Gtk.ListBoxRow):

    __gtype_name__ = "SelectionLabel"

    def __init__(
        self,
        data_bus: DataBus,
        controller: Controller,
        name: Optional[str],
        combination: EventCombination,
    ):
        super().__init__()
        self.data_bus = data_bus
        self.controller = controller
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
        self.data_bus.subscribe(MessageType.mapping, self.on_mapping_changed)

    def on_mapping_changed(self, mapping: MappingData):
        if not self.is_selected():
            return
        self._name = mapping.name
        self.combination = mapping.event_combination
        self.label.set_label(self.name)


class CodeEditor:
    def __init__(
        self,
        data_bus: DataBus,
        controller: Controller,
        system_mapping: SystemMapping,
        editor: GtkSource.View,
    ):
        self.data_bus = data_bus
        self.controller = controller
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
        self.data_bus.subscribe(MessageType.mapping, self.on_mapping_loaded)

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
        self.controller.save()

    def on_gtk_changed(self, *_):
        code = self.system_mapping.correct_case(self.code)
        self.controller.update_mapping(output_symbol=code)

    def on_mapping_loaded(self, mapping: MappingData):
        code = ""
        if not mapping.is_default():
            code = mapping.output_symbol
            self.enable()
        else:
            self.disable()

        self.code = code
        self.toggle_line_numbers()


class RecordingToggle:
    def __init__(
        self, data_bus: DataBus, controller: Controller, toggle: Gtk.ToggleButton
    ):
        self.data_bus = data_bus
        self.controller = controller
        self.gui = toggle
        toggle.connect(
            "focus-out-event", lambda *__: self.update_label(_("Record Keys"))
        )
        toggle.connect(
            "focus-in-event", lambda *__: self.update_label(_("Recording Keys"))
        )

        # toggle.connect("focus-out-event", self._reset_keycode_consumption)
        # toggle.connect("focus-out-event", lambda *_: self.gui.set_active(False))
        toggle.connect("toggled", self.on_gtk_toggle)
        # Don't leave the input when using arrow keys or tab. wait for the
        # window to consume the keycode from the reader. I.e. a tab input should
        # be recorded, instead of causing the recording to stop.
        toggle.connect("key-press-event", lambda *args: Gdk.EVENT_STOP)

        self.attach_to_events()

    def attach_to_events(self):
        self.data_bus.subscribe(
            MessageType.combination_recorded, self.on_combination_recorded
        )
        self.data_bus.subscribe(
            MessageType.recording_finished, self.on_recording_finished
        )

    def update_label(self, msg: str):
        self.gui.set_label(msg)

    def on_gtk_toggle(self, *__):
        if self.gui.get_active():
            self.controller.start_key_recording()
            self.update_label(_("Recording ..."))
        else:
            self.update_label(_("Record Keys"))

    def on_recording_finished(self, _):
        logger.debug("finished recording")
        self.gui.set_active(False)

    def on_combination_recorded(self, data: CombinationRecorded):
        if not self.gui.get_active():
            return

        self.controller.update_combination(data.combination)

