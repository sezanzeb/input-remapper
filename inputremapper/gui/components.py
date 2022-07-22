from __future__ import annotations

from collections import defaultdict
from typing import List, Optional, Dict, Literal, Union, Tuple, Callable

import cairo
from evdev.ecodes import EV_KEY, EV_ABS, EV_REL, bytype
from gi.repository import Gtk, GtkSource, Gdk

from inputremapper.configs.mapping import MappingData
from inputremapper.configs.system_mapping import SystemMapping
from inputremapper.event_combination import EventCombination
from inputremapper.groups import DeviceType
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
    DeviceType.GAMEPAD: "input-gaming",
    DeviceType.MOUSE: "input-mouse",
    DeviceType.KEYBOARD: "input-keyboard",
    DeviceType.GRAPHICS_TABLET: "input-tablet",
    DeviceType.TOUCHPAD: "input-touchpad",
    DeviceType.UNKNOWN: None,
}

# sort types that most devices would fall in easily to the right.
ICON_PRIORITIES = [
    DeviceType.GRAPHICS_TABLET,
    DeviceType.TOUCHPAD,
    DeviceType.GAMEPAD,
    DeviceType.MOUSE,
    DeviceType.KEYBOARD,
    DeviceType.UNKNOWN,
]


class DeviceSelection:
    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        combobox: Gtk.ComboBox,
    ):
        self._message_broker = message_broker
        self._controller = controller
        self._device_store = Gtk.ListStore(str, str, str)
        self._gui = combobox

        # https://python-gtk-3-tutorial.readthedocs.io/en/latest/treeview.html#the-view
        combobox.set_model(self._device_store)
        renderer_icon = Gtk.CellRendererPixbuf()
        renderer_text = Gtk.CellRendererText()
        renderer_text.set_padding(5, 0)
        combobox.pack_start(renderer_icon, False)
        combobox.pack_start(renderer_text, False)
        combobox.add_attribute(renderer_icon, "icon-name", 1)
        combobox.add_attribute(renderer_text, "text", 2)
        combobox.set_id_column(0)

        self._message_broker.subscribe(MessageType.groups, self._on_groups_changed)
        self._message_broker.subscribe(MessageType.group, self._on_group_changed)
        combobox.connect("changed", self._on_gtk_select_device)

    def _on_groups_changed(self, data: GroupsData):
        with HandlerDisabled(self._gui, self._on_gtk_select_device):
            self._device_store.clear()
            for group_key, types in data.groups.items():
                if len(types) > 0:
                    device_type = sorted(types, key=ICON_PRIORITIES.index)[0]
                    icon_name = ICON_NAMES[device_type]
                else:
                    icon_name = None

                logger.debug(f"adding {group_key} to device dropdown ")
                self._device_store.append([group_key, icon_name, group_key])

    def _on_group_changed(self, data: GroupData):
        with HandlerDisabled(self._gui, self._on_gtk_select_device):
            self._gui.set_active_id(data.group_key)

    def _on_gtk_select_device(self, *_, **__):
        group_key = self._gui.get_active_id()
        logger.debug('Selecting device "%s"', group_key)
        self._controller.load_group(group_key)


class TargetSelection:
    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        combobox: Gtk.ComboBox,
    ):
        self._message_broker = message_broker
        self._controller = controller
        self._gui = combobox

        self._message_broker.subscribe(MessageType.uinputs, self._on_uinputs_changed)
        self._message_broker.subscribe(MessageType.mapping, self._on_mapping_loaded)
        self._gui.connect("changed", self._on_gtk_target_selected)

    def _on_uinputs_changed(self, data: UInputsData):
        target_store = Gtk.ListStore(str)
        for uinput in data.uinputs.keys():
            target_store.append([uinput])

        self._gui.set_model(target_store)
        renderer_text = Gtk.CellRendererText()
        self._gui.pack_start(renderer_text, False)
        self._gui.add_attribute(renderer_text, "text", 0)
        self._gui.set_id_column(0)

    def _on_mapping_loaded(self, mapping: MappingData):
        if not self._controller.is_empty_mapping():
            self._enable()
        else:
            self._disable()

        with HandlerDisabled(self._gui, self._on_gtk_target_selected):
            self._gui.set_active_id(mapping.target_uinput)

    def _enable(self):
        self._gui.set_sensitive(True)
        self._gui.set_opacity(1)

    def _disable(self):
        self._gui.set_sensitive(False)
        self._gui.set_opacity(0.5)

    def _on_gtk_target_selected(self, *_):
        target = self._gui.get_active_id()
        self._controller.update_mapping(target_uinput=target)


class PresetSelection:
    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        combobox: Gtk.ComboBoxText,
    ):
        self._message_broker = message_broker
        self._controller = controller
        self._gui = combobox

        self._connect_message_listener()
        combobox.connect("changed", self._on_gtk_select_preset)

    def _connect_message_listener(self):
        self._message_broker.subscribe(MessageType.group, self._on_group_changed)
        self._message_broker.subscribe(MessageType.preset, self._on_preset_changed)

    def _on_group_changed(self, data: GroupData):
        with HandlerDisabled(self._gui, self._on_gtk_select_preset):
            self._gui.remove_all()
            for preset in data.presets:
                self._gui.append(preset, preset)

    def _on_preset_changed(self, data: PresetData):
        with HandlerDisabled(self._gui, self._on_gtk_select_preset):
            self._gui.set_active_id(data.name)

    def _on_gtk_select_preset(self, *_, **__):
        name = self._gui.get_active_id()
        logger.debug('Selecting preset "%s"', name)
        self._controller.load_preset(name)


class MappingListBox:
    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        listbox: Gtk.ListBox,
    ):
        self._message_broker = message_broker
        self._controller = controller
        self._gui = listbox
        self._gui.set_sort_func(self._sort_func)

        self._message_broker.subscribe(MessageType.preset, self._on_preset_changed)
        self._message_broker.subscribe(MessageType.mapping, self._on_mapping_changed)
        self._gui.connect("row-selected", self._on_gtk_mapping_selected)

    @staticmethod
    def _sort_func(row1: SelectionLabel, row2: SelectionLabel) -> int:
        """sort alphanumerical by name"""
        if row1.combination == EventCombination.empty_combination():
            return 1
        if row2.combination == EventCombination.empty_combination():
            return 0

        return 0 if row1.name < row2.name else 1

    def _on_preset_changed(self, data: PresetData):
        self._gui.foreach(lambda label: (label.cleanup(), self._gui.remove(label)))
        if not data.mappings:
            return

        for name, combination in data.mappings:
            selection_label = SelectionLabel(
                self._message_broker, self._controller, name, combination
            )
            self._gui.insert(selection_label, -1)
        self._gui.invalidate_sort()

    def _on_mapping_changed(self, mapping: MappingData):
        with HandlerDisabled(self._gui, self._on_gtk_mapping_selected):
            combination = mapping.event_combination

            def set_active(row: SelectionLabel):
                if row.combination == combination:
                    self._gui.select_row(row)

            self._gui.foreach(set_active)

    def _on_gtk_mapping_selected(self, _, row: Optional[SelectionLabel]):
        if not row:
            return
        self._controller.load_mapping(row.combination)


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
        self._message_broker = message_broker
        self._controller = controller
        self._name = name
        self.combination = combination

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
        self.name_input.connect("activate", self._on_gtk_rename_finished)

        self._box = Gtk.Box(Gtk.Orientation.HORIZONTAL)
        self._box.set_center_widget(self.label)
        self._box.add(self.edit_btn)
        self._box.set_child_packing(self.edit_btn, False, False, 4, Gtk.PackType.END)
        self._box.add(self.name_input)
        self._box.set_child_packing(self.name_input, False, True, 4, Gtk.PackType.START)

        self.add(self._box)
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
        self._message_broker.subscribe(MessageType.mapping, self._on_mapping_changed)
        self._message_broker.subscribe(
            MessageType.combination_update, self._on_combination_update
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
        self._controller.set_focus(self.name_input)

    def _on_mapping_changed(self, mapping: MappingData):
        if mapping.event_combination != self.combination:
            self._set_not_selected()
            return
        self._name = mapping.name
        self._set_selected()
        self.get_parent().invalidate_sort()

    def _on_combination_update(self, data: CombinationUpdate):
        if data.old_combination == self.combination and self.is_selected():
            self.combination = data.new_combination

    def _on_gtk_rename_finished(self, *_):
        name = self.name_input.get_text()
        if name.lower().strip() == self.combination.beautify().lower():
            name = ""
        self._name = name
        self._set_selected()
        self._controller.update_mapping(name=name)

    def cleanup(self) -> None:
        """clean up message listeners. Execute before removing from gui!"""
        self._message_broker.unsubscribe(self._on_mapping_changed)
        self._message_broker.unsubscribe(self._on_combination_update)


class CodeEditor:
    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        editor: GtkSource.View,
    ):
        self._message_broker = message_broker
        self._controller = controller
        self.gui = editor

        # without this the wrapping ScrolledWindow acts weird when new lines are added,
        # not offering enough space to the text editor so the whole thing is suddenly
        # scrollable by a few pixels.
        # Found this after making blind guesses with settings in glade, and then
        # actually looking at the snapshot preview! In glades editor this didn't have an
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

        self.gui.connect("focus-out-event", self._on_gtk_focus_out)
        self.gui.get_buffer().connect("changed", self._on_gtk_changed)
        self._connect_message_listener()

    @property
    def code(self) -> str:
        buffer = self.gui.get_buffer()
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)

    @code.setter
    def code(self, code: str) -> None:
        buffer = self.gui.get_buffer()
        with HandlerDisabled(buffer, self._on_gtk_changed):
            buffer.set_text(code)
            self.gui.do_move_cursor(self.gui, Gtk.MovementStep.BUFFER_ENDS, -1, False)

    def _connect_message_listener(self):
        self._message_broker.subscribe(MessageType.mapping, self._on_mapping_loaded)
        self._message_broker.subscribe(
            MessageType.recording_finished, self._on_recording_finished
        )

    def _toggle_line_numbers(self):
        """Show line numbers if multiline, otherwise remove them"""
        if "\n" in self.code:
            self.gui.set_show_line_numbers(True)
            self.gui.set_monospace(True)
            self.gui.get_style_context().add_class("multiline")
        else:
            self.gui.set_show_line_numbers(False)
            self.gui.set_monospace(False)
            self.gui.get_style_context().remove_class("multiline")

    def _enable(self):
        logger.debug("Enabling the code editor")
        self.gui.set_sensitive(True)
        self.gui.set_opacity(1)

    def _disable(self):
        logger.debug("Disabling the code editor")

        # beware that this also appeared to disable event listeners like
        # focus-out-event:
        self.gui.set_sensitive(False)
        self.gui.set_opacity(0.5)

    def _on_gtk_focus_out(self, *_):
        self._controller.save()

    def _on_gtk_changed(self, *_):
        self._controller.update_mapping(output_symbol=self.code)

    def _on_mapping_loaded(self, mapping: MappingData):
        code = SET_KEY_FIRST
        if not self._controller.is_empty_mapping():
            code = mapping.output_symbol or ""
            self._enable()
        else:
            self._disable()

        if self.code.strip().lower() != code.strip().lower():
            self.code = code
        self._toggle_line_numbers()

    def _on_recording_finished(self, _):
        self._controller.set_focus(self.gui)


class RecordingToggle:
    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        toggle: Gtk.ToggleButton,
    ):
        self._message_broker = message_broker
        self._controller = controller
        self._gui = toggle

        toggle.connect("toggled", self._on_gtk_toggle)
        # Don't leave the input when using arrow keys or tab. wait for the
        # window to consume the keycode from the reader. I.e. a tab input should
        # be recorded, instead of causing the recording to stop.
        toggle.connect("key-press-event", lambda *args: Gdk.EVENT_STOP)
        self._message_broker.subscribe(
            MessageType.recording_finished, self._on_recording_finished
        )
        self._update_label(_("Record Input"))

    def _update_label(self, msg: str):
        self._gui.set_label(msg)

    def _on_gtk_toggle(self, *__):
        if self._gui.get_active():
            self._update_label(_("Recording ..."))
            self._controller.start_key_recording()
        else:
            self._update_label(_("Record Input"))
            self._controller.stop_key_recording()

    def _on_recording_finished(self, __):
        logger.debug("finished recording")
        with HandlerDisabled(self._gui, self._on_gtk_toggle):
            self._gui.set_active(False)
            self._update_label(_("Record Input"))


class StatusBar:
    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        status_bar: Gtk.Statusbar,
        error_icon: Gtk.Image,
        warning_icon: Gtk.Image,
    ):
        self._message_broker = message_broker
        self._controller = controller
        self._gui = status_bar
        self._error_icon = error_icon
        self._warning_icon = warning_icon

        self._message_broker.subscribe(MessageType.status_msg, self._on_status_update)
        self._message_broker.subscribe(MessageType.init, self._on_init)

        # keep track if there is an error or warning in the stack of statusbar
        # unfortunately this is not exposed over the api
        self._error = False
        self._warning = False

    def _on_init(self, _):
        self._error_icon.hide()
        self._warning_icon.hide()

    def _on_status_update(self, data: StatusData):
        """Show a status message and set its tooltip.

        If message is None, it will remove the newest message of the
        given context_id.
        """
        context_id = data.ctx_id
        message = data.msg
        tooltip = data.tooltip
        status_bar = self._gui

        if message is None:
            status_bar.remove_all(context_id)

            if context_id in (CTX_ERROR, CTX_MAPPING):
                self._error_icon.hide()
                self._error = False
                if self._warning:
                    self._warning_icon.show()

            if context_id == CTX_WARNING:
                self._warning_icon.hide()
                self._warning = False
                if self._error:
                    self._error_icon.show()

            status_bar.set_tooltip_text("")
        else:
            if tooltip is None:
                tooltip = message

            self._error_icon.hide()
            self._warning_icon.hide()

            if context_id in (CTX_ERROR, CTX_MAPPING):
                self._error_icon.show()
                self._error = True

            if context_id == CTX_WARNING:
                self._warning_icon.show()
                self._warning = True

            max_length = 45
            if len(message) > max_length:
                message = message[: max_length - 3] + "..."

            status_bar.push(context_id, message)
            status_bar.set_tooltip_text(tooltip)


class AutoloadSwitch:
    def __init__(
        self, message_broker: MessageBroker, controller: Controller, switch: Gtk.Switch
    ):
        self._message_broker = message_broker
        self._controller = controller
        self._gui = switch

        self._gui.connect("state-set", self._on_gtk_toggle)
        self._message_broker.subscribe(MessageType.preset, self._on_preset_changed)

    def _on_preset_changed(self, data: PresetData):
        with HandlerDisabled(self._gui, self._on_gtk_toggle):
            self._gui.set_active(data.autoload)

    def _on_gtk_toggle(self, *_):
        self._controller.set_autoload(self._gui.get_active())


class ReleaseCombinationSwitch:
    """switch for Mapping.release_combination_keys"""

    def __init__(
        self, message_broker: MessageBroker, controller: Controller, switch: Gtk.Switch
    ):
        self._message_broker = message_broker
        self._controller = controller
        self._gui = switch

        self._gui.connect("state-set", self._on_gtk_toggle)
        self._message_broker.subscribe(MessageType.mapping, self._on_mapping_changed)

    def _on_mapping_changed(self, data: MappingData):
        with HandlerDisabled(self._gui, self._on_gtk_toggle):
            self._gui.set_active(data.release_combination_keys)

    def _on_gtk_toggle(self, *_):
        self._controller.update_mapping(release_combination_keys=self._gui.get_active())


class EventEntry(Gtk.ListBoxRow):
    """One row per InputEvent in the EventCombination."""

    __gtype_name__ = "EventEntry"

    def __init__(self, event: InputEvent, controller: Controller):
        super().__init__()

        self.input_event = event
        self._controller = controller
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
            lambda *_: self._controller.move_event_in_combination(
                self.input_event, "up"
            ),
        )
        down_btn.connect(
            "clicked",
            lambda *_: self._controller.move_event_in_combination(
                self.input_event, "down"
            ),
        )
        self.add(hbox)
        self.show_all()

        # only used in testing
        self._up_btn = up_btn
        self._down_btn = down_btn

    def cleanup(self):
        """remove any message listeners we are about to get destroyed"""
        pass


class CombinationListbox:
    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        listbox: Gtk.ListBox,
    ):
        self._message_broker = message_broker
        self._controller = controller
        self._gui = listbox
        self._combination: Optional[EventCombination] = None

        self._message_broker.subscribe(MessageType.mapping, self._on_mapping_changed)
        self._message_broker.subscribe(
            MessageType.selected_event, self._on_event_changed
        )
        self._gui.connect("row-selected", self._on_gtk_row_selected)

    def _select_row(self, event: InputEvent):
        def select(r: EventEntry):
            if r.input_event == event:
                self._gui.select_row(r)

        self._gui.foreach(select)

    def _on_mapping_changed(self, mapping: MappingData):
        if self._combination == mapping.event_combination:
            return

        self._gui.foreach(lambda label: (label.cleanup(), self._gui.remove(label)))
        if self._controller.is_empty_mapping():
            self._combination = None
        else:
            self._combination = mapping.event_combination
            for event in self._combination:
                self._gui.insert(EventEntry(event, self._controller), -1)

    def _on_event_changed(self, event: InputEvent):
        with HandlerDisabled(self._gui, self._on_gtk_row_selected):
            self._select_row(event)

    def _on_gtk_row_selected(self, *_):
        row: Optional[EventEntry] = None

        def find_row(r: EventEntry):
            nonlocal row
            if r.is_selected():
                row = r

        self._gui.foreach(find_row)
        if row:
            self._controller.load_event(row.input_event)


class AnalogInputSwitch:
    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        gui: Gtk.Switch,
    ):
        self._message_broker = message_broker
        self._controller = controller
        self._gui = gui
        self._event: Optional[InputEvent] = None

        self._gui.connect("state-set", self._on_gtk_toggle)
        self._message_broker.subscribe(MessageType.selected_event, self._on_event)

    def _on_event(self, event: InputEvent):
        with HandlerDisabled(self._gui, self._on_gtk_toggle):
            self._gui.set_active(event.value == 0)
            self._event = event

        if event.type == EV_KEY:
            self._gui.set_sensitive(False)
            self._gui.set_opacity(0.5)
        else:
            self._gui.set_sensitive(True)
            self._gui.set_opacity(1)

    def _on_gtk_toggle(self, *_):
        self._controller.set_event_as_analog(self._gui.get_active())


class TriggerThresholdInput:
    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        gui: Gtk.SpinButton,
    ):
        self._message_broker = message_broker
        self._controller = controller
        self._gui = gui
        self._event: Optional[InputEvent] = None

        self._gui.set_increments(1, 1)
        self._gui.connect("value-changed", self._on_gtk_changed)
        self._message_broker.subscribe(MessageType.selected_event, self._on_event)

    def _on_event(self, event: InputEvent):
        if event.type == EV_KEY:
            self._gui.set_sensitive(False)
            self._gui.set_opacity(0.5)
        elif event.type == EV_ABS:
            self._gui.set_sensitive(True)
            self._gui.set_opacity(1)
            self._gui.set_range(-99, 99)
        else:
            self._gui.set_sensitive(True)
            self._gui.set_opacity(1)
            self._gui.set_range(-999, 999)

        with HandlerDisabled(self._gui, self._on_gtk_changed):
            self._gui.set_value(event.value)
            self._event = event

    def _on_gtk_changed(self, *_):
        self._controller.update_event(
            self._event.modify(value=int(self._gui.get_value()))
        )


class ReleaseTimeoutInput:
    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        gui: Gtk.SpinButton,
    ):
        self._message_broker = message_broker
        self._controller = controller
        self._gui = gui

        self._gui.set_increments(0.01, 0.01)
        self._gui.set_range(0, 2)
        self._gui.connect("value-changed", self._on_gtk_changed)
        self._message_broker.subscribe(MessageType.mapping, self._on_mapping_message)

    def _on_mapping_message(self, mapping: MappingData):
        if EV_REL in [event.type for event in mapping.event_combination]:
            self._gui.set_sensitive(True)
            self._gui.set_opacity(1)
        else:
            self._gui.set_sensitive(False)
            self._gui.set_opacity(0.5)

        with HandlerDisabled(self._gui, self._on_gtk_changed):
            self._gui.set_value(mapping.release_timeout)

    def _on_gtk_changed(self, *_):
        self._controller.update_mapping(release_timeout=self._gui.get_value())


class OutputAxisSelector:
    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        gui: Gtk.ComboBox,
    ):
        self._message_broker = message_broker
        self._controller = controller
        self._gui = gui
        self._uinputs: Dict[str, Capabilities] = {}
        self.model = Gtk.ListStore(str, str)

        self._current_target: Optional[str] = None

        self._gui.set_model(self.model)
        renderer_text = Gtk.CellRendererText()
        self._gui.pack_start(renderer_text, False)
        self._gui.add_attribute(renderer_text, "text", 1)
        self._gui.set_id_column(0)

        self._gui.connect("changed", self._on_gtk_select_axis)
        self._message_broker.subscribe(MessageType.mapping, self._on_mapping_message)
        self._message_broker.subscribe(MessageType.uinputs, self._on_uinputs_message)

    def _set_model(self, target: str):
        if target == self._current_target:
            return

        capabilities = self._uinputs.get(target) or defaultdict(list)
        types_codes = [(EV_ABS, code) for code in capabilities.get(EV_ABS) or ()]
        types_codes.extend((EV_REL, code) for code in capabilities.get(EV_REL) or ())
        self.model.clear()
        self.model.append([f"None, None", _("No Axis")])
        for type_code in types_codes:
            key_name = bytype[type_code[0]][type_code[1]]
            if isinstance(key_name, list):
                key_name = key_name[0]
            self.model.append([f"{type_code[0]}, {type_code[1]}", key_name])

        self._current_target = target

    def _on_mapping_message(self, mapping: MappingData):
        with HandlerDisabled(self._gui, self._on_gtk_select_axis):
            self._set_model(mapping.target_uinput)
            self._gui.set_active_id(f"{mapping.output_type}, {mapping.output_code}")

    def _on_uinputs_message(self, uinputs: UInputsData):
        self._uinputs = uinputs.uinputs

    def _on_gtk_select_axis(self, *_):
        if self._gui.get_active_id() == f"None, None":
            type_code = (None, None)
        else:
            type_code = tuple(int(i) for i in self._gui.get_active_id().split(","))
        self._controller.update_mapping(
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
        self._message_broker = message_broker
        self._controller = controller
        self._gui = gui
        self._label = label

        self._message_broker.subscribe(
            MessageType.user_confirm_request, self._on_user_confirm_request
        )

    def _on_user_confirm_request(self, msg: UserConfirmRequest):
        self._label.set_label(msg.msg)
        self._gui.show()
        response = self._gui.run()
        self._gui.hide()
        msg.respond(response == Gtk.ResponseType.ACCEPT)


class KeyAxisStack:
    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        gui: Gtk.Stack,
    ):
        self._message_broker = message_broker
        self._controller = controller
        self._gui = gui

        self._message_broker.subscribe(MessageType.mapping, self._on_mapping_message)

    def _on_mapping_message(self, mapping: MappingData):
        if (
            mapping.output_type
            and mapping.output_code is not None
            and not mapping.output_symbol
        ):
            self._gui.set_visible_child_name("Analog Axis")
        elif mapping.output_symbol and not (
            mapping.output_code is not None or mapping.output_type
        ):
            self._gui.set_visible_child_name("Key or Macro")


class TransformationDrawArea:
    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        gui: Gtk.DrawingArea,
    ):
        self._message_broker = message_broker
        self._controller = controller
        self._gui = gui

        self._transformation: Callable[[Union[float, int]], float] = lambda x: x

        self._gui.connect("draw", self._on_gtk_draw)
        self._message_broker.subscribe(MessageType.mapping, self._on_mapping_message)

    def _on_mapping_message(self, mapping: MappingData):
        self._transformation = Transformation(
            100, -100, mapping.deadzone, mapping.gain, mapping.expo
        )
        self._gui.queue_draw()

    def _on_gtk_draw(self, _, context: cairo.Context):
        points = [
            (x / 200 + 0.5, -0.5 * self._transformation(x) + 0.5)
            for x in range(-100, 100)
        ]
        w = self._gui.get_allocated_width()
        h = self._gui.get_allocated_height()
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
        self._message_broker = message_broker
        self._controller = controller
        self._gain = gain
        self._deadzone = deadzone
        self._expo = expo

        self._gain.set_range(-2, 2)
        self._deadzone.set_range(0, 0.9)
        self._expo.set_range(-1, 1)

        self._gain.connect("value-changed", self._on_gtk_gain_changed)
        self._expo.connect("value-changed", self._on_gtk_expo_changed)
        self._deadzone.connect("value-changed", self._on_gtk_deadzone_changed)
        self._message_broker.subscribe(MessageType.mapping, self._on_mapping_message)

    def _on_mapping_message(self, mapping: MappingData):
        with HandlerDisabled(self._gain, self._on_gtk_gain_changed):
            self._gain.set_value(mapping.gain)

        with HandlerDisabled(self._expo, self._on_gtk_expo_changed):
            self._expo.set_value(mapping.expo)

        with HandlerDisabled(self._deadzone, self._on_gtk_deadzone_changed):
            self._deadzone.set_value(mapping.deadzone)

    def _on_gtk_gain_changed(self, *_):
        self._controller.update_mapping(gain=self._gain.get_value())

    def _on_gtk_deadzone_changed(self, *_):
        self._controller.update_mapping(deadzone=self._deadzone.get_value())

    def _on_gtk_expo_changed(self, *_):
        self._controller.update_mapping(expo=self._expo.get_value())
