#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2020 sezanzeb <proxima@hip70890b.de>
#
# This file is part of key-mapper.
#
# key-mapper is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# key-mapper is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with key-mapper.  If not, see <https://www.gnu.org/licenses/>.


"""A single, configurable key mapping."""


import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GLib', '2.0')
from gi.repository import Gtk, GLib
import cairo as Cairo

from keymapper.mapping import custom_mapping
from keymapper.logger import logger
from keymapper.linux import keycode_reader


CTX_KEYCODE = 2


class Row:
    """A single, configurable key mapping."""
    def __init__(self, delete_callback, window, keycode=None, character=None):
        """Construct a row widget."""
        self.widget = None
        self.device = window.selected_device
        self.window = window
        self.delete_callback = delete_callback
        self.put_together(keycode, character)

    def get_widget(self):
        """Return the widget that wraps all the widgets of the row."""
        return self.widget

    def get_keycode(self):
        keycode = self.keycode.get_label()
        return int(keycode) if keycode else None

    def get_character(self):
        character = self.character_input.get_text()
        return character if character else None

    def start_watching_keycodes(self, *args):
        """Start to periodically check if a keycode has been pressed.

        This is different from just listening for text input events
        (as in Gtk.Entry), since keys may not write characters into the form
        because they are not mapped. Furthermore their keycode is needed,
        not their mapped character."""
        keycode_reader.clear()

        def iterate():
            self.check_newest_keycode()
            return self.keycode.is_focus() and self.window.window.is_active()

        GLib.timeout_add(1000 / 30, iterate)

    def check_newest_keycode(self):
        """Check if a keycode has been pressed and if so, display it."""
        new_keycode = keycode_reader.read()
        previous_keycode = self.get_keycode()
        character = self.get_character()

        # no input
        if new_keycode is None:
            return

        # keycode didn't change, do nothing
        if new_keycode == previous_keycode:
            return

        # keycode is already set by some other row
        if custom_mapping.get(new_keycode) is not None:
            msg = f'Keycode {new_keycode} is already mapped'
            logger.info(msg)
            self.window.get('status_bar').push(CTX_KEYCODE, msg)
            return
        # it's legal to display the keycode
        self.window.get('status_bar').remove_all(CTX_KEYCODE)
        self.keycode.set_label(str(new_keycode))
        # switch to the character, don't require mouse input because
        # that would overwrite the key with the mouse-button key if
        # the current device is a mouse
        self.window.window.set_focus(self.character_input)
        self.highlight()

        # the character is empty and therefore the mapping is not complete
        if character is None:
            return

        # else, the keycode has changed, the character is set, all good
        custom_mapping.change(previous_keycode, new_keycode, character)

    def highlight(self):
        """Mark this row as changed."""
        self.widget.get_style_context().add_class('changed')

    def on_character_input_change(self, entry):
        keycode = self.get_keycode()
        character = self.get_character()

        self.highlight()

        if keycode is not None:
            custom_mapping.change(None, keycode, character)

    def put_together(self, keycode, character):
        """Create all GTK widgets."""
        delete_button = Gtk.EventBox()
        delete_button.add(Gtk.Image.new_from_icon_name(
            'window-close',
            Gtk.IconSize.BUTTON
        ))
        delete_button.connect(
            'button-press-event',
            self.on_delete_button_clicked
        )
        delete_button.set_margin_start(5)
        delete_button.set_margin_end(5)

        keycode_input = Gtk.ToggleButton()
        if keycode is not None:
            keycode_input.set_label(str(keycode))
        keycode_input.connect(
            'focus-in-event',
            self.start_watching_keycodes
        )
        # make the togglebutton go back to its normal state when doing
        # something else in the UI
        keycode_input.connect(
            'focus-out-event',
            lambda *args: keycode_input.set_active(False)
        )

        character_input = Gtk.Entry()
        character_input.set_alignment(0.5)
        character_input.set_width_chars(4)
        character_input.set_has_frame(False)
        if character is not None:
            character_input.set_text(character)
        character_input.connect(
            'changed',
            self.on_character_input_change
        )

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box.set_homogeneous(True)
        box.set_spacing(2)
        box.pack_start(keycode_input, expand=True, fill=True, padding=0)
        box.pack_start(character_input, expand=True, fill=True, padding=0)
        box.pack_start(delete_button, expand=True, fill=False, padding=0)
        box.show_all()

        row = Gtk.ListBoxRow()
        row.add(box)
        row.show_all()

        self.widget = row
        self.character_input = character_input
        self.keycode = keycode_input

    def on_delete_button_clicked(self, *args):
        """Destroy the row and remove it from the config."""
        keycode = self.get_keycode()
        if keycode is not None:
            custom_mapping.clear(keycode)
        self.delete_callback(self)
