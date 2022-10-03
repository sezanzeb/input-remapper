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

from __future__ import annotations

from collections import defaultdict
from typing import List, Optional, Dict, Union, Callable, Literal

import cairo
from evdev.ecodes import EV_KEY, EV_ABS, EV_REL, bytype
from gi.repository import Gtk, GtkSource, Gdk

from inputremapper.configs.mapping import MappingData
from inputremapper.event_combination import EventCombination
from inputremapper.groups import DeviceType
from inputremapper.gui.controller import Controller
from inputremapper.gui.gettext import _
from inputremapper.exceptions import NoMappingError
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
    DoStackSwitch,
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


class DeviceGroupEntry(Gtk.ToggleButton):
    """A device that can be selected in the GUI.

    For example a keyboard or a mouse.
    """

    __gtype_name__ = "DeviceGroupEntry"

    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        icon_name: Optional[str],
        group_key: str,
    ):
        super().__init__()
        self.icon_name = icon_name
        self.message_broker = message_broker
        self.group_key = group_key
        self._controller = controller

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        if icon_name:
            icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.DND)
            box.add(icon)

        label = Gtk.Label()
        label.set_label(group_key)

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

        self.connect("toggled", self._on_gtk_select_device)

    def _on_gtk_select_device(self, *_, **__):
        logger.debug('Selecting device "%s"', self.group_key)
        self._controller.load_group(self.group_key)
        self.message_broker.send(DoStackSwitch(Stack.presets_page))

    def show_active(self, active):
        """Show the active state without triggering anything."""
        with HandlerDisabled(self, self._on_gtk_select_device):
            self.set_active(active)


class DeviceGroupSelection:
    """A wrapper for the container with our groups.

    A group is a collection of devices.
    """

    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        flowbox: Gtk.FlowBox,
    ):
        self._message_broker = message_broker
        self._controller = controller
        self._gui = flowbox

        self._message_broker.subscribe(MessageType.groups, self._on_groups_changed)
        self._message_broker.subscribe(MessageType.group, self._on_group_changed)

    def _on_groups_changed(self, data: GroupsData):
        self._gui.foreach(lambda group: self._gui.remove(group))

        for group_key, types in data.groups.items():
            if len(types) > 0:
                device_type = sorted(types, key=ICON_PRIORITIES.index)[0]
                icon_name = ICON_NAMES[device_type]
            else:
                icon_name = None

            logger.debug(f"adding {group_key} to device selection")
            device_group_entry = DeviceGroupEntry(
                self._message_broker,
                self._controller,
                icon_name,
                group_key,
            )
            self._gui.insert(device_group_entry, -1)

    def _on_group_changed(self, data: GroupData):
        self.show_active_group_key(data.group_key)

    def show_active_group_key(self, group_key: str):
        """Highlight the button of the given group."""
        for child in self._gui.get_children():
            device_group_entry: DeviceGroupEntry = child.get_children()[0]
            device_group_entry.show_active(device_group_entry.group_key == group_key)


# TODO test
class Stack:
    """Wraps the Stack, which contains the main menu pages."""

    devices_page = 0
    presets_page = 1
    editor_page = 2

    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        stack: Gtk.Stack,
    ):
        self._message_broker = message_broker
        self._controller = controller
        self._gui = stack

        self._message_broker.subscribe(
            MessageType.do_stack_switch, self._do_stack_switch
        )

    def _do_stack_switch(self, msg: DoStackSwitch):
        self._gui.set_visible_child(self._gui.get_children()[msg.page_index])


class TargetSelection:
    """The dropdown menu to select the targe_uinput of the active_mapping,

    For example "keyboard" or "gamepad".
    """

    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        listbox: Gtk.listbox,
    ):
        self._message_broker = message_broker
        self._controller = controller
        self._gui = listbox

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


class PresetEntry(Gtk.ToggleButton):
    """A preset that can be selected in the GUI."""

    __gtype_name__ = "PresetEntry"

    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        preset_name: str,
    ):
        super().__init__()
        self.message_broker = message_broker
        self.preset_name = preset_name
        self._controller = controller

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        label = Gtk.Label()

        # wrap very long names properly
        label.set_line_wrap(True)
        label.set_line_wrap_mode(2)
        # this affeects how many device entries fit next to each other
        label.set_width_chars(28)
        label.set_max_width_chars(28)

        label.set_label(preset_name)
        box.add(label)

        box.set_margin_top(18)
        box.set_margin_bottom(18)
        box.set_homogeneous(True)
        box.set_spacing(12)

        # self.set_relief(Gtk.ReliefStyle.NONE)

        self.add(box)

        self.show_all()

        self.connect("toggled", self._on_gtk_select_preset)

    def _on_gtk_select_preset(self, *_, **__):
        logger.debug('Selecting preset "%s"', self.preset_name)
        self._controller.load_preset(self.preset_name)
        self.message_broker.send(DoStackSwitch(Stack.editor_page))

    def show_active(self, active):
        """Show the active state without triggering anything."""
        with HandlerDisabled(self, self._on_gtk_select_preset):
            self.set_active(active)


# TODO test
class PresetSelectionTitle:
    """The title of the preset selection, which is the device name."""

    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        label: Gtk.Label,
    ):
        self._message_broker = message_broker
        self._controller = controller
        self._gui = label
        self._connect_message_listener()
        label.set_max_width_chars(50)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(2)

    def _connect_message_listener(self):
        self._message_broker.subscribe(MessageType.group, self._on_group_changed)

    def _on_group_changed(self, data: GroupData):
        self._gui.set_label(data.group_key)


# TODO test
class EditorTitle:
    """The title of the editor, which is the device and preset name."""

    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        label: Gtk.Label,
    ):
        self._message_broker = message_broker
        self._controller = controller
        self._gui = label
        self._connect_message_listener()

        self._group_key: str = ""
        self._preset_name: str = ""

        label.set_max_width_chars(50)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(2)

    def _connect_message_listener(self):
        self._message_broker.subscribe(MessageType.group, self._on_group_changed)
        self._message_broker.subscribe(MessageType.preset, self._on_preset_changed)

    def _on_preset_changed(self, data: PresetData):
        self._preset_name = data.name or ""
        self._render()

    def _on_group_changed(self, data: GroupData):
        self._group_key = data.group_key
        self._render()

    def _render(self):
        self._gui.set_label(f"{self._group_key} / {self._preset_name}")


class PresetSelection:
    """A wrapper for the container with our presets.

    Selectes the active_preset.
    """

    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        flowbox: Gtk.FlowBox,
    ):
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
        self.show_active_preset(data.name)

    def set_active_preset(self, preset_name: str):
        """Change the currently selected preset."""
        # TODO might only be needed in tests
        for child in self._gui.get_children():
            preset_entry: PresetEntry = child.get_children()[0]
            preset_entry.set_active(preset_entry.preset_name == preset_name)

    def show_active_preset(self, preset_name: str):
        """Highlight the button of the given preset."""
        for child in self._gui.get_children():
            preset_entry: PresetEntry = child.get_children()[0]
            preset_entry.show_active(preset_entry.preset_name == preset_name)


class MappingListBox:
    """the listbox showing all available mapping in the active_preset"""

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
            selection_label = MappingSelectionLabel(
                self._message_broker,
                self._controller,
                name,
                combination,
            )
            self._gui.insert(selection_label, -1)
        self._gui.invalidate_sort()

    def _on_mapping_changed(self, mapping: MappingData):
        with HandlerDisabled(self._gui, self._on_gtk_mapping_selected):
            combination = mapping.event_combination

            def set_active(row: MappingSelectionLabel):
                if row.combination == combination:
                    self._gui.select_row(row)

            self._gui.foreach(set_active)

    def _on_gtk_mapping_selected(self, _, row: Optional[MappingSelectionLabel]):
        if not row:
            return
        self._controller.load_mapping(row.combination)


class MappingSelectionLabel(Gtk.ListBoxRow):
    """the ListBoxRow representing a mapping inside the MappingListBox"""

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

        self.label.set_margin_top(11)
        self.label.set_margin_bottom(11)

        # button to edit the name of the mapping
        self.edit_btn = Gtk.Button()
        self.edit_btn.set_relief(Gtk.ReliefStyle.NONE)
        self.edit_btn.set_image(
            Gtk.Image.new_from_icon_name("text-x-generic", Gtk.IconSize.MENU)
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
        self.name_input.connect("key-press-event", self._on_gtk_rename_abort)

        self._box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self._box.set_center_widget(self.label)
        self._box.add(self.edit_btn)
        self._box.set_child_packing(self.edit_btn, False, False, 4, Gtk.PackType.END)
        self._box.add(self.name_input)
        self._box.set_child_packing(self.name_input, False, True, 4, Gtk.PackType.START)

        self.add(self._box)

        self.set_margin_bottom(6)

        self.show_all()
        self._message_broker.subscribe(MessageType.mapping, self._on_mapping_changed)
        self._message_broker.subscribe(
            MessageType.combination_update, self._on_combination_update
        )

        self.edit_btn.hide()
        self.name_input.hide()

    def __repr__(self):
        return f"MappingSelectionLabel for {self.combination} as {self.name}"

    @property
    def name(self) -> str:
        if (
            self.combination == EventCombination.empty_combination()
            or self.combination is None
        ):
            return EMPTY_MAPPING_NAME
        return self._name or self.combination.beautify()

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

    def _on_gtk_rename_abort(self, _, key_event: Gdk.EventKey):
        logger.error("called")
        if key_event.keyval == Gdk.KEY_Escape:
            self._set_selected()

    def cleanup(self) -> None:
        """clean up message listeners. Execute before removing from gui!"""
        self._message_broker.unsubscribe(self._on_mapping_changed)
        self._message_broker.unsubscribe(self._on_combination_update)


class CodeEditor:
    """the editor used to edit the output_symbol of the active_mapping"""

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
    """the toggle used to record the input form the active_group in order to update the
    event_combination of the active_mapping"""

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
    """the status bar on the bottom of the main window"""

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
    """the switch used to toggle the autoload state of the active_preset for
    the acive_group"""

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
    """the switch used to set the active_mapping.release_combination_keys parameter"""

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

    def cleanup(self):
        """Remove any message listeners we are about to get destroyed."""
        pass


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
    """the switch used to modify the active_event in order to be
    marked as an analog input"""

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
    """the number selection used to set the speed or position threshold of the
    active_event when it is an ABS or REL event used as a key"""

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
    """the number selector used to set the active_mapping.release_timeout parameter"""

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
    """the number selector to set active_mapping.rel_input_cutoff"""

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
            self._gui.set_value(mapping.rel_input_cutoff)

    def _on_gtk_changed(self, *_):
        self._controller.update_mapping(rel_input_cutoff=self._gui.get_value())


class OutputAxisSelector:
    """the dropdown menu used to select the output axis if the active_mapping is a
    mapping targeting an analog axis

    modifies the active_mapping.output_code and active_mapping.output_type parameters
    """

    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        gui: Gtk.listbox,
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
        self.model.append([f"None, None", _("No Axis")])
        for type, code in types_codes:

            key_name = bytype[type][code]
            if isinstance(key_name, list):
                key_name = key_name[0]
            self.model.append([f"{type}, {code}", key_name])

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
    """the dialog shown to the user to query a confirm or cancel action form the user"""

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


class KeyAxisStackSwitcher:
    """the controls used to switch between the gui to modify a key-mapping or
    an analog-axis mapping"""

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

        try:
            if btn is self._key_macro_toggle:
                self._controller.update_mapping(mapping_type="key_macro")
            else:
                self._controller.update_mapping(mapping_type="analog")
        except NoMappingError:
            # Revert the button active state, otherwise the guard on top will prevent
            # the function from doing anything forever
            with HandlerDisabled(btn, self._on_gtk_toggle):
                btn.set_active(was_active)


class TransformationDrawArea:
    """the graph which shows the relation between input- and output-axis"""

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
    """the different sliders to modify the gain, deadzone and expo parameters of the
    active_mapping"""

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
