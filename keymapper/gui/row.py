#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@sezanzeb.de>
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
from gi.repository import Gtk, GLib, Gdk

from keymapper.state import custom_mapping, system_mapping
from keymapper.logger import logger
from keymapper.key import Key
from keymapper.gui.reader import keycode_reader


CTX_KEYCODE = 2


store = Gtk.ListStore(str)
for name in system_mapping.list_names():
    store.append([name])


def to_string(key):
    """A nice to show description of the pressed key."""
    if isinstance(key, Key):
        return ' + '.join([to_string(sub_key) for sub_key in key])

    if isinstance(key[0], tuple):
        raise Exception('deprecated stuff')

    ev_type, code, value = key

    if ev_type not in evdev.ecodes.bytype:
        logger.error('Unknown key type for %s', key)
        return 'unknown'

    if code not in evdev.ecodes.bytype[ev_type]:
        logger.error('Unknown key code for %s', key)
        return 'unknown'

    key_name = evdev.ecodes.bytype[ev_type][code]
    if isinstance(key_name, list):
        key_name = key_name[0]

    if ev_type != evdev.ecodes.EV_KEY:
        direction = {
            # D-Pad
            (evdev.ecodes.ABS_HAT0X, -1): 'L',
            (evdev.ecodes.ABS_HAT0X, 1): 'R',
            (evdev.ecodes.ABS_HAT0Y, -1): 'U',
            (evdev.ecodes.ABS_HAT0Y, 1): 'D',
            (evdev.ecodes.ABS_HAT1X, -1): 'L',
            (evdev.ecodes.ABS_HAT1X, 1): 'R',
            (evdev.ecodes.ABS_HAT1Y, -1): 'U',
            (evdev.ecodes.ABS_HAT1Y, 1): 'D',
            (evdev.ecodes.ABS_HAT2X, -1): 'L',
            (evdev.ecodes.ABS_HAT2X, 1): 'R',
            (evdev.ecodes.ABS_HAT2Y, -1): 'U',
            (evdev.ecodes.ABS_HAT2Y, 1): 'D',
            # joystick
            (evdev.ecodes.ABS_X, 1): 'R',
            (evdev.ecodes.ABS_X, -1): 'L',
            (evdev.ecodes.ABS_Y, 1): 'D',
            (evdev.ecodes.ABS_Y, -1): 'U',
            (evdev.ecodes.ABS_RX, 1): 'R',
            (evdev.ecodes.ABS_RX, -1): 'L',
            (evdev.ecodes.ABS_RY, 1): 'D',
            (evdev.ecodes.ABS_RY, -1): 'U',
            # wheel
            (evdev.ecodes.REL_WHEEL, -1): 'D',
            (evdev.ecodes.REL_WHEEL, 1): 'U',
            (evdev.ecodes.REL_HWHEEL, -1): 'L',
            (evdev.ecodes.REL_HWHEEL, 1): 'R',
        }.get((code, value))
        if direction is not None:
            key_name += f' {direction}'

    return key_name.replace('KEY_', '')


IDLE = 0
HOLDING = 1


class Row(Gtk.ListBoxRow):
    """A single, configurable key mapping."""
    __gtype_name__ = 'ListBoxRow'

    def __init__(self, delete_callback, window, key=None, character=None):
        """Construct a row widget.

        Parameters
        ----------
        key : Key
        """
        if key is not None and not isinstance(key, Key):
            raise TypeError('Expected key to be a Key object')

        super().__init__()
        self.device = window.selected_device
        self.window = window
        self.delete_callback = delete_callback

        self.character_input = None
        self.keycode_input = None

        self.key = key

        self.put_together(character)

        self._state = IDLE

    def refresh_state(self):
        """Refresh the state.

        The state is needed to switch focus when no keys are held anymore,
        but only if the row has been in the HOLDING state before.
        """
        old_state = self._state

        if not self.keycode_input.is_focus():
            self._state = IDLE
            return

        unreleased_keys = keycode_reader.get_unreleased_keys()
        if unreleased_keys is None and old_state == HOLDING and self.key:
            # A key was pressed and then released.
            # Switch to the character. idle_add this so that the
            # keycode event won't write into the character input as well.
            window = self.window.window
            GLib.idle_add(lambda: window.set_focus(self.character_input))

        if unreleased_keys is not None:
            self._state = HOLDING
            return

        self._state = IDLE

    def get_key(self):
        """Get the Key object from the left column.

        Or None if no code is mapped on this row.
        """
        return self.key

    def get_character(self):
        """Get the assigned character from the middle column."""
        character = self.character_input.get_text()
        return character if character else None

    def set_new_key(self, new_key):
        """Check if a keycode has been pressed and if so, display it.

        Parameters
        ----------
        new_key : Key
        """
        if new_key is not None and not isinstance(new_key, Key):
            raise TypeError('Expected new_key to be a Key object')

        # the newest_keycode is populated since the ui regularly polls it
        # in order to display it in the status bar.
        previous_key = self.get_key()

        # no input
        if new_key is None:
            return

        # it might end up being a key combination
        self._state = HOLDING

        # keycode didn't change, do nothing
        if new_key == previous_key:
            return

        # keycode is already set by some other row
        existing = custom_mapping.get_character(new_key)
        if existing is not None:
            msg = f'"{to_string(new_key)}" already mapped to "{existing}"'
            logger.info(msg)
            self.window.show_status(CTX_KEYCODE, msg)
            return

        # it's legal to display the keycode

        # always ask for get_child to set the label, otherwise line breaking
        # has to be configured again.
        self.set_keycode_input_label(to_string(new_key))

        self.key = new_key

        self.highlight()

        character = self.get_character()

        # the character is empty and therefore the mapping is not complete
        if character is None:
            return

        # else, the keycode has changed, the character is set, all good
        custom_mapping.change(
            new_key=new_key,
            character=character,
            previous_key=previous_key
        )

    def highlight(self):
        """Mark this row as changed."""
        self.get_style_context().add_class('changed')

    def unhighlight(self):
        """Mark this row as unchanged."""
        self.get_style_context().remove_class('changed')

    def on_character_input_change(self, _):
        """When the output character for that keycode is typed in."""
        key = self.get_key()
        character = self.get_character()

        if character is None:
            return

        self.highlight()

        if key is not None:
            custom_mapping.change(
                new_key=key,
                character=character,
                previous_key=None
            )

    def match(self, _, key, tree_iter):
        """Search the avilable names."""
        value = store.get_value(tree_iter, 0)
        return key in value.lower()

    def show_click_here(self):
        """Show 'click here' on the keycode input button."""
        if self.get_key() is not None:
            return

        self.set_keycode_input_label('click here')
        self.keycode_input.set_opacity(0.3)

    def show_press_key(self):
        """Show 'press key' on the keycode input button."""
        if self.get_key() is not None:
            return

        self.set_keycode_input_label('press key')
        self.keycode_input.set_opacity(1)

    def on_keycode_input_focus(self, *_):
        """Refresh useful usage information."""
        keycode_reader.clear()
        self.show_press_key()
        self.window.can_modify_mapping()

    def on_keycode_input_unfocus(self, *_):
        """Refresh useful usage information and set some state stuff."""
        self.show_click_here()
        self.keycode_input.set_active(False)
        self._state = IDLE
        keycode_reader.clear()

    def set_keycode_input_label(self, label):
        """Set the label of the keycode input."""
        self.keycode_input.set_label(label)
        # make the child label widget break lines, important for
        # long combinations
        label = self.keycode_input.get_child()
        label.set_line_wrap(True)
        label.set_line_wrap_mode(2)
        label.set_max_width_chars(13)
        label.set_justify(Gtk.Justification.CENTER)

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
        self.keycode_input = keycode_input
        keycode_input.set_size_request(140, -1)

        if self.key is not None:
            self.set_keycode_input_label(to_string(self.key))
        else:
            self.show_click_here()

        # make the togglebutton go back to its normal state when doing
        # something else in the UI
        keycode_input.connect(
            'focus-in-event',
            self.on_keycode_input_focus
        )
        keycode_input.connect(
            'focus-out-event',
            self.on_keycode_input_unfocus
        )
        # don't leave the input when using arrow keys or tab. wait for the
        # window to consume the keycode from the reader
        keycode_input.connect(
            'key-press-event',
            lambda *args: Gdk.EVENT_STOP
        )

        character_input = Gtk.Entry()
        self.character_input = character_input
        character_input.set_alignment(0.5)
        character_input.set_width_chars(4)
        character_input.set_has_frame(False)
        completion = Gtk.EntryCompletion()
        completion.set_model(store)
        completion.set_text_column(0)
        completion.set_match_func(self.match)
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

    def on_delete_button_clicked(self, *_):
        """Destroy the row and remove it from the config."""
        key = self.get_key()
        if key is not None:
            custom_mapping.clear(key)

        self.character_input.set_text('')
        self.set_keycode_input_label('')
        self.key = None
        self.delete_callback(self)
