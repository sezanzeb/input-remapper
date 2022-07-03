from __future__ import annotations

from collections import defaultdict
from typing import List, Optional, Dict, Literal, Union, Tuple, Callable

import cairo
from evdev.ecodes import EV_KEY, EV_ABS, EV_REL, bytype
from gi.repository import Gtk, GtkSource, Gdk

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
from inputremapper.gui.message_broker import (
    MessageBroker,
    MessageType,
    GroupsData,
    GroupData,
    UInputsData,
    PresetData,
    StatusData,
    CombinationUpdate,
    UserConfirmRequest,
)
from inputremapper.gui.utils import HandlerDisabled, CTX_ERROR, CTX_MAPPING, CTX_WARNING
from inputremapper.injection.mapping_handlers.axis_transform import Transformation
from inputremapper.input_event import InputEvent
from inputremapper.logger import logger

Capabilities = Dict[int, List]

SET_KEY_FIRST = _("Record the input first")
EMPTY_MAPPING_NAME = _("Empty Mapping")

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
        self,
        message_broker: MessageBroker,
        controller: Controller,
        combobox: Gtk.ComboBox,
    ):
        self.message_broker = message_broker
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

        self._connect_message_listener()
        combobox.connect("changed", self.on_gtk_select_device)

    def _connect_message_listener(self):
        self.message_broker.subscribe(MessageType.groups, self.on_groups_changed)
        self.message_broker.subscribe(MessageType.group, self.on_group_changed)

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
        self,
        message_broker: MessageBroker,
        controller: Controller,
        combobox: Gtk.ComboBox,
    ):
        self.message_broker = message_broker
        self.controller = controller
        self.gui = combobox

        self._connect_message_listener()
        self.gui.connect("changed", self.on_gtk_target_selected)

    def _connect_message_listener(self):
        self.message_broker.subscribe(MessageType.uinputs, self.on_uinputs_changed)
        self.message_broker.subscribe(MessageType.mapping, self.on_mapping_loaded)

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
        if not self.controller.is_empty_mapping():
            self.enable()
        else:
            self.disable()

        with HandlerDisabled(self.gui, self.on_gtk_target_selected):
            self.gui.set_active_id(mapping.target_uinput)

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
        self,
        message_broker: MessageBroker,
        controller: Controller,
        combobox: Gtk.ComboBoxText,
    ):
        self.message_broker = message_broker
        self.controller = controller
        self.gui = combobox

        self._connect_message_listener()
        combobox.connect("changed", self.on_gtk_select_preset)

    def _connect_message_listener(self):
        self.message_broker.subscribe(MessageType.group, self.on_group_changed)
        self.message_broker.subscribe(MessageType.preset, self.on_preset_changed)

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
    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        listbox: Gtk.ListBox,
    ):
        self.message_broker = message_broker
        self.controller = controller
        self.gui = listbox
        self.gui.set_sort_func(self.sort_func)
        self.gui.connect("row-selected", self.on_gtk_mapping_selected)
        self._connect_message_listener()

    @staticmethod
    def sort_func(row1: SelectionLabel, row2: SelectionLabel) -> int:
        """sort alphanumerical by name"""
        if row1.combination == EventCombination.empty_combination():
            return 1
        if row2.combination == EventCombination.empty_combination():
            return 0

        return 0 if row1.name < row2.name else 1

    def _connect_message_listener(self):
        self.message_broker.subscribe(MessageType.preset, self.on_preset_changed)
        self.message_broker.subscribe(MessageType.mapping, self.on_mapping_changed)

    def on_preset_changed(self, data: PresetData):
        self.gui.foreach(lambda label: (label.cleanup(), self.gui.remove(label)))
        if not data.mappings:
            return

        for name, combination in data.mappings:
            selection_label = SelectionLabel(
                self.message_broker, self.controller, name, combination
            )
            self.gui.insert(selection_label, -1)
        self.gui.invalidate_sort()

    def on_mapping_changed(self, mapping: MappingData):
        with HandlerDisabled(self.gui, self.on_gtk_mapping_selected):
            combination = mapping.event_combination

            def set_active(row: SelectionLabel):
                if row.combination == combination:
                    self.gui.select_row(row)

            self.gui.foreach(set_active)

    def on_gtk_mapping_selected(self, _, row: Optional[SelectionLabel]):
        if not row:
            return
        self.controller.load_mapping(row.combination)


class SelectionLabel(Gtk.ListBoxRow):

    __gtype_name__ = "SelectionLabel"

    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        name: Optional[str],
        combination: EventCombination,
    ):
        super().__init__()
        self.message_broker = message_broker
        self.controller = controller
        self.combination = combination
        self._name = name

        # Make the child label widget break lines, important for
        # long combinations
        self.label = Gtk.Label()
        self.label.set_line_wrap(True)
        self.label.set_line_wrap_mode(Gtk.WrapMode.WORD)
        self.label.set_justify(Gtk.Justification.CENTER)
        # set the name or combination.beautify as label
        self.label.set_label(self.name)

        # button to edit the name of the mapping
        self.edit_btn = Gtk.Button()
        self.edit_btn.set_relief(Gtk.ReliefStyle.NONE)
        self.edit_btn.set_image(
            Gtk.Image.new_from_stock(Gtk.STOCK_EDIT, Gtk.IconSize.MENU)
        )
        self.edit_btn.set_tooltip_text(_("Change Mapping Name"))
        self.edit_btn.set_margin_top(4)
        self.edit_btn.set_margin_bottom(4)
        self.edit_btn.connect("clicked", self._set_edit_mode)

        self.name_input = Gtk.Entry()
        self.name_input.set_text(self.name)
        self.name_input.set_width_chars(12)
        self.name_input.set_margin_top(4)
        self.name_input.set_margin_bottom(4)
        self.name_input.connect("activate", self.on_gtk_rename_finished)

        self.box = Gtk.Box(Gtk.Orientation.HORIZONTAL)
        self.box.set_center_widget(self.label)
        self.box.add(self.edit_btn)
        self.box.set_child_packing(self.edit_btn, False, False, 4, Gtk.PackType.END)
        self.box.add(self.name_input)
        self.box.set_child_packing(self.name_input, False, True, 4, Gtk.PackType.START)

        self.add(self.box)
        self._connect_message_listener()
        self.show_all()

        self.edit_btn.hide()
        self.name_input.hide()

    def __repr__(self):
        return f"SelectionLabel for {self.combination} as {self.name}"

    @property
    def name(self) -> str:
        if (
            self.combination == EventCombination.empty_combination()
            or self.combination is None
        ):
            return EMPTY_MAPPING_NAME
        return self._name or self.combination.beautify()

    def _connect_message_listener(self):
        self.message_broker.subscribe(MessageType.mapping, self.on_mapping_changed)
        self.message_broker.subscribe(
            MessageType.combination_update, self.on_combination_update
        )

    def _set_not_selected(self):
        self.edit_btn.hide()
        self.name_input.hide()
        self.label.show()

    def _set_selected(self):
        self.label.set_label(self.name)
        self.edit_btn.show()
        self.name_input.hide()
        self.label.show()

    def _set_edit_mode(self, *_):
        self.name_input.set_text(self.name)
        self.label.hide()
        self.name_input.show()
        self.controller.set_focus(self.name_input)

    def on_mapping_changed(self, mapping: MappingData):
        if mapping.event_combination != self.combination:
            self._set_not_selected()
            return
        self._name = mapping.name
        self._set_selected()
        self.get_parent().invalidate_sort()

    def on_combination_update(self, data: CombinationUpdate):
        if data.old_combination == self.combination and self.is_selected():
            self.combination = data.new_combination

    def on_gtk_rename_finished(self, *_):
        name = self.name_input.get_text()
        if name.lower().strip() == self.combination.beautify().lower():
            name = ""
        self._name = name
        self._set_selected()
        self.controller.update_mapping(name=name)

    def cleanup(self) -> None:
        """clean up message listeners. Execute before removing from gui!"""
        self.message_broker.unsubscribe(self.on_mapping_changed)
        self.message_broker.unsubscribe(self.on_combination_update)


class CodeEditor:
    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        system_mapping: SystemMapping,
        editor: GtkSource.View,
    ):
        self.message_broker = message_broker
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
        self._connect_message_listener()

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

    def _connect_message_listener(self):
        self.message_broker.subscribe(MessageType.mapping, self.on_mapping_loaded)
        self.message_broker.subscribe(
            MessageType.recording_finished, self.on_recording_finished
        )

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

    def disable(self):
        logger.debug("Disabling the code editor")

        # beware that this also appeared to disable event listeners like
        # focus-out-event:
        self.gui.set_sensitive(False)
        self.gui.set_opacity(0.5)

    def on_gtk_focus_out(self, *_):
        self.controller.save()

    def on_gtk_changed(self, *_):
        code = self.system_mapping.correct_case(self.code)
        self.controller.update_mapping(output_symbol=code)

    def on_mapping_loaded(self, mapping: MappingData):
        code = SET_KEY_FIRST
        if not self.controller.is_empty_mapping():
            code = mapping.output_symbol or ""
            self.enable()
        else:
            self.disable()

        if self.code.strip().lower() != code.strip().lower():
            self.code = code
        self.toggle_line_numbers()

    def on_recording_finished(self, _):
        self.controller.set_focus(self.gui)


class RecordingToggle:
    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        toggle: Gtk.ToggleButton,
    ):
        self.message_broker = message_broker
        self.controller = controller
        self.gui = toggle

        toggle.connect("toggled", self.on_gtk_toggle)
        # Don't leave the input when using arrow keys or tab. wait for the
        # window to consume the keycode from the reader. I.e. a tab input should
        # be recorded, instead of causing the recording to stop.
        toggle.connect("key-press-event", lambda *args: Gdk.EVENT_STOP)

        self._connect_message_listener()

    def _connect_message_listener(self):
        self.message_broker.subscribe(
            MessageType.recording_finished, self.on_recording_finished
        )

    def update_label(self, msg: str):
        self.gui.set_label(msg)

    def on_gtk_toggle(self, *__):
        if self.gui.get_active():
            self.update_label(_("Recording ..."))
            self.controller.start_key_recording()
        else:
            self.update_label(_("Record Input"))
            self.controller.stop_key_recording()

    def on_recording_finished(self, __):
        logger.debug("finished recording")
        with HandlerDisabled(self.gui, self.on_gtk_toggle):
            self.gui.set_active(False)
            self.update_label(_("Record Input"))


class StatusBar:
    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        status_bar: Gtk.Statusbar,
        error_icon,
        warning_icon,
    ):
        self.message_broker = message_broker
        self.controller = controller
        self.gui = status_bar
        self.error_icon = error_icon
        self.warning_icon = warning_icon

        self._connect_message_listener()

    def _connect_message_listener(self):
        self.message_broker.subscribe(MessageType.status_msg, self.on_status_update)

    def on_status_update(self, data: StatusData):
        """Show a status message and set its tooltip.

        If message is None, it will remove the newest message of the
        given context_id.
        """
        context_id = data.ctx_id
        message = data.msg
        tooltip = data.tooltip
        status_bar = self.gui

        if message is None:
            status_bar.remove_all(context_id)

            if context_id in (CTX_ERROR, CTX_MAPPING):
                self.error_icon.hide()

            if context_id == CTX_WARNING:
                self.warning_icon.hide()

            status_bar.set_tooltip_text("")
        else:
            if tooltip is None:
                tooltip = message

            self.error_icon.hide()
            self.warning_icon.hide()

            if context_id in (CTX_ERROR, CTX_MAPPING):
                self.error_icon.show()

            if context_id == CTX_WARNING:
                self.warning_icon.show()

            max_length = 45
            if len(message) > max_length:
                message = message[: max_length - 3] + "..."

            status_bar.push(context_id, message)
            status_bar.set_tooltip_text(tooltip)


class AutoloadSwitch:
    def __init__(
        self, message_broker: MessageBroker, controller: Controller, switch: Gtk.Switch
    ):
        self.message_broker = message_broker
        self.controller = controller
        self.gui = switch

        self.gui.connect("state-set", self.on_gtk_toggle)
        self._connect_message_listener()

    def _connect_message_listener(self):
        self.message_broker.subscribe(MessageType.preset, self.on_preset_changed)

    def on_preset_changed(self, data: PresetData):
        with HandlerDisabled(self.gui, self.on_gtk_toggle):
            self.gui.set_active(data.autoload)

    def on_gtk_toggle(self, *_):
        self.controller.set_autoload(self.gui.get_active())


class ReleaseCombinationSwitch:
    def __init__(
        self, message_broker: MessageBroker, controller: Controller, switch: Gtk.Switch
    ):
        self.message_broker = message_broker
        self.controller = controller
        self.gui = switch

        self.gui.connect("state-set", self.on_gtk_toggle)
        self._connect_message_listener()

    def _connect_message_listener(self):
        self.message_broker.subscribe(MessageType.mapping, self.on_mapping_changed)

    def on_mapping_changed(self, data: MappingData):
        with HandlerDisabled(self.gui, self.on_gtk_toggle):
            self.gui.set_active(data.release_combination_keys)

    def on_gtk_toggle(self, *_):
        self.controller.update_mapping(release_combination_keys=self.gui.get_active())


class EventEntry(Gtk.ListBoxRow):
    """One row per InputEvent in the EventCombination."""

    __gtype_name__ = "EventEntry"

    def __init__(self, event: InputEvent, controller: Controller):
        super().__init__()

        self.input_event = event
        self.controller = controller
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        label = Gtk.Label()
        label.set_label(event.description())
        hbox.pack_start(label, False, False, 0)

        up_btn = Gtk.Button()
        up_btn.set_halign(Gtk.Align.END)
        up_btn.set_relief(Gtk.ReliefStyle.NONE)
        up_btn.get_style_context().add_class("no-v-padding")
        up_img = Gtk.Image.new_from_icon_name("go-up", Gtk.IconSize.BUTTON)
        up_btn.add(up_img)

        down_btn = Gtk.Button()
        down_btn.set_halign(Gtk.Align.END)
        down_btn.set_relief(Gtk.ReliefStyle.NONE)
        down_btn.get_style_context().add_class("no-v-padding")
        down_img = Gtk.Image.new_from_icon_name("go-down", Gtk.IconSize.BUTTON)
        down_btn.add(down_img)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.pack_start(up_btn, False, True, 0)
        vbox.pack_end(down_btn, False, True, 0)
        hbox.pack_end(vbox, False, False, 0)

        up_btn.connect(
            "clicked",
            lambda *_: self.controller.move_event_in_combination(
                self.input_event, "up"
            ),
        )
        down_btn.connect(
            "clicked",
            lambda *_: self.controller.move_event_in_combination(
                self.input_event, "down"
            ),
        )
        self.add(hbox)
        self.show_all()

    def cleanup(self):
        """cleanup any message listeners we are about to get destroyed"""
        # todo: see if we can do this with a gtk signal handler
        pass


class CombinationListbox:
    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        listbox: Gtk.ListBox,
    ):
        self.message_broker = message_broker
        self.controller = controller
        self.gui = listbox
        self.combination: Optional[EventCombination] = None
        self._connect_message_listeners()

        self.gui.connect("row-selected", self.on_gtk_row_selected)

    def _connect_message_listeners(self):
        self.message_broker.subscribe(MessageType.mapping, self.on_mapping_changed)
        self.message_broker.subscribe(MessageType.event, self.on_event_changed)

    def select_row(self, event: InputEvent):
        def select(r: EventEntry):
            if r.input_event == event:
                self.gui.select_row(r)

        self.gui.foreach(select)

    def on_mapping_changed(self, mapping: MappingData):
        if self.combination == mapping.event_combination:
            return

        self.gui.foreach(lambda label: (label.cleanup(), self.gui.remove(label)))
        if self.controller.is_empty_mapping():
            self.combination = None
        else:
            self.combination = mapping.event_combination
            for event in self.combination:
                self.gui.insert(EventEntry(event, self.controller), -1)

    def on_event_changed(self, event: InputEvent):
        with HandlerDisabled(self.gui, self.on_gtk_row_selected):
            self.select_row(event)

    def on_gtk_row_selected(self, *_):
        row: Optional[EventEntry] = None

        def find_row(r: EventEntry):
            nonlocal row
            if r.is_selected():
                row = r

        self.gui.foreach(find_row)
        if row:
            self.controller.load_event(row.input_event)


class AnalogInputSwitch:
    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        gui: Gtk.Switch,
    ):
        self.message_broker = message_broker
        self.controller = controller
        self.gui = gui
        self.event: Optional[InputEvent] = None

        self.gui.connect("state-set", self.on_gtk_toggle)
        self._connect_message_listeners()

    def _connect_message_listeners(self):
        self.message_broker.subscribe(MessageType.event, self.on_event)

    def on_event(self, event: InputEvent):
        with HandlerDisabled(self.gui, self.on_gtk_toggle):
            self.gui.set_active(event.value == 0)
            self.event = event

        if event.type == EV_KEY:
            self.gui.set_sensitive(False)
            self.gui.set_opacity(0.5)
        else:
            self.gui.set_sensitive(True)
            self.gui.set_opacity(1)

    def on_gtk_toggle(self, *_):
        self.controller.set_event_as_analog(self.gui.get_active())


class TriggerThresholdInput:
    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        gui: Gtk.SpinButton,
    ):
        self.message_broker = message_broker
        self.controller = controller
        self.gui = gui
        self.event: Optional[InputEvent] = None

        self.gui.set_increments(1, 1)
        self.gui.connect("value-changed", self.on_gtk_changed)
        self._connect_message_listeners()

    def _connect_message_listeners(self):
        self.message_broker.subscribe(MessageType.event, self.on_event)

    def on_event(self, event: InputEvent):
        if event.type == EV_KEY:
            self.gui.set_sensitive(False)
            self.gui.set_opacity(0.5)
        elif event.type == EV_ABS:
            self.gui.set_sensitive(True)
            self.gui.set_opacity(1)
            self.gui.set_range(-99, 99)
        else:
            self.gui.set_sensitive(True)
            self.gui.set_opacity(1)
            self.gui.set_range(-999, 999)

        with HandlerDisabled(self.gui, self.on_gtk_changed):
            self.gui.set_value(event.value)
            self.event = event

    def on_gtk_changed(self, *_):
        self.controller.update_event(self.event.modify(value=int(self.gui.get_value())))


class ReleaseTimeoutInput:
    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        gui: Gtk.SpinButton,
    ):
        self.message_broker = message_broker
        self.controller = controller
        self.gui = gui

        self.gui.set_increments(0.01, 0.01)
        self.gui.set_range(0, 2)
        self.gui.connect("value-changed", self.on_gtk_changed)

        self._connect_message_listeners()

    def _connect_message_listeners(self):
        self.message_broker.subscribe(MessageType.mapping, self.on_mapping_message)

    def on_mapping_message(self, mapping: MappingData):
        if EV_REL in [event.type for event in mapping.event_combination]:
            self.gui.set_sensitive(True)
            self.gui.set_opacity(1)
        else:
            self.gui.set_sensitive(False)
            self.gui.set_opacity(0.5)

        with HandlerDisabled(self.gui, self.on_gtk_changed):
            self.gui.set_value(mapping.release_timeout)

    def on_gtk_changed(self, *_):
        self.controller.update_mapping(release_timeout=self.gui.get_value())


class OutputAxisSelector:
    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        gui: Gtk.ComboBox,
    ):
        self.message_broker = message_broker
        self.controller = controller
        self.gui = gui
        self.uinputs: Dict[str, Capabilities] = {}
        self.model = Gtk.ListStore(str, str)

        self._current_target: Optional[str] = None

        self.gui.set_model(self.model)
        renderer_text = Gtk.CellRendererText()
        self.gui.pack_start(renderer_text, False)
        self.gui.add_attribute(renderer_text, "text", 1)
        self.gui.set_id_column(0)

        self.gui.connect("changed", self.on_gtk_select_axis)
        self._connect_message_listeners()

    def set_model(self, target: str):
        if target == self._current_target:
            return

        capabilities = self.uinputs.get(target) or defaultdict(list)
        types_codes = [(EV_ABS, code) for code in capabilities.get(EV_ABS) or ()]
        types_codes.extend((EV_REL, code) for code in capabilities.get(EV_REL) or ())
        self.model.clear()
        self.model.append([repr((None, None)), _("No Axis")])
        for type_code in types_codes:
            key_name = bytype[type_code[0]][type_code[1]]
            if isinstance(key_name, list):
                key_name = key_name[0]
            self.model.append([repr(type_code), key_name])

        self._current_target = target

    def _connect_message_listeners(self):
        self.message_broker.subscribe(MessageType.mapping, self.on_mapping_message)
        self.message_broker.subscribe(MessageType.uinputs, self.on_uinputs_message)

    def on_mapping_message(self, mapping: MappingData):
        with HandlerDisabled(self.gui, self.on_gtk_select_axis):
            self.set_model(mapping.target_uinput)
            self.gui.set_active_id(repr((mapping.output_type, mapping.output_code)))

    def on_uinputs_message(self, uinputs: UInputsData):
        self.uinputs = uinputs.uinputs

    def on_gtk_select_axis(self, *_):
        type_code = eval(self.gui.get_active_id())
        assert isinstance(type_code, tuple)
        self.controller.update_mapping(
            output_type=type_code[0], output_code=type_code[1]
        )


class ConfirmCancelDialog:
    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        gui: Gtk.Dialog,
        label: Gtk.Label,
    ):
        self.message_broker = message_broker
        self.controller = controller
        self.gui = gui
        self.label = label

        self._connect_message_listeners()

    def _connect_message_listeners(self):
        self.message_broker.subscribe(
            MessageType.user_confirm_request, self.on_user_confirm_request
        )

    def on_user_confirm_request(self, msg: UserConfirmRequest):
        self.label.set_label(msg.msg)
        self.gui.show()
        response = self.gui.run()
        self.gui.hide()
        msg.response(response == Gtk.ResponseType.ACCEPT)


class KeyAxisStack:
    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        gui: Gtk.Stack,
    ):
        self.message_broker = message_broker
        self.controller = controller
        self.gui = gui

        self._connect_message_listeners()

    def _connect_message_listeners(self):
        self.message_broker.subscribe(MessageType.mapping, self.on_mapping_message)

    def on_mapping_message(self, mapping: MappingData):
        if (
            mapping.output_type
            and mapping.output_code is not None
            and not mapping.output_symbol
        ):
            self.gui.set_visible_child_name("Analog Axis")
        elif mapping.output_symbol and not (
            mapping.output_code is not None or mapping.output_type
        ):
            self.gui.set_visible_child_name("Key or Macro")


class TransformationDrawArea:
    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        gui: Gtk.DrawingArea,
    ):
        self.message_broker = message_broker
        self.controller = controller
        self.gui = gui

        self.transformation: Callable[[Union[float, int]], float] = lambda x: x

        self.gui.connect("draw", self.on_gtk_draw)
        self._connect_message_listeners()

    def _connect_message_listeners(self):
        self.message_broker.subscribe(MessageType.mapping, self.on_mapping_message)

    def on_mapping_message(self, mapping: MappingData):
        self.transformation = Transformation(
            100, -100, mapping.deadzone, mapping.gain, mapping.expo
        )
        self.gui.queue_draw()

    def on_gtk_draw(self, _, context: cairo.Context):
        points = [
            (x / 200 + 0.5, -0.5 * self.transformation(x) + 0.5)
            for x in range(-100, 100)
        ]
        w = self.gui.get_allocated_width()
        h = self.gui.get_allocated_height()
        b = min((w, h))
        scaled_points = [(x * b, y * b) for x, y in points]

        # box
        context.move_to(0, 0)
        context.line_to(0, b)
        context.line_to(b, b)
        context.line_to(b, 0)
        context.line_to(0, 0)
        context.set_line_width(1)
        context.set_source_rgb(0.7, 0.7, 0.7)
        context.stroke()

        # x arrow
        context.move_to(0 * b, 0.5 * b)
        context.line_to(1 * b, 0.5 * b)
        context.line_to(0.96 * b, 0.52 * b)
        context.move_to(1 * b, 0.5 * b)
        context.line_to(0.96 * b, 0.48 * b)

        # y arrow
        context.move_to(0.5 * b, 1 * b)
        context.line_to(0.5 * b, 0)
        context.line_to(0.48 * b, 0.04 * b)
        context.move_to(0.5 * b, 0)
        context.line_to(0.52 * b, 0.04 * b)

        context.set_line_width(2)
        context.set_source_rgb(0.5, 0.5, 0.5)
        context.stroke()

        # graph
        context.move_to(*scaled_points[0])
        for p in scaled_points[1:]:
            # Ploting point
            context.line_to(*p)

        context.set_line_width(2)
        context.set_source_rgb(0.2, 0.2, 1)
        context.stroke()


class Sliders:
    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        gain: Gtk.Range,
        deadzone: Gtk.Range,
        expo: Gtk.Range,
    ):
        self.message_broker = message_broker
        self.controller = controller
        self.gain = gain
        self.deadzone = deadzone
        self.expo = expo

        self.gain.set_range(-2, 2)
        self.deadzone.set_range(0, 0.9)
        self.expo.set_range(-1, 1)

        self.gain.connect("value-changed", self.on_gtk_gain_changed)
        self.expo.connect("value-changed", self.on_gtk_expo_changed)
        self.deadzone.connect("value-changed", self.on_gtk_deadzone_changed)
        self._connect_message_listeners()

    def _connect_message_listeners(self):
        self.message_broker.subscribe(MessageType.mapping, self.on_mapping_message)

    def on_mapping_message(self, mapping: MappingData):
        with HandlerDisabled(self.gain, self.on_gtk_gain_changed):
            self.gain.set_value(mapping.gain)

        with HandlerDisabled(self.expo, self.on_gtk_expo_changed):
            self.expo.set_value(mapping.expo)

        with HandlerDisabled(self.deadzone, self.on_gtk_deadzone_changed):
            self.deadzone.set_value(mapping.deadzone)

    def on_gtk_gain_changed(self, *_):
        self.controller.update_mapping(gain=self.gain.get_value())

    def on_gtk_deadzone_changed(self, *_):
        self.controller.update_mapping(deadzone=self.deadzone.get_value())

    def on_gtk_expo_changed(self, *_):
        self.controller.update_mapping(expo=self.expo.get_value())
