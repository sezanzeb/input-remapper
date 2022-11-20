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


"""All components that control a single preset."""


from __future__ import annotations

from collections import defaultdict
from typing import List, Optional, Dict, Union, Callable, Literal, Set

import cairo
from evdev.ecodes import (
    EV_KEY,
    EV_ABS,
    EV_REL,
    bytype,
    BTN_LEFT,
    BTN_MIDDLE,
    BTN_RIGHT,
    BTN_EXTRA,
    BTN_SIDE,
)

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GtkSource", "4")
from gi.repository import Gtk, GtkSource, Gdk, GObject

from inputremapper.configs.mapping import MappingData
from inputremapper.event_combination import EventCombination
from inputremapper.groups import DeviceType
from inputremapper.gui.controller import Controller
from inputremapper.gui.gettext import _
from inputremapper.gui.messages.message_broker import (
    MessageBroker,
    MessageType,
)
from inputremapper.gui.messages.message_data import (
    UInputsData,
    PresetData,
    CombinationUpdate,
)
from inputremapper.gui.utils import HandlerDisabled, Colors, debounce, debounce_manager
from inputremapper.injection.mapping_handlers.axis_transform import Transformation
from inputremapper.input_event import InputEvent
from inputremapper.configs.system_mapping import system_mapping, XKB_KEYCODE_OFFSET

Capabilities = Dict[int, List]

SET_KEY_FIRST = _("Record the input first")

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


class TargetSelection:
    """The dropdown menu to select the targe_uinput of the active_mapping,

    For example "keyboard" or "gamepad".
    """

    _mapping: Optional[MappingData] = None

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

    def _select_current_target(self):
        """Select the currently configured target."""
        if self._mapping is not None:
            with HandlerDisabled(self._gui, self._on_gtk_target_selected):
                self._gui.set_active_id(self._mapping.target_uinput)

    def _on_uinputs_changed(self, data: UInputsData):
        target_store = Gtk.ListStore(str)
        for uinput in data.uinputs.keys():
            target_store.append([uinput])

        self._gui.set_model(target_store)
        renderer_text = Gtk.CellRendererText()
        self._gui.pack_start(renderer_text, False)
        self._gui.add_attribute(renderer_text, "text", 0)
        self._gui.set_id_column(0)

        self._select_current_target()

    def _on_mapping_loaded(self, mapping: MappingData):
        self._mapping = mapping
        self._select_current_target()

    def _on_gtk_target_selected(self, *_):
        target = self._gui.get_active_id()
        self._controller.update_mapping(target_uinput=target)


class MappingListBox:
    """The listbox showing all available mapping in the active_preset."""

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
    def _sort_func(row1: MappingSelectionLabel, row2: MappingSelectionLabel) -> int:
        """Sort alphanumerical by name."""
        if row1.combination == EventCombination.empty_combination():
            return 1
        if row2.combination == EventCombination.empty_combination():
            return 0

        return 0 if row1.name < row2.name else 1

    def _on_preset_changed(self, data: PresetData):
        selection_labels = self._gui.get_children()
        for selection_label in selection_labels:
            selection_label.cleanup()
            self._gui.remove(selection_label)

        if not data.mappings:
            return

        for mapping in data.mappings:
            selection_label = MappingSelectionLabel(
                self._message_broker,
                self._controller,
                mapping.format_name(),
                mapping.event_combination,
            )
            self._gui.insert(selection_label, -1)
        self._gui.invalidate_sort()

    def _on_mapping_changed(self, mapping: MappingData):
        with HandlerDisabled(self._gui, self._on_gtk_mapping_selected):
            combination = mapping.event_combination

            for row in self._gui.get_children():
                if row.combination == combination:
                    self._gui.select_row(row)

    def _on_gtk_mapping_selected(self, _, row: Optional[MappingSelectionLabel]):
        if not row:
            return
        self._controller.load_mapping(row.combination)


class MappingSelectionLabel(Gtk.ListBoxRow):
    """The ListBoxRow representing a mapping inside the MappingListBox."""

    __gtype_name__ = "MappingSelectionLabel"

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

        if not name:
            name = combination.beautify()

        self.name = name
        self.combination = combination

        # Make the child label widget break lines, important for
        # long combinations
        self.label = Gtk.Label()
        self.label.set_line_wrap(True)
        self.label.set_line_wrap_mode(Gtk.WrapMode.WORD)
        self.label.set_justify(Gtk.Justification.CENTER)
        # set the name or combination.beautify as label
        self.label.set_label(self.name)

        self.label.set_margin_top(11)
        self.label.set_margin_bottom(11)

        # button to edit the name of the mapping
        self.edit_btn = Gtk.Button()
        self.edit_btn.set_relief(Gtk.ReliefStyle.NONE)
        self.edit_btn.set_image(
            Gtk.Image.new_from_icon_name(Gtk.STOCK_EDIT, Gtk.IconSize.MENU)
        )
        self.edit_btn.set_tooltip_text(_("Change Mapping Name"))
        self.edit_btn.set_margin_top(4)
        self.edit_btn.set_margin_bottom(4)
        self.edit_btn.connect("clicked", self._set_edit_mode)

        self.name_input = Gtk.Entry()
        self.name_input.set_text(self.name)
        self.name_input.set_halign(Gtk.Align.FILL)
        self.name_input.set_margin_top(4)
        self.name_input.set_margin_bottom(4)
        self.name_input.connect("activate", self._on_gtk_rename_finished)
        self.name_input.connect("key-press-event", self._on_gtk_rename_abort)

        self._box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self._box.set_center_widget(self.label)
        self._box.add(self.edit_btn)
        self._box.set_child_packing(self.edit_btn, False, False, 4, Gtk.PackType.END)
        self._box.add(self.name_input)
        self._box.set_child_packing(self.name_input, True, True, 4, Gtk.PackType.START)

        self.add(self._box)
        self.show_all()
        self._message_broker.subscribe(MessageType.mapping, self._on_mapping_changed)
        self._message_broker.subscribe(
            MessageType.combination_update, self._on_combination_update
        )

        self.edit_btn.hide()
        self.name_input.hide()

    def __repr__(self):
        return f"MappingSelectionLabel for {self.combination} as {self.name}"

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
        self.name = mapping.format_name()
        self._set_selected()
        self.get_parent().invalidate_sort()

    def _on_combination_update(self, data: CombinationUpdate):
        if data.old_combination == self.combination and self.is_selected():
            self.combination = data.new_combination

    def _on_gtk_rename_finished(self, *_):
        name = self.name_input.get_text()
        if name.lower().strip() == self.combination.beautify().lower():
            name = ""
        self.name = name
        self._set_selected()
        self._controller.update_mapping(name=name)

    def _on_gtk_rename_abort(self, _, key_event: Gdk.EventKey):
        if key_event.keyval == Gdk.KEY_Escape:
            self._set_selected()

    def cleanup(self) -> None:
        """Clean up message listeners. Execute before removing from gui!"""
        self._message_broker.unsubscribe(self._on_mapping_changed)
        self._message_broker.unsubscribe(self._on_combination_update)


class GdkEventRecorder:
    """Records events delivered by GDK, similar to the ReaderService/ReaderClient."""

    _combination: List[int]
    _pressed: Set[int]

    __gtype_name__ = "GdkEventRecorder"

    def __init__(self, window: Gtk.Window, gui: Gtk.Label):
        super().__init__()
        self._combination = []
        self._pressed = set()
        self._gui = gui
        window.connect("event", self._on_gtk_event)

    def _get_button_code(self, event: Gdk.Event):
        """Get the evdev code for the given event."""
        return {
            Gdk.BUTTON_MIDDLE: BTN_MIDDLE,
            Gdk.BUTTON_PRIMARY: BTN_LEFT,
            Gdk.BUTTON_SECONDARY: BTN_RIGHT,
            9: BTN_EXTRA,
            8: BTN_SIDE,
        }.get(event.get_button().button)

    def _reset(self, event: Gdk.Event):
        """If a new combination is being typed, start from scratch."""
        gdk_event_type: int = event.type

        is_press = gdk_event_type in [
            Gdk.EventType.KEY_PRESS,
            Gdk.EventType.BUTTON_PRESS,
        ]

        if len(self._pressed) == 0 and is_press:
            self._combination = []

    def _press(self, event: Gdk.Event):
        """Remember pressed keys, write down combinations."""
        gdk_event_type: int = event.type

        if gdk_event_type == Gdk.EventType.KEY_PRESS:
            code = event.hardware_keycode - XKB_KEYCODE_OFFSET
            if code not in self._combination:
                self._combination.append(code)

            self._pressed.add(code)

        if gdk_event_type == Gdk.EventType.BUTTON_PRESS:
            code = self._get_button_code(event)
            if code not in self._combination:
                self._combination.append(code)

            self._pressed.add(code)

    def _release(self, event: Gdk.Event):
        """Clear pressed keys if this is a release event."""
        if event.type in [Gdk.EventType.KEY_RELEASE, Gdk.EventType.BUTTON_RELEASE]:
            self._pressed = set()

    def _display(self, event):
        """Show the recorded combination in the gui."""
        is_press = event.type in [
            Gdk.EventType.KEY_PRESS,
            Gdk.EventType.BUTTON_PRESS,
        ]

        if is_press and len(self._combination) > 0:
            names = [
                system_mapping.get_name(code)
                for code in self._combination
                if code is not None and system_mapping.get_name(code) is not None
            ]
            print("set etxt", names, self._combination)
            self._gui.set_text(" + ".join(names))

    def _on_gtk_event(self, _, event: Gdk.Event):
        """For all sorts of input events that gtk cares about."""
        self._reset(event)
        self._release(event)
        self._press(event)
        self._display(event)


class CodeEditor:
    """The editor used to edit the output_symbol of the active_mapping."""

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
        """Get the user-defined macro code string."""
        buffer = self.gui.get_buffer()
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)

    @code.setter
    def code(self, code: str) -> None:
        buffer = self.gui.get_buffer()
        with HandlerDisabled(buffer, self._on_gtk_changed):
            buffer.set_text(code)
            self.gui.do_move_cursor(self.gui, Gtk.MovementStep.BUFFER_ENDS, -1, False)

    def _connect_message_listener(self):
        self._message_broker.subscribe(
            MessageType.mapping,
            self._on_mapping_loaded,
        )
        self._message_broker.subscribe(
            MessageType.recording_finished,
            self._on_recording_finished,
        )

    def _toggle_line_numbers(self):
        """Show line numbers if multiline, otherwise remove them."""
        if "\n" in self.code:
            self.gui.set_show_line_numbers(True)
            # adds a bit of space between numbers and text:
            self.gui.set_show_line_marks(True)
            self.gui.set_monospace(True)
            self.gui.get_style_context().add_class("multiline")
        else:
            self.gui.set_show_line_numbers(False)
            self.gui.set_show_line_marks(False)
            self.gui.set_monospace(False)
            self.gui.get_style_context().remove_class("multiline")

    def _on_gtk_focus_out(self, *_):
        # This helps to keep the gui data up-to-date when changed-events are
        # debounced
        self._controller.update_mapping(output_symbol=self.code)
        debounce_manager.stop(self, self._on_gtk_changed)

    @debounce(500)
    def _on_gtk_changed(self, *_):
        # This triggers for each typed character, will cause disk-writes and writes
        # tons of logs, so this is debounced a bit
        self._controller.update_mapping(output_symbol=self.code)

    def _on_mapping_loaded(self, mapping: MappingData):
        debounce_manager.stop(self, self._on_gtk_changed)

        code = SET_KEY_FIRST
        if not self._controller.is_empty_mapping():
            code = mapping.output_symbol or ""

        if self.code.strip().lower() != code.strip().lower():
            self.code = code

        self._toggle_line_numbers()

    def _on_recording_finished(self, _):
        debounce_manager.stop(self, self._on_gtk_changed)
        self._controller.set_focus(self.gui)


class RequireActiveMapping:
    """Disable the widget if no mapping is selected."""

    def __init__(
        self,
        message_broker: MessageBroker,
        widget: Gtk.ToggleButton,
        require_recorded_input: False,
    ):
        self._widget = widget
        self._default_tooltip = self._widget.get_tooltip_text()
        self._require_recorded_input = require_recorded_input

        self._active_preset: Optional[PresetData] = None
        self._active_mapping: Optional[MappingData] = None

        message_broker.subscribe(MessageType.preset, self._on_preset)
        message_broker.subscribe(MessageType.mapping, self._on_mapping)

    def _on_preset(self, preset_data: PresetData):
        self._active_preset = preset_data
        self._check()

    def _on_mapping(self, mapping_data: MappingData):
        self._active_mapping = mapping_data
        self._check()

    def _check(self, *__):
        if not self._active_preset or len(self._active_preset.mappings) == 0:
            self._disable()
            self._widget.set_tooltip_text(_("Add a mapping first"))
            return

        if (
            self._require_recorded_input
            and self._active_mapping
            and not self._active_mapping.has_input_defined()
        ):
            self._disable()
            self._widget.set_tooltip_text(_("Record input first"))
            return

        self._enable()
        self._widget.set_tooltip_text(self._default_tooltip)

    def _enable(self):
        self._widget.set_sensitive(True)
        self._widget.set_opacity(1)

    def _disable(self):
        self._widget.set_sensitive(False)
        self._widget.set_opacity(0.5)


class RecordingToggle:
    """The toggle that starts input recording for the active_mapping."""

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
            MessageType.recording_finished,
            self._on_recording_finished,
        )

        RequireActiveMapping(
            message_broker,
            toggle,
            require_recorded_input=False,
        )

    def _on_gtk_toggle(self, *__):
        if self._gui.get_active():
            self._controller.start_key_recording()
        else:
            self._controller.stop_key_recording()

    def _on_recording_finished(self, __):
        with HandlerDisabled(self._gui, self._on_gtk_toggle):
            self._gui.set_active(False)


class RecordingStatus:
    """Displays if keys are being recorded for a mapping."""

    def __init__(
        self,
        message_broker: MessageBroker,
        label: Gtk.Label,
    ):
        self._gui = label

        message_broker.subscribe(
            MessageType.recording_started,
            self._on_recording_started,
        )

        message_broker.subscribe(
            MessageType.recording_finished,
            self._on_recording_finished,
        )

    def _on_recording_started(self, _):
        self._gui.set_visible(True)

    def _on_recording_finished(self, _):
        self._gui.set_visible(False)


class AutoloadSwitch:
    """The switch used to toggle the autoload state of the active_preset."""

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
    """The switch used to set the active_mapping.release_combination_keys parameter."""

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
    """The ListBoxRow representing a single event inside the CombinationListBox."""

    __gtype_name__ = "EventEntry"

    def __init__(self, event: InputEvent, controller: Controller):
        super().__init__()

        self.input_event = event
        self._controller = controller

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        hbox.set_margin_start(12)

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


class CombinationListbox:
    """The ListBox with all the events inside active_mapping.event_combination."""

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

        self._message_broker.subscribe(
            MessageType.mapping,
            self._on_mapping_changed,
        )
        self._message_broker.subscribe(
            MessageType.selected_event,
            self._on_event_changed,
        )

        self._gui.connect("row-selected", self._on_gtk_row_selected)

    def _select_row(self, event: InputEvent):
        for row in self._gui.get_children():
            if row.input_event == event:
                self._gui.select_row(row)

    def _on_mapping_changed(self, mapping: MappingData):
        if self._combination == mapping.event_combination:
            return

        event_entries = self._gui.get_children()
        for event_entry in event_entries:
            self._gui.remove(event_entry)

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
        for row in self._gui.get_children():
            if row.is_selected():
                self._controller.load_event(row.input_event)
                break


class AnalogInputSwitch:
    """The switch that marks the active_event as analog input."""

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
    """The number selection used to set the speed or position threshold of the
    active_event when it is an ABS or REL event used as a key."""

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
    """The number selector used to set the active_mapping.release_timeout parameter."""

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


class RelativeInputCutoffInput:
    """The number selector to set active_mapping.rel_to_abs_input_cutoff."""

    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        gui: Gtk.SpinButton,
    ):
        self._message_broker = message_broker
        self._controller = controller
        self._gui = gui

        self._gui.set_increments(1, 1)
        self._gui.set_range(1, 1000)
        self._gui.connect("value-changed", self._on_gtk_changed)
        self._message_broker.subscribe(MessageType.mapping, self._on_mapping_message)

    def _on_mapping_message(self, mapping: MappingData):
        if (
            EV_REL in [event.type for event in mapping.event_combination]
            and mapping.output_type == EV_ABS
        ):
            self._gui.set_sensitive(True)
            self._gui.set_opacity(1)
        else:
            self._gui.set_sensitive(False)
            self._gui.set_opacity(0.5)

        with HandlerDisabled(self._gui, self._on_gtk_changed):
            self._gui.set_value(mapping.rel_to_abs_input_cutoff)

    def _on_gtk_changed(self, *_):
        self._controller.update_mapping(rel_xy_cutoff=self._gui.get_value())


class OutputAxisSelector:
    """The dropdown menu used to select the output axis if the active_mapping is a
    mapping targeting an analog axis

    modifies the active_mapping.output_code and active_mapping.output_type parameters
    """

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
        types_codes = [
            (EV_ABS, code) for code, absinfo in capabilities.get(EV_ABS) or ()
        ]
        types_codes.extend((EV_REL, code) for code in capabilities.get(EV_REL) or ())
        self.model.clear()
        self.model.append(["None, None", _("No Axis")])
        for type_, code in types_codes:

            key_name = bytype[type_][code]
            if isinstance(key_name, list):
                key_name = key_name[0]
            self.model.append([f"{type_}, {code}", key_name])

        self._current_target = target

    def _on_mapping_message(self, mapping: MappingData):
        with HandlerDisabled(self._gui, self._on_gtk_select_axis):
            self._set_model(mapping.target_uinput)
            self._gui.set_active_id(f"{mapping.output_type}, {mapping.output_code}")

    def _on_uinputs_message(self, uinputs: UInputsData):
        self._uinputs = uinputs.uinputs

    def _on_gtk_select_axis(self, *_):
        if self._gui.get_active_id() == "None, None":
            type_code = (None, None)
        else:
            type_code = tuple(int(i) for i in self._gui.get_active_id().split(","))
        self._controller.update_mapping(
            output_type=type_code[0], output_code=type_code[1]
        )


class KeyAxisStackSwitcher:
    """The controls used to switch between the gui to modify a key-mapping or
    an analog-axis mapping."""

    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        stack: Gtk.Stack,
        key_macro_toggle: Gtk.ToggleButton,
        analog_toggle: Gtk.ToggleButton,
    ):
        self._message_broker = message_broker
        self._controller = controller
        self._stack = stack
        self._key_macro_toggle = key_macro_toggle
        self._analog_toggle = analog_toggle

        self._key_macro_toggle.connect("toggled", self._on_gtk_toggle)
        self._analog_toggle.connect("toggled", self._on_gtk_toggle)
        self._message_broker.subscribe(MessageType.mapping, self._on_mapping_message)

    def _set_active(self, mapping_type: Literal["key_macro", "analog"]):
        if mapping_type == "analog":
            self._stack.set_visible_child_name("Analog Axis")
            active = self._analog_toggle
            inactive = self._key_macro_toggle
        else:
            self._stack.set_visible_child_name("Key or Macro")
            active = self._key_macro_toggle
            inactive = self._analog_toggle

        with HandlerDisabled(active, self._on_gtk_toggle):
            active.set_active(True)
        with HandlerDisabled(inactive, self._on_gtk_toggle):
            inactive.set_active(False)

    def _on_mapping_message(self, mapping: MappingData):
        # fist check the actual mapping
        if mapping.mapping_type == "analog":
            self._set_active("analog")

        if mapping.mapping_type == "key_macro":
            self._set_active("key_macro")

    def _on_gtk_toggle(self, btn: Gtk.ToggleButton):
        # get_active returns the new toggle state already
        was_active = not btn.get_active()

        if was_active:
            # cannot deactivate manually
            with HandlerDisabled(btn, self._on_gtk_toggle):
                btn.set_active(True)
            return

        if btn is self._key_macro_toggle:
            self._controller.update_mapping(mapping_type="key_macro")
        else:
            self._controller.update_mapping(mapping_type="analog")


class TransformationDrawArea:
    """The graph which shows the relation between input- and output-axis."""

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
            # leave some space left and right for the lineCap to be visible
            for x in range(-97, 97)
        ]
        width = self._gui.get_allocated_width()
        height = self._gui.get_allocated_height()
        b = min((width, height))
        scaled_points = [(x * b, y * b) for x, y in points]

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
        arrow_color = Gdk.RGBA(0.5, 0.5, 0.5, 0.2)
        context.set_source_rgba(
            arrow_color.red,
            arrow_color.green,
            arrow_color.blue,
            arrow_color.alpha,
        )
        context.stroke()

        # graph
        context.move_to(*scaled_points[0])
        for scaled_point in scaled_points[1:]:
            # Ploting point
            context.line_to(*scaled_point)

        line_color = Colors.get_accent_color()
        context.set_line_width(3)
        context.set_line_cap(cairo.LineCap.ROUND)
        # the default gtk adwaita highlight color:
        context.set_source_rgba(
            line_color.red,
            line_color.green,
            line_color.blue,
            line_color.alpha,
        )
        context.stroke()


class Sliders:
    """The different sliders to modify the gain, deadzone and expo parameters of the
    active_mapping."""

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
