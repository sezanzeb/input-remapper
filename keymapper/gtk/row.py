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


import evdev

from gi.repository import Gtk, GLib

from keymapper.state import custom_mapping, system_mapping
from keymapper.logger import logger


CTX_KEYCODE = 2


store = Gtk.ListStore(str)
for name in system_mapping.list_names():
    store.append([name])


def to_string(ev_type, code):
    """A nice to show description of the pressed key."""
    try:
        name = evdev.ecodes.bytype[ev_type][code]
        if isinstance(name, list):
            name = name[0]
        return name.replace('KEY_', '')
    except KeyError:
        return 'unknown'


class Row(Gtk.ListBoxRow):
    """A single, configurable key mapping."""
    __gtype_name__ = 'ListBoxRow'

    def __init__(
            self, delete_callback, window, ev_type=None, keycode=None,
            character=None
    ):
        """Construct a row widget."""
        super().__init__()
        self.device = window.selected_device
        self.window = window
        self.delete_callback = delete_callback

        self.character_input = None
        self.keycode_input = None

        self.ev_type = ev_type
        self.keycode = keycode

        self.put_together(character)

    def get_keycode(self):
        """Get a tuple of event_type and keycode from the left column.

        Or None if no codes are mapped on this row.
        """
        keycode = self.keycode_input.get_label()
        if not keycode:
            return None

        return self.ev_type, self.keycode

    def get_character(self):
        """Get the assigned character from the middle column."""
        character = self.character_input.get_text()
        return character if character else None

    def set_new_keycode(self, ev_type, new_keycode):
        """Check if a keycode has been pressed and if so, display it."""
        # the newest_keycode is populated since the ui regularly polls it
        # in order to display it in the status bar.
        key = self.get_keycode()
        previous_type = key[0] if key else None
        previous_keycode = key[1] if key else None

        character = self.get_character()

        # no input
        if new_keycode is None:
            return

        # keycode didn't change, do nothing
        if new_keycode == previous_keycode:
            return

        # keycode is already set by some other row
        existing = custom_mapping.get_character(ev_type, new_keycode)
        if existing is not None:
            name = to_string(ev_type, new_keycode)
            msg = f'"{name}" already mapped to {existing}"'
            logger.info(msg)
            self.window.get('status_bar').push(CTX_KEYCODE, msg)
            return

        # it's legal to display the keycode
        self.window.get('status_bar').remove_all(CTX_KEYCODE)
        self.keycode_input.set_label(to_string(ev_type, new_keycode))
        self.ev_type = ev_type
        self.keycode = new_keycode
        # switch to the character, don't require mouse input because
        # that would overwrite the key with the mouse-button key if
        # the current device is a mouse. idle_add this so that the
        # keycode event won't write into the character input as well.
        window = self.window.window
        GLib.idle_add(lambda: window.set_focus(self.character_input))
        self.highlight()

        # the character is empty and therefore the mapping is not complete
        if character is None:
            return

        # else, the keycode has changed, the character is set, all good
        custom_mapping.change(
            new=(ev_type, new_keycode),
            character=character,
            previous=(previous_type, previous_keycode)
        )

    def highlight(self):
        """Mark this row as changed."""
        self.get_style_context().add_class('changed')

    def unhighlight(self):
        """Mark this row as unchanged."""
        self.get_style_context().remove_class('changed')

    def on_character_input_change(self, _):
        """When the output character for that keycode is typed in."""
        key = self.get_keycode()
        character = self.get_character()

        self.highlight()

        if key is not None:
            ev_type, keycode = key
            custom_mapping.change(
                new=(ev_type, keycode),
                character=character,
                previous=(None, None)
            )

    def match(self, completion, key, iter):
        """Search the avilable names."""
        value = store.get_value(iter, 0)
        return key in value.lower()

    def put_together(self, character):
        """Create all child GTK widgets and connect their signals."""
        delete_button = Gtk.EventBox()
        delete_button.add(Gtk.Image.new_from_icon_name(
            'window-close',
            Gtk.IconSize.BUTTON
        ))
        delete_button.connect(
            'button-press-event',
            self.on_delete_button_clicked
        )
        delete_button.set_size_request(50, -1)

        keycode_input = Gtk.ToggleButton()
        keycode_input.set_size_request(130, -1)

        if self.keycode is not None:
            keycode_input.set_label(to_string(self.ev_type, self.keycode))

        # make the togglebutton go back to its normal state when doing
        # something else in the UI
        keycode_input.connect(
            'focus-in-event',
            self.window.can_modify_mapping
        )
        keycode_input.connect(
            'focus-out-event',
            lambda *args: keycode_input.set_active(False)
        )

        character_input = Gtk.Entry()
        character_input.set_alignment(0.5)
        character_input.set_width_chars(4)
        character_input.set_has_frame(False)
        completion = Gtk.EntryCompletion()
        completion.set_model(store)
        completion.set_text_column(0)
        completion.set_match_func(self.match)
        completion.set_popup_single_match(False)
        character_input.set_completion(completion)

        if character is not None:
            character_input.set_text(character)
        character_input.connect(
            'changed',
            self.on_character_input_change
        )

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box.set_homogeneous(False)
        box.set_spacing(0)
        box.pack_start(keycode_input, expand=False, fill=True, padding=0)
        box.pack_start(character_input, expand=True, fill=True, padding=0)
        box.pack_start(delete_button, expand=False, fill=True, padding=0)
        box.show_all()
        box.get_style_context().add_class('row-box')

        self.add(box)
        self.show_all()

        self.character_input = character_input
        self.keycode_input = keycode_input

    def on_delete_button_clicked(self, *args):
        """Destroy the row and remove it from the config."""
        key = self.get_keycode()
        if key is not None:
            ev_type, keycode = key
            custom_mapping.clear(ev_type, keycode)
        self.character_input.set_text('')
        self.keycode_input.set_label('')
        self.delete_callback(self)
