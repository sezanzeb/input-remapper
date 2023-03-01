# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2023 sezanzeb <proxima@sezanzeb.de>
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
import time

from gi.repository import Gtk, GLib, Gdk

from inputremapper.gui.gettext import _
from inputremapper.gui.editor.autocompletion import Autocompletion
from inputremapper.configs.system_mapping import system_mapping
from inputremapper.gui.active_preset import active_preset
from inputremapper.event_combination import EventCombination
from inputremapper.logger import logger
from inputremapper.gui.reader import reader
from inputremapper.gui.utils import CTX_KEYCODE, CTX_WARNING, CTX_ERROR
from inputremapper.injection.global_uinputs import global_uinputs


class SelectionLabel(Gtk.ListBoxRow):
    """One label per mapping in the preset.

    This wrapper serves as a storage for the information the inherited label represents.
    """

    __gtype_name__ = "SelectionLabel"

    def __init__(self):
        super().__init__()
        self.combination = None
        self.symbol = ""

        label = Gtk.Label()

        # Make the child label widget break lines, important for
        # long combinations
        label.set_line_wrap(True)
        label.set_line_wrap_mode(2)
        label.set_justify(Gtk.Justification.CENTER)

        self.label = label
        self.add(label)

        self.show_all()

    def set_combination(self, combination: EventCombination):
        """Set the combination this button represents

        Parameters
        ----------
        combination : EventCombination
        """
        self.combination = combination
        if combination:
            self.label.set_label(combination.beautify())
        else:
            self.label.set_label(_("new entry"))

    def get_combination(self) -> EventCombination:
        return self.combination

    def set_label(self, label):
        return self.label.set_label(label)

    def get_label(self):
        return self.label.get_label()

    def __str__(self):
        return f"SelectionLabel({str(self.combination)})"

    def __repr__(self):
        return self.__str__()


def ensure_everything_saved(func):
    """Make sure the editor has written its changes to active_preset and save."""

    def wrapped(self, *args, **kwargs):
        if self.user_interface.preset_name:
            self.gather_changes_and_save()

        return func(self, *args, **kwargs)

    return wrapped


SET_KEY_FIRST = _("Set the key first")

RECORD_ALL = float("inf")
RECORD_NONE = 0


class Editor:
    """Maintains the widgets of the editor."""

    def __init__(self, user_interface):
        self.user_interface = user_interface

        self.autocompletion = None

        self._setup_target_selector()
        self._setup_source_view()
        self._setup_recording_toggle()

        self.window = self.get("window")
        self.timeouts = [
            GLib.timeout_add(100, self.check_add_new_key),
            GLib.timeout_add(1000, self.update_toggle_opacity),
        ]
        self.active_selection_label: SelectionLabel = None

        selection_label_listbox = self.get("selection_label_listbox")
        selection_label_listbox.connect("row-selected", self.on_mapping_selected)

        self.device = user_interface.group

        # keys were not pressed yet
        self._input_has_arrived = False

        self.record_events_until = RECORD_NONE

        text_input = self.get_text_input()
        text_input.connect("focus-out-event", self.on_text_input_unfocus)

        delete_button = self.get_delete_button()
        delete_button.connect("clicked", self._on_delete_button_clicked)

        target_selector = self.get_target_selector()
        target_selector.connect("changed", self._on_target_input_changed)

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
        an incredible amount of logs for every single input. The custom_mapping would
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

    @ensure_everything_saved
    def _on_target_input_changed(self, *_):
        """save when target changed"""
        pass

    def clear(self):
        """Clear all inputs, labels, etc. Reset the state.

        This is really important to do before loading a different preset.
        Otherwise the inputs will be read and then saved into the next preset.
        """
        if self.active_selection_label:
            self.set_combination(None)

        self.disable_symbol_input(clear=True)
        self.set_target_selection("keyboard")  # sane default
        self.disable_target_selector()
        self._reset_keycode_consumption()

        self.clear_mapping_list()

    def clear_mapping_list(self):
        """Clear the labels from the mapping selection and add an empty one."""
        selection_label_listbox = self.get("selection_label_listbox")
        selection_label_listbox.forall(selection_label_listbox.remove)
        self.add_empty()
        selection_label_listbox.select_row(selection_label_listbox.get_children()[0])

    def _setup_target_selector(self):
        """Prepare the target selector combobox"""
        target_store = Gtk.ListStore(str)
        for uinput in global_uinputs.devices:
            target_store.append([uinput])

        target_input = self.get_target_selector()
        target_input.set_model(target_store)
        renderer_text = Gtk.CellRendererText()
        target_input.pack_start(renderer_text, False)
        target_input.add_attribute(renderer_text, "text", 0)
        target_input.set_id_column(0)

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

    def _setup_source_view(self):
        """Prepare the code editor."""
        source_view = self.get("code_editor")

        # without this the wrapping ScrolledWindow acts weird when new lines are added,
        # not offering enough space to the text editor so the whole thing is suddenly
        # scrollable by a few pixels.
        # Found this after making blind guesses with settings in glade, and then
        # actually looking at the snaphot preview! In glades editor this didn have an
        # effect.
        source_view.set_resize_mode(Gtk.ResizeMode.IMMEDIATE)

        source_view.get_buffer().connect("changed", self.show_line_numbers_if_multiline)

        # Syntax Highlighting
        # Thanks to https://github.com/wolfthefallen/py-GtkSourceCompletion-example
        # language_manager = GtkSource.LanguageManager()
        # fun fact: without saving LanguageManager into its own variable it doesn't work
        #  python = language_manager.get_language("python")
        # source_view.get_buffer().set_language(python)
        # TODO there are some similarities with python, but overall it's quite useless.
        #  commented out until there is proper highlighting for input-remappers syntax.

        autocompletion = Autocompletion(source_view, self.get_target_selector())
        autocompletion.set_relative_to(self.get("code_editor_container"))
        autocompletion.connect("suggestion-inserted", self.gather_changes_and_save)
        self.autocompletion = autocompletion

    def show_line_numbers_if_multiline(self, *_):
        """Show line numbers if a macro is being edited."""
        code_editor = self.get("code_editor")
        symbol = self.get_symbol_input_text() or ""

        if "\n" in symbol:
            code_editor.set_show_line_numbers(True)
            code_editor.set_monospace(True)
            code_editor.get_style_context().add_class("multiline")
        else:
            code_editor.set_show_line_numbers(False)
            code_editor.set_monospace(False)
            code_editor.get_style_context().remove_class("multiline")

    def get_delete_button(self):
        return self.get("delete-mapping")

    def check_add_new_key(self):
        """If needed, add a new empty mapping to the list for the user to configure."""
        selection_label_listbox = self.get("selection_label_listbox")

        selection_label_listbox = selection_label_listbox.get_children()

        for selection_label in selection_label_listbox:
            if selection_label.get_combination() is None:
                # unfinished row found
                break
        else:
            self.add_empty()

        return True

    def disable_symbol_input(self, clear=False):
        """Display help information and dont allow entering a symbol.

        Without this, maybe a user enters a symbol or writes a macro, switches
        presets accidentally before configuring the key and then it's gone. It can
        only be saved to the preset if a key is configured. This avoids that pitfall.
        """
        logger.debug("Disabling the text input")
        text_input = self.get_text_input()

        # beware that this also appeared to disable event listeners like
        # focus-out-event:
        text_input.set_sensitive(False)

        text_input.set_opacity(0.5)

        if clear or self.get_symbol_input_text() == "":
            # don't overwrite user input
            self.set_symbol_input_text(SET_KEY_FIRST)

    def enable_symbol_input(self):
        """Don't display help information anymore and allow changing the symbol."""
        logger.debug("Enabling the text input")
        text_input = self.get_text_input()
        text_input.set_sensitive(True)
        text_input.set_opacity(1)

        buffer = text_input.get_buffer()
        symbol = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
        if symbol == SET_KEY_FIRST:
            # don't overwrite user input
            self.set_symbol_input_text("")

    def disable_target_selector(self):
        """don't allow any selection"""
        selector = self.get_target_selector()
        selector.set_sensitive(False)
        selector.set_opacity(0.5)

    def enable_target_selector(self):
        selector = self.get_target_selector()
        selector.set_sensitive(True)
        selector.set_opacity(1)

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
            self.disable_symbol_input(clear=True)
            # default target should fit in most cases
            self.set_target_selection("keyboard")
            # symbol input disabled until a combination is configured
            self.disable_target_selector()
            # symbol input disabled until a combination is configured
        else:
            if active_preset.get_mapping(combination):
                self.set_symbol_input_text(active_preset.get_mapping(combination)[0])
                self.set_target_selection(active_preset.get_mapping(combination)[1])

            self.enable_symbol_input()
            self.enable_target_selector()

        self.get("window").set_focus(self.get_text_input())

    def add_empty(self):
        """Add one empty row for a single mapped key."""
        selection_label_listbox = self.get("selection_label_listbox")
        mapping_selection = SelectionLabel()
        mapping_selection.set_label(_("new entry"))
        mapping_selection.show_all()
        selection_label_listbox.insert(mapping_selection, -1)

    @ensure_everything_saved
    def load_custom_mapping(self):
        """Display the entries in active_preset."""
        selection_label_listbox = self.get("selection_label_listbox")

        selection_label_listbox.forall(selection_label_listbox.remove)

        for key, _ in active_preset:
            selection_label = SelectionLabel()
            selection_label.set_combination(key)
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

    def get_text_input(self):
        return self.get("code_editor")

    def get_target_selector(self):
        return self.get("target-selector")

    def set_combination(self, combination):
        """Show what the user is currently pressing in the user interface."""
        self.active_selection_label.set_combination(combination)

        if combination and len(combination) > 0:
            self.enable_symbol_input()
        else:
            self.disable_symbol_input()

    def get_combination(self):
        """Get the EventCombination object from the left column.

        Or None if no code is mapped on this row.
        """
        if self.active_selection_label is None:
            return None

        return self.active_selection_label.combination

    def set_symbol_input_text(self, symbol):
        self.get("code_editor").get_buffer().set_text(symbol or "")
        # move cursor location to the beginning, like any code editor does
        Gtk.TextView.do_move_cursor(
            self.get("code_editor"),
            Gtk.MovementStep.BUFFER_ENDS,
            -1,
            False,
        )

    def get_symbol_input_text(self):
        """Get the assigned symbol from the text input.

        This might not be stored in active_preset yet, and might therefore also not
        be part of the preset json file yet.

        If there is no symbol, this returns None. This is important for some other
        logic down the road in active_preset or something.
        """
        buffer = self.get("code_editor").get_buffer()
        symbol = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)

        if symbol == SET_KEY_FIRST:
            # not configured yet
            return ""

        return symbol.strip()

    def set_target_selection(self, target):
        selector = self.get_target_selector()
        selector.set_active_id(target)

    def get_target_selection(self):
        return self.get_target_selector().get_active_id()

    def get(self, name):
        """Get a widget from the window"""
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

        key = self.get_combination()
        if key is not None:
            active_preset.clear(key)

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

    def gather_changes_and_save(self, *_):
        """Look into the ui if new changes should be written, and save the preset."""
        # correct case
        symbol = self.get_symbol_input_text()
        target = self.get_target_selection()

        if not symbol or not target:
            return

        correct_case = system_mapping.correct_case(symbol)
        if symbol != correct_case:
            self.get_text_input().get_buffer().set_text(correct_case)

        # make sure the active_preset is up to date
        key = self.get_combination()
        if correct_case and key and target:
            active_preset.change(key, target, correct_case)

        # save to disk if required
        if active_preset.has_unsaved_changes():
            self.user_interface.save_preset()

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
            existing = list(existing)
            existing[0] = re.sub(r"\s", "", existing[0])
            msg = _('"%s" already mapped to "%s"') % (
                combination.beautify(),
                tuple(existing),
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

        symbol = self.get_symbol_input_text()
        target = self.get_target_selection()

        if not symbol:
            # has not been entered yet
            logger.debug("Symbol missing")
            return

        if not target:
            logger.debug("Target missing")
            return

        # else, the keycode has changed, the symbol is set, all good
        active_preset.change(
            new_combination=combination,
            target=target,
            symbol=symbol,
            previous_combination=previous_key,
        )

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
            self.enable_symbol_input()
            self.enable_target_selector()
            GLib.idle_add(lambda: window.set_focus(self.get_text_input()))

        if not all_keys_released:
            # currently the user is using the widget, and certain keys have already
            # reached it.
            self._input_has_arrived = True
            return

        self._reset_keycode_consumption()

    def _reset_keycode_consumption(self, *_):
        self._input_has_arrived = False
