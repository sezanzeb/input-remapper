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

from keymapper.system_mapping import system_mapping
from keymapper.gui.custom_mapping import custom_mapping
from keymapper.logger import logger
from keymapper.key import Key
from keymapper.gui.reader import reader
from keymapper.injection.global_uinputs import global_uinputs
from keymapper.injection.macros.parse import parse, is_this_a_macro


CTX_KEYCODE = 2


store = Gtk.ListStore(str)


def populate_store():
    """Fill the dropdown for key suggestions with values."""
    for name in system_mapping.list_names():
        store.append([name])

    extra = [
        "mouse(up, 1)",
        "mouse(down, 1)",
        "mouse(left, 1)",
        "mouse(right, 1)",
        "wheel(up, 1)",
        "wheel(down, 1)",
        "wheel(left, 1)",
        "wheel(right, 1)",
    ]

    for key in extra:
        # add some more keys to the dropdown list
        store.append([key])


populate_store()


def to_string(key):
    """A nice to show description of the pressed key."""
    if isinstance(key, Key):
        return " + ".join([to_string(sub_key) for sub_key in key])

    if isinstance(key[0], tuple):
        raise Exception("deprecated stuff")

    ev_type, code, value = key

    if ev_type not in evdev.ecodes.bytype:
        logger.error("Unknown key type for %s", key)
        return str(code)

    if code not in evdev.ecodes.bytype[ev_type]:
        logger.error("Unknown key code for %s", key)
        return str(code)

    key_name = None

    # first try to find the name in xmodmap to not display wrong
    # names due to the keyboard layout
    if ev_type == evdev.ecodes.EV_KEY:
        key_name = system_mapping.get_name(code)

    if key_name is None:
        # if no result, look in the linux key constants. On a german
        # keyboard for example z and y are switched, which will therefore
        # cause the wrong letter to be displayed.
        key_name = evdev.ecodes.bytype[ev_type][code]
        if isinstance(key_name, list):
            key_name = key_name[0]

    if ev_type != evdev.ecodes.EV_KEY:
        direction = {
            # D-Pad
            (evdev.ecodes.ABS_HAT0X, -1): "Left",
            (evdev.ecodes.ABS_HAT0X, 1): "Right",
            (evdev.ecodes.ABS_HAT0Y, -1): "Up",
            (evdev.ecodes.ABS_HAT0Y, 1): "Down",
            (evdev.ecodes.ABS_HAT1X, -1): "Left",
            (evdev.ecodes.ABS_HAT1X, 1): "Right",
            (evdev.ecodes.ABS_HAT1Y, -1): "Up",
            (evdev.ecodes.ABS_HAT1Y, 1): "Down",
            (evdev.ecodes.ABS_HAT2X, -1): "Left",
            (evdev.ecodes.ABS_HAT2X, 1): "Right",
            (evdev.ecodes.ABS_HAT2Y, -1): "Up",
            (evdev.ecodes.ABS_HAT2Y, 1): "Down",
            # joystick
            (evdev.ecodes.ABS_X, 1): "Right",
            (evdev.ecodes.ABS_X, -1): "Left",
            (evdev.ecodes.ABS_Y, 1): "Down",
            (evdev.ecodes.ABS_Y, -1): "Up",
            (evdev.ecodes.ABS_RX, 1): "Right",
            (evdev.ecodes.ABS_RX, -1): "Left",
            (evdev.ecodes.ABS_RY, 1): "Down",
            (evdev.ecodes.ABS_RY, -1): "Up",
            # wheel
            (evdev.ecodes.REL_WHEEL, -1): "Down",
            (evdev.ecodes.REL_WHEEL, 1): "Up",
            (evdev.ecodes.REL_HWHEEL, -1): "Left",
            (evdev.ecodes.REL_HWHEEL, 1): "Right",
        }.get((code, value))
        if direction is not None:
            key_name += f" {direction}"

    key_name = key_name.replace("ABS_Z", "Trigger Left")
    key_name = key_name.replace("ABS_RZ", "Trigger Right")

    key_name = key_name.replace("ABS_HAT0X", "DPad")
    key_name = key_name.replace("ABS_HAT0Y", "DPad")
    key_name = key_name.replace("ABS_HAT1X", "DPad 2")
    key_name = key_name.replace("ABS_HAT1Y", "DPad 2")
    key_name = key_name.replace("ABS_HAT2X", "DPad 3")
    key_name = key_name.replace("ABS_HAT2Y", "DPad 3")

    key_name = key_name.replace("ABS_X", "Joystick")
    key_name = key_name.replace("ABS_Y", "Joystick")
    key_name = key_name.replace("ABS_RX", "Joystick 2")
    key_name = key_name.replace("ABS_RY", "Joystick 2")

    key_name = key_name.replace("BTN_", "Button ")
    key_name = key_name.replace("KEY_", "")

    key_name = key_name.replace("REL_", "")
    key_name = key_name.replace("HWHEEL", "Wheel")
    key_name = key_name.replace("WHEEL", "Wheel")

    key_name = key_name.replace("_", " ")
    key_name = key_name.replace("  ", " ")

    return key_name


IDLE = 0
HOLDING = 1


class Row(Gtk.ListBoxRow):
    """A single, configurable key mapping."""

    __gtype_name__ = "ListBoxRow"

    def __init__(self, delete_callback, window, key=None, target=None, symbol=None):
        """Construct a row widget.

        Parameters
        ----------
        key : Key
        """
        if key is not None and not isinstance(key, Key):
            raise TypeError("Expected key to be a Key object")

        super().__init__()
        self.device = window.group
        self.window = window
        self.delete_callback = delete_callback

        self.symbol_input = None
        self.keycode_input = None
        self.target_input = None
        self.completion = None
        self.completion_store = store
        
        self.key = key

        self.put_together(target, symbol)

        self._state = IDLE

    def update_mapping(self, previous_key=None):
        """update the mapping/preset"""
        key = self.get_key()
        target = self.get_target()
        symbol = self.get_symbol()

        if self.is_finished():
            custom_mapping.change(key, target, symbol, previous_key)
    
    def is_finished(self):
        key = self.get_key()
        target = self.get_target()
        symbol = self.get_symbol()
        return symbol is not None and target is not None and key is not None
    
    def refresh_state(self):
        """Refresh the state.

        The state is needed to switch focus when no keys are held anymore,
        but only if the row has been in the HOLDING state before.
        """
        old_state = self._state

        if not self.keycode_input.is_focus():
            self._state = IDLE
            return

        unreleased_keys = reader.get_unreleased_keys()
        if unreleased_keys is None and old_state == HOLDING and self.key:
            # A key was pressed and then released.
            # Switch to the target. idle_add this so that the
            # keycode event won't write into the target input as well.
            window = self.window.window
            GLib.idle_add(lambda: window.set_focus(self.target_input))

        if unreleased_keys is not None:
            self._state = HOLDING
            return

        self._state = IDLE

    def get_key(self):
        """Get the Key object from the left column.

        Or None if no code is mapped on this row.
        """
        return self.key
    
    def get_target(self):
        """Get the assigned target"""
        target = self.target_input.get_active_id()
        return target if target else None
    
    def get_symbol(self):
        """Get the assigned symbol"""
        symbol = self.symbol_input.get_text()
        return symbol if symbol else None

    def set_new_key(self, new_key):
        """Check if a keycode has been pressed and if so, display it.

        Parameters
        ----------
        new_key : Key
        """
        if new_key is not None and not isinstance(new_key, Key):
            raise TypeError("Expected new_key to be a Key object")

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
        existing = custom_mapping.get_symbol(new_key)
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
        self.update_mapping(previous_key)

    def on_symbol_input_change(self, _):
        """When the output symbol for that keycode is typed in."""
        self.update_mapping()
        self.validate_symbol()

    def on_target_input_change(self, _):
        """When the mapping target is selected"""
        if self.get_target() not in global_uinputs.devices:
            self.target_input.get_style_context().add_class("invalid_input")
        else:
            self.target_input.get_style_context().remove_class("invalid_input")
            
        self.update_mapping()
        self.window.save_preset()
        self.update_completion()
        self.validate_symbol()

    def update_completion(self):
        """update the dropdown for key suggestions"""
        target = self.get_target()
        if target and global_uinputs.get_uinput(target):
            s = Gtk.ListStore(str)
            for name in system_mapping.list_names(global_uinputs.get_uinput(target).capabilities()[1]):
                s.append([name])
        else:
            s = store
        self.completion_store = s
        self.completion.set_model(s)

    def validate_symbol(self):
        """check if target can handle all event codes in symbol_input and color the Gtk.Entry"""
        def validate():
            symbol = self.get_symbol()
            target = self.get_target()
            if not symbol or not target or not global_uinputs.get_uinput(target):
                return True

            if is_this_a_macro(symbol):
                if parse(symbol, return_errors=True):
                    return False

                capabilities = parse(symbol).get_capabilities()
            else:
                capabilities = {
                    1: {system_mapping.get(symbol)},
                    2: set(),
                }

            target_capabilities = global_uinputs.get_uinput(target).capabilities()
            for i in range(1, 3):
                if i not in target_capabilities.keys():
                    target_capabilities[i] = []

            return (capabilities[1].issubset(target_capabilities[1]) and
                    capabilities[2].issubset(target_capabilities[2]))

        rt = validate()
        if rt:
            self.symbol_input.get_style_context().remove_class("invalid_input")
        else:
            self.symbol_input.get_style_context().add_class("invalid_input")

        return rt

    def match(self, _, key, tree_iter):
        """Search the available names."""
        value = self.completion_store.get_value(tree_iter, 0)
        return key in value.lower()

    def show_click_here(self):
        """Show 'click here' on the keycode input button."""
        if self.get_key() is not None:
            return

        self.set_keycode_input_label("click here")
        self.keycode_input.set_opacity(0.3)

    def show_press_key(self):
        """Show 'press key' on the keycode input button."""
        if self.get_key() is not None:
            return

        self.set_keycode_input_label("press key")
        self.keycode_input.set_opacity(1)

    def on_keycode_input_focus(self, *_):
        """Refresh useful usage information."""
        reader.clear()
        self.show_press_key()
        self.window.can_modify_mapping()

    def on_keycode_input_unfocus(self, *_):
        """Refresh useful usage information and set some state stuff."""
        self.show_click_here()
        self.keycode_input.set_active(False)
        self._state = IDLE
        self.window.save_preset()

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
        self.keycode_input.set_opacity(1)

    def on_symbol_input_unfocus(self, symbol_input, _):
        """Save the preset and correct the input casing."""
        symbol = symbol_input.get_text()
        correct_case = system_mapping.correct_case(symbol)
        if symbol != correct_case:
            symbol_input.set_text(correct_case)
        self.window.save_preset()

    def put_together(self, target, symbol):
        """Create all child GTK widgets and connect their signals."""
        logger.debug(f"creating row {symbol}")
        delete_button = Gtk.EventBox()
        delete_button.add(
            Gtk.Image.new_from_icon_name("window-close", Gtk.IconSize.BUTTON)
        )
        delete_button.connect("button-press-event", self.on_delete_button_clicked)
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
        keycode_input.connect("focus-in-event", self.on_keycode_input_focus)
        keycode_input.connect("focus-out-event", self.on_keycode_input_unfocus)
        # don't leave the input when using arrow keys or tab. wait for the
        # window to consume the keycode from the reader
        keycode_input.connect("key-press-event", lambda *args: Gdk.EVENT_STOP)
        
        target_store = Gtk.ListStore(str)
        for uinput in global_uinputs.devices:
            target_store.append([uinput])   
            
        target_input = Gtk.ComboBox.new_with_model(target_store)
        self.target_input = target_input
        target_input.set_size_request(100, -1)
        renderer_text = Gtk.CellRendererText()
        target_input.pack_start(renderer_text, False)
        target_input.add_attribute(renderer_text, "text", 0)
        target_input.set_id_column(0)
        
        symbol_input = Gtk.Entry()
        self.symbol_input = symbol_input
        symbol_input.set_alignment(0.5)
        symbol_input.set_width_chars(4)
        symbol_input.set_has_frame(False)
        completion = Gtk.EntryCompletion()
        self.completion = completion
        completion.set_text_column(0)
        completion.set_match_func(self.match)
        symbol_input.set_completion(completion)

        if symbol is not None:
            symbol_input.set_text(symbol)

        if target is not None:
            if not target_input.set_active_id(target):
                target_store.append([target])
                target_input.set_active_id(target)
                target_input.get_style_context().add_class("invalid_input")
        
        self.update_completion()
        self.validate_symbol()

        target_input.connect("changed", self.on_target_input_change)
        symbol_input.connect("changed", self.on_symbol_input_change)
        symbol_input.connect("focus-out-event", self.on_symbol_input_unfocus)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box.set_homogeneous(False)
        box.set_spacing(0)
        box.pack_start(keycode_input, expand=False, fill=True, padding=0)
        box.pack_start(target_input, expand=False, fill=True, padding=0)
        box.pack_start(symbol_input, expand=True, fill=True, padding=0)
        box.pack_start(delete_button, expand=False, fill=True, padding=0)
        box.show_all()
        box.get_style_context().add_class("row-box")

        self.add(box)
        self.show_all()

    def on_delete_button_clicked(self, *_):
        """Destroy the row and remove it from the config."""
        key = self.get_key()
        if key is not None:
            custom_mapping.clear(key)
        
        self.target_input.set_active_id("")
        self.symbol_input.set_text("")
        self.set_keycode_input_label("")
        self.key = None
        self.delete_callback(self)
