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


"""The editor with multiline code input, recording toggle and autocompletion."""


import re
import locale
import gettext
import os
import time
from typing import Optional

from inputremapper.configs.mapping import UIMapping

from gi.repository import Gtk, GLib, Gdk, GtkSource
from inputremapper.gui.gettext import _
from inputremapper.gui.editor.autocompletion import Autocompletion
from inputremapper.configs.system_mapping import system_mapping
from inputremapper.gui.active_preset import active_preset
from inputremapper.event_combination import EventCombination
from inputremapper.input_event import InputEvent
from inputremapper.logger import logger

from inputremapper.gui.utils import CTX_KEYCODE, CTX_WARNING, CTX_ERROR


class CombinationEntry(Gtk.ListBoxRow):
    """One row per InputEvent in the EventCombination."""

    __gtype_name__ = "CombinationEntry"

    def __init__(self, event: InputEvent):
        super().__init__()

        self.event = event
        hbox = Gtk.Box(Gtk.Orientation.HORIZONTAL, spacing=4)

        label = Gtk.Label()
        label.set_label(event.json_str())
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

        self.add(hbox)
        self.show_all()


def ensure_everything_saved(func):
    """Make sure the editor has written its changes to active_preset and save."""

    def wrapped(self, *args, **kwargs):
        if self.user_interface.preset_name:
            # self.gather_changes_and_save()
            pass

        return func(self, *args, **kwargs)

    return wrapped


RECORD_ALL = float("inf")
RECORD_NONE = 0


class Editor:
    """Maintains the widgets of the editor."""

    def __init__(self, user_interface):
        self.user_interface = user_interface

        self.autocompletion = None

        self.active_mapping: Optional[UIMapping] = None

        # self._setup_source_view()
        # self._setup_recording_toggle()

        self.window = self.get("window")
        self.timeouts = [
            GLib.timeout_add(100, self.check_add_new_key),
            GLib.timeout_add(1000, self.update_toggle_opacity),
        ]
        self.active_selection_label = None

        # selection_label_listbox = self.get("selection_label_listbox")
        # selection_label_listbox.connect("row-selected", self.on_mapping_selected)

        self.device = user_interface.group

        # keys were not pressed yet
        self._input_has_arrived = False

        self.record_events_until = RECORD_NONE

        # code_editor = self.get_code_editor()
        # code_editor.connect("focus-out-event", self.on_text_input_unfocus)
        # code_editor.get_buffer().connect("changed", self.on_text_input_changed)

        # delete_button = self.get_delete_button()
        # delete_button.connect("clicked", self._on_delete_button_clicked)

    def __del__(self):
        for timeout in self.timeouts:
            GLib.source_remove(timeout)
            self.timeouts = []

    def _on_toggle_clicked(self, toggle, event=None):
        if toggle.get_active():
            self._show_press_key()
        else:
            self._show_change_key()

    @ensure_everything_saved
    def _on_toggle_unfocus(self, toggle, event=None):
        toggle.set_active(False)

    @ensure_everything_saved
    def on_text_input_unfocus(self, *_):
        """When unfocusing the text it saves.

        Input Remapper doesn't save the editor on change, because that would cause
        an incredible amount of logs for every single input. The active_preset would
        need to be changed, which causes two logs, then it has to be saved
        to disk which is another two log messages. So every time a single character
        is typed it writes 4 lines.

        Instead, it will save the preset when it is really needed, i.e. when a button
        that requires a saved preset is pressed. For this there exists the
        @ensure_everything_saved decorator.

        To avoid maybe forgetting to add this decorator somewhere, it will also save
        when unfocusing the text input.

        If the scroll wheel is used to interact with gtk widgets it won't unfocus,
        so this focus-out handler is not the solution to everything as well.

        One could debounce saving on text-change to avoid those logs, but that just
        sounds like a huge source of race conditions and is also hard to test.
        """
        pass  # the decorator will be triggered

    def _on_target_input_changed(self, *_):
        """Save when target changed."""
        self.active_mapping.target_uinput = self.get_target_selection()
        self.gather_changes_and_save()

    def clear(self):
        """Clear all inputs, labels, etc. Reset the state.

        This is really important to do before loading a different preset.
        Otherwise the inputs will be read and then saved into the next preset.
        """
        if self.active_selection_label:
            self.set_combination(None)

        self._reset_keycode_consumption()

        self.clear_mapping_list()

    def clear_mapping_list(self):
        """Clear the labels from the mapping selection and add an empty one."""
        logger.debug("deprecated")
        return
        selection_label_listbox = self.get("selection_label_listbox")
        selection_label_listbox.forall(selection_label_listbox.remove)
        self.add_empty()
        selection_label_listbox.select_row(selection_label_listbox.get_children()[0])

    def _setup_recording_toggle(self):
        """Prepare the toggle button for recording key inputs."""
        toggle = self.get_recording_toggle()
        toggle.connect("focus-out-event", self._show_change_key)
        toggle.connect("focus-in-event", self._show_press_key)
        toggle.connect("clicked", self._on_toggle_clicked)
        toggle.connect("focus-out-event", self._reset_keycode_consumption)
        toggle.connect("focus-out-event", self._on_toggle_unfocus)
        toggle.connect("toggled", self._on_recording_toggle_toggle)
        # Don't leave the input when using arrow keys or tab. wait for the
        # window to consume the keycode from the reader. I.e. a tab input should
        # be recorded, instead of causing the recording to stop.
        toggle.connect("key-press-event", lambda *args: Gdk.EVENT_STOP)

    def _show_press_key(self, *args):
        """Show user friendly instructions."""
        self.get_recording_toggle().set_label(_("Press Key"))

    def _show_change_key(self, *args):
        """Show user friendly instructions."""
        self.get_recording_toggle().set_label(_("Change Key"))

    def check_add_new_key(self):
        """If needed, add a new empty mapping to the list for the user to configure."""
        logger.debug("deprecated")
        return
        selection_label_listbox = self.get("selection_label_listbox")

        selection_label_listbox = selection_label_listbox.get_children()

        for selection_label in selection_label_listbox:
            combination = selection_label.get_combination()
            if (
                combination is None
                or active_preset.get_mapping(combination) is None
                or not active_preset.get_mapping(combination).is_valid()
            ):
                # unfinished row found
                break
        else:
            self.add_empty()

        return True

    @ensure_everything_saved
    def on_mapping_selected(self, _=None, selection_label=None):
        """One of the buttons in the left "combination" column was clicked.

        Load the information from that mapping entry into the editor.
        """
        self.active_selection_label = selection_label

        if selection_label is None:
            return

        combination = selection_label.combination
        self.set_combination(combination)

        if combination is None:
            # the empty mapping was selected
            self.active_mapping = UIMapping()
            # active_preset.add(self.active_mapping)
            # self.disable_symbol_input(clear=True)
            self.active_mapping.target_uinput = "keyboard"
            # target input disabled until a combination is configured
            # symbol input disabled until a combination is configured
        else:
            mapping = active_preset.get_mapping(combination)
            if mapping is not None:
                self.active_mapping = mapping
                self.set_symbol_input_text(mapping.output_symbol)
            # self.enable_symbol_input()

        self.get("window").set_focus(self.get_code_editor())

    def add_empty(self):
        """Add one empty row for a single mapped key."""
        logger.debug("deprecated")
        return
        selection_label_listbox = self.get("selection_label_listbox")
        mapping_selection = SelectionLabel()
        mapping_selection.set_label(_("new entry"))
        mapping_selection.show_all()
        selection_label_listbox.insert(mapping_selection, -1)

    @ensure_everything_saved
    def load_custom_mapping(self):
        """Display the entries in active_preset."""
        logger.debug("deprecated")
        return
        selection_label_listbox = self.get("selection_label_listbox")

        selection_label_listbox.forall(selection_label_listbox.remove)

        for mapping in active_preset:
            selection_label = SelectionLabel()
            selection_label.set_combination(mapping.event_combination)
            selection_label_listbox.insert(selection_label, -1)

        self.check_add_new_key()

        # select the first entry
        selection_labels = selection_label_listbox.get_children()

        if len(selection_labels) == 0:
            self.add_empty()
            selection_labels = selection_label_listbox.get_children()

        selection_label_listbox.select_row(selection_labels[0])

    def get_recording_toggle(self) -> Gtk.ToggleButton:
        return self.get("key_recording_toggle")

    def get_code_editor(self) -> GtkSource.View:
        return self.get("code_editor")

    def get_target_selector(self) -> Gtk.ComboBox:
        return self.get("target-selector")

    def get_combination_listbox(self) -> Gtk.ListBox:
        return self.get("combination-listbox")

    def get_add_axis_btn(self) -> Gtk.Button:
        return self.get("add-axis-as-btn")

    def get_delete_button(self) -> Gtk.Button:
        return self.get("delete-mapping")

    def set_combination(self, combination):
        """Show what the user is currently pressing in the user interface."""
        self.active_selection_label.set_combination(combination)
        listbox = self.get_combination_listbox()
        listbox.forall(listbox.remove)

        if combination:
            for event in combination:
                listbox.insert(CombinationEntry(event), -1)

    def get_combination(self):
        """Get the EventCombination object from the left column.

        Or None if no code is mapped on this row.
        """
        if self.active_selection_label is None:
            return None

        return self.active_selection_label.combination

    def set_symbol_input_text(self, symbol):
        code_editor = self.get_code_editor()
        code_editor.get_buffer().set_text(symbol or "")
        # move cursor location to the beginning, like any code editor does
        Gtk.TextView.do_move_cursor(
            code_editor,
            Gtk.MovementStep.BUFFER_ENDS,
            -1,
            False,
        )

    def get_target_selection(self):
        return self.get_target_selector().get_active_id()

    def get(self, name):
        """Get a widget from the window."""
        return self.user_interface.builder.get_object(name)

    def update_toggle_opacity(self):
        """If the key can't be mapped, grey it out.

        During injection, when the device is grabbed and weird things are being
        done, it is not possible.
        """
        toggle = self.get_recording_toggle()
        if not self.user_interface.can_modify_preset():
            toggle.set_opacity(0.4)
        else:
            toggle.set_opacity(1)

        return True

    def _on_recording_toggle_toggle(self, toggle):
        """Refresh useful usage information."""
        if not toggle.get_active():
            # if more events arrive from the time when the toggle was still on,
            # use them.
            self.record_events_until = time.time()
            return

        self.record_events_until = RECORD_ALL

        self._reset_keycode_consumption()
        reader.clear()
        if not self.user_interface.can_modify_preset():
            # because the device is in grab mode by the daemon and
            # therefore the original keycode inaccessible
            logger.info("Cannot change keycodes while injecting")
            self.user_interface.show_status(
                CTX_ERROR, _('Use "Stop Injection" to stop before editing')
            )
            toggle.set_active(False)

    def _on_delete_button_clicked(self, *_):
        """Destroy the row and remove it from the config."""
        accept = Gtk.ResponseType.ACCEPT
        if (
            len(self.get_symbol_input_text()) > 0
            and self._show_confirm_delete() != accept
        ):
            return

        combination = self.get_combination()
        if combination is not None:
            active_preset.remove(combination)

        # make sure there is no outdated information lying around in memory
        self.set_combination(None)

        self.load_custom_mapping()

    def _show_confirm_delete(self):
        """Blocks until the user decided about an action."""
        confirm_delete = self.get("confirm-delete")

        text = _("Are you sure to delete this mapping?")
        self.get("confirm-delete-label").set_text(text)

        confirm_delete.show()
        response = confirm_delete.run()
        confirm_delete.hide()
        return response

    def is_waiting_for_input(self):
        """Check if the user is trying to record buttons."""
        return self.get_recording_toggle().get_active()

    def should_record_combination(self, combination):
        """Check if the combination was written when the toggle was active."""
        # At this point the toggle might already be off, because some keys that are
        # used while the toggle was still on might cause the focus of the toggle to
        # be lost, like multimedia keys. This causes the toggle to be disabled.
        # Yet, this event should be mapped.
        timestamp = max([event.timestamp() for event in combination])
        return timestamp < self.record_events_until

    def consume_newest_keycode(self, combination: EventCombination):
        """To capture events from keyboards, mice and gamepads."""
        self._switch_focus_if_complete()

        if combination is None:
            return

        if not self.should_record_combination(combination):
            # the event arrived after the toggle has been deactivated
            logger.debug("Recording toggle is not on")
            return

        if not isinstance(combination, EventCombination):
            raise TypeError("Expected new_key to be a EventCombination object")

        # keycode is already set by some other row
        existing = active_preset.get_mapping(combination)
        if existing is not None:
            msg = _('"%s" already mapped to "%s"') % (
                combination.beautify(),
                existing.event_combination.beautify(),
            )
            logger.info("%s %s", combination, msg)
            self.user_interface.show_status(CTX_KEYCODE, msg)
            return

        if combination.is_problematic():
            self.user_interface.show_status(
                CTX_WARNING,
                _("ctrl, alt and shift may not combine properly"),
                _("Your system might reinterpret combinations ")
                + _("with those after they are injected, and by doing so ")
                + _("break them."),
            )

        # the newest_keycode is populated since the ui regularly polls it
        # in order to display it in the status bar.
        previous_key = self.get_combination()

        # it might end up being a key combination, wait for more
        self._input_has_arrived = True

        # keycode didn't change, do nothing
        if combination == previous_key:
            logger.debug("%s didn't change", previous_key)
            return

        self.set_combination(combination)
        self.active_mapping.event_combination = combination
        if previous_key is None and combination is not None:
            logger.debug(f"adding new mapping to preset\n{self.active_mapping}")
            active_preset.add(self.active_mapping)

    def _switch_focus_if_complete(self):
        """If keys are released, it will switch to the text_input.

        States:
        1. not doing anything, waiting for the user to start using it
        2. user focuses it, no keys pressed
        3. user presses keys
        4. user releases keys. no keys are pressed, just like in step 2, but this time
        the focus needs to switch.
        """
        if not self.is_waiting_for_input():
            self._reset_keycode_consumption()
            return

        all_keys_released = reader.get_unreleased_keys() is None
        if all_keys_released and self._input_has_arrived and self.get_combination():
            logger.debug("Recording complete")
            # A key was pressed and then released.
            # Switch to the symbol. idle_add this so that the
            # keycode event won't write into the symbol input as well.
            window = self.user_interface.window
            # self.enable_symbol_input()
            GLib.idle_add(lambda: window.set_focus(self.get_code_editor()))

        if not all_keys_released:
            # currently the user is using the widget, and certain keys have already
            # reached it.
            self._input_has_arrived = True
            return

        self._reset_keycode_consumption()

    def _reset_keycode_consumption(self, *_):
        self._input_has_arrived = False
