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


"""User Interface."""


import evdev
import sys
from evdev.ecodes import EV_KEY

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GLib', '2.0')
from gi.repository import Gtk, Gdk, GLib

from keymapper.data import get_data_path
from keymapper.state import custom_mapping
from keymapper.presets import get_presets, find_newest_preset, \
    delete_preset, rename_preset, get_available_preset_name
from keymapper.logger import logger
from keymapper.getdevices import get_devices
from keymapper.gtk.row import Row, to_string
from keymapper.gtk.unsaved import unsaved_changes_dialog, GO_BACK
from keymapper.dev.reader import keycode_reader
from keymapper.daemon import get_dbus_interface
from keymapper.config import config


def gtk_iteration():
    """Iterate while events are pending."""
    while Gtk.events_pending():
        Gtk.main_iteration()


CTX_SAVE = 0
CTX_APPLY = 1
CTX_ERROR = 3


def get_selected_row_bg():
    """Get the background color that a row is going to have when selected."""
    # ListBoxRows can be selected, but either they are always selectable
    # via mouse clicks and via code, or not at all. I just want to controll
    # it over code. So I have to add a class and change the background color
    # to act like it's selected. For this I need the right color, but
    # @selected_bg_color doesn't work for every theme. So get it from
    # some widget (which is deprecated according to the docs, but it works...)
    row = Gtk.ListBoxRow()
    row.show_all()
    context = row.get_style_context()
    color = context.get_background_color(Gtk.StateFlags.SELECTED)
    # but this way it can be made only slightly highlighted, which is nice
    color.alpha /= 4
    row.destroy()
    return color.to_string()


class Window:
    """User Interface."""
    def __init__(self):
        self.dbus = get_dbus_interface()

        self.selected_device = None
        self.selected_preset = None

        css_provider = Gtk.CssProvider()
        with open(get_data_path('style.css'), 'r') as file:
            data = (
                file.read() +
                '\n.changed{background-color:' +
                get_selected_row_bg() +
                ';}\n'
            )
            css_provider.load_from_data(bytes(data, encoding='UTF-8'))

        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        gladefile = get_data_path('key-mapper.glade')
        builder = Gtk.Builder()
        builder.add_from_file(gladefile)
        builder.connect_signals(self)
        self.builder = builder

        window = self.get('window')
        window.show()
        # hide everything until stuff is populated
        self.get('vertical-wrapper').set_opacity(0)
        self.window = window

        # if any of the next steps take a bit to complete, have the window
        # already visible to make it look more responsive.
        gtk_iteration()

        self.populate_devices()

        self.select_newest_preset()

        self.timeouts = [
            GLib.timeout_add(100, self.check_add_row),
            GLib.timeout_add(1000 / 30, self.consume_newest_keycode)
        ]

        # now show the proper finished content of the window
        self.get('vertical-wrapper').set_opacity(1)

    def get(self, name):
        """Get a widget from the window"""
        return self.builder.get_object(name)

    def on_close(self, *_):
        """Safely close the application."""
        logger.debug('Closing window')
        for timeout in self.timeouts:
            GLib.source_remove(timeout)
            self.timeouts = []
        keycode_reader.stop_reading()
        self.window.destroy()
        gtk_iteration()
        sys.exit(0)

    def check_add_row(self):
        """Ensure that one empty row is available at all times."""
        num_rows = len(self.get('key_list').get_children())

        # verify that all mappings are displayed. One of them
        # is possible the empty row
        num_maps = len(custom_mapping)
        if num_rows < num_maps or num_rows > num_maps + 1:
            raise AssertionError(
                f'custom_mapping contains {len(custom_mapping)} rows, '
                f'but {num_rows} are displayed'
            )

        if num_rows == len(custom_mapping):
            self.add_empty()

        return True

    def select_newest_preset(self):
        """Find and select the newest preset."""
        device, preset = find_newest_preset()
        if device is not None:
            self.get('device_selection').set_active_id(device)
        if preset is not None:
            self.get('device_selection').set_active_id(preset)

    def populate_devices(self):
        """Make the devices selectable."""
        devices = get_devices()
        device_selection = self.get('device_selection')
        for device in devices:
            device_selection.append(device, device)

    def populate_presets(self):
        """Show the available presets for the selected device.

        This will destroy unsaved changes in the custom_mapping.
        """
        self.get('preset_name_input').set_text('')

        device = self.selected_device
        presets = get_presets(device)

        if len(presets) == 0:
            new_preset = get_available_preset_name(self.selected_device)
            custom_mapping.empty()
            custom_mapping.save(self.selected_device, new_preset)
            presets = [new_preset]
        else:
            logger.debug('"%s" presets: "%s"', device, '", "'.join(presets))

        preset_selection = self.get('preset_selection')

        preset_selection.handler_block_by_func(self.on_select_preset)
        # otherwise the handler is called with None for each removed preset
        preset_selection.remove_all()
        preset_selection.handler_unblock_by_func(self.on_select_preset)

        for preset in presets:
            preset_selection.append(preset, preset)
        # and select the newest one (on the top)
        preset_selection.set_active(0)

    def clear_mapping_table(self):
        """Remove all rows from the mappings table."""
        key_list = self.get('key_list')
        key_list.forall(key_list.remove)
        custom_mapping.empty()

    def unhighlight_all_rows(self):
        """Remove all rows from the mappings table."""
        key_list = self.get('key_list')
        key_list.forall(lambda row: row.unhighlight())

    def consume_newest_keycode(self):
        """To capture events from keyboard, mice and gamepads."""
        # the "event" event of Gtk.Window wouldn't trigger on gamepad
        # events, so it became a GLib timeout
        ev_type, keycode = keycode_reader.read()

        if keycode is None or ev_type is None:
            return True

        click_events = [
            evdev.ecodes.BTN_LEFT,
            evdev.ecodes.BTN_TOOL_DOUBLETAP
        ]

        if ev_type == EV_KEY and keycode in click_events:
            # disable mapping the left mouse button because it would break
            # the mouse. Also it is emitted right when focusing the row
            # which breaks the current workflow.
            return True

        self.get('keycode').set_text(to_string(ev_type, keycode))

        # inform the currently selected row about the new keycode
        focused = self.window.get_focus()
        if focused is None:
            return True

        box = focused.get_parent()
        if box is None:
            return True

        row = box.get_parent()
        if isinstance(focused, Gtk.ToggleButton) and isinstance(row, Row):
            row.set_new_keycode(ev_type, keycode)

        return True

    def on_apply_system_layout_clicked(self, _):
        """Load the mapping."""
        self.dbus.stop_injecting(self.selected_device)
        self.get('status_bar').push(
            CTX_APPLY,
            'Applied the system default'
        )
        GLib.timeout_add(10, self.show_device_mapping_status)

    def on_save_preset_clicked(self, button):
        """Save changes to a preset to the file system."""
        new_name = self.get('preset_name_input').get_text()
        try:
            self.save_config()
            if new_name not in ['', self.selected_preset]:
                rename_preset(
                    self.selected_device,
                    self.selected_preset,
                    new_name
                )
            # after saving the config, its modification date will be the
            # newest, so populate_presets will automatically select the
            # right one again.
            self.populate_presets()
            self.get('status_bar').push(
                CTX_SAVE,
                f'Saved "{self.selected_preset}"'
            )
        except PermissionError as error:
            self.get('status_bar').push(
                CTX_ERROR,
                'Error: Permission denied!'
            )
            logger.error(str(error))

    def on_delete_preset_clicked(self, _):
        """Delete a preset from the file system."""
        delete_preset(self.selected_device, self.selected_preset)
        self.populate_presets()

    def on_apply_preset_clicked(self, _):
        """Apply a preset without saving changes."""
        preset = self.selected_preset
        device = self.selected_device

        logger.debug('Applying preset "%s" for "%s"', preset, device)

        push = self.get('status_bar').push
        if custom_mapping.changed:
            push(CTX_APPLY, f'Applied outdated preset "{preset}"')
        else:
            push(CTX_APPLY, f'Applied preset "{preset}"')

        success = self.dbus.start_injecting(
            self.selected_device,
            preset
        )

        if not success:
            self.get('status_bar').push(
                CTX_ERROR,
                'Error: Could not grab devices!'
            )

        # restart reading because after injecting the device landscape
        # changes a bit
        keycode_reader.start_reading(device)
        GLib.timeout_add(10, self.show_device_mapping_status)

    def on_preset_autoload_switch_activate(self, _, active):
        """Load the preset automatically next time the user logs in."""
        device = self.selected_device
        preset = self.selected_preset
        config.set_autoload_preset(device, preset if active else None)
        config.save_config()

    def on_select_device(self, dropdown):
        """List all presets, create one if none exist yet."""
        if dropdown.get_active_id() == self.selected_device:
            return

        if custom_mapping.changed and unsaved_changes_dialog() == GO_BACK:
            dropdown.set_active_id(self.selected_device)
            return

        # selecting a device will also automatically select a different
        # preset. Prevent another unsaved-changes dialog to pop up
        custom_mapping.changed = False

        device = dropdown.get_active_text()

        logger.debug('Selecting device "%s"', device)

        self.selected_device = device
        self.selected_preset = None

        self.populate_presets()
        GLib.idle_add(lambda: keycode_reader.start_reading(device))

        self.show_device_mapping_status()

    def show_device_mapping_status(self):
        """Figure out if this device is currently under keymappers control."""
        if self.dbus.is_injecting(self.selected_device):
            logger.info('This device is currently mapped.')
            self.get('apply_system_layout').set_opacity(1)
        else:
            self.get('apply_system_layout').set_opacity(0.4)

    def on_create_preset_clicked(self, _):
        """Create a new preset and select it."""
        if custom_mapping.changed:
            if unsaved_changes_dialog() == GO_BACK:
                return

        try:
            new_preset = get_available_preset_name(self.selected_device)
            custom_mapping.empty()
            custom_mapping.save(self.selected_device, new_preset)
            self.get('preset_selection').append(new_preset, new_preset)
            self.get('preset_selection').set_active_id(new_preset)
        except PermissionError as error:
            self.get('status_bar').push(
                CTX_ERROR,
                'Error: Permission denied!'
            )
            logger.error(str(error))

    def on_select_preset(self, dropdown):
        """Show the mappings of the preset."""
        if dropdown.get_active_id() == self.selected_preset:
            return

        if custom_mapping.changed and unsaved_changes_dialog() == GO_BACK:
            dropdown.set_active_id(self.selected_preset)
            return

        self.clear_mapping_table()

        preset = dropdown.get_active_text()
        logger.debug('Selecting preset "%s"', preset)

        self.selected_preset = preset
        custom_mapping.load(self.selected_device, self.selected_preset)

        key_list = self.get('key_list')
        for (ev_type, keycode), output in custom_mapping:
            single_key_mapping = Row(
                window=self,
                delete_callback=self.on_row_removed,
                ev_type=ev_type,
                keycode=keycode,
                character=output
            )
            key_list.insert(single_key_mapping, -1)

        autoload_switch = self.get('preset_autoload_switch')
        autoload_switch.set_active(config.is_autoloaded(
            self.selected_device,
            self.selected_preset
        ))

        self.get('preset_name_input').set_text('')
        self.add_empty()

    def add_empty(self):
        """Add one empty row for a single mapped key."""
        empty = Row(
            window=self,
            delete_callback=self.on_row_removed
        )
        key_list = self.get('key_list')
        key_list.insert(empty, -1)

    def on_row_removed(self, single_key_mapping):
        """Stuff to do when a row was removed

        Parameters
        ----------
        single_key_mapping : Row
        """
        key_list = self.get('key_list')
        # https://stackoverflow.com/a/30329591/4417769
        key_list.remove(single_key_mapping)

    def save_config(self):
        """Write changes to disk."""
        if self.selected_device is None or self.selected_preset is None:
            return

        logger.info(
            'Updating configs for "%s", "%s"',
            self.selected_device,
            self.selected_preset
        )

        custom_mapping.save(self.selected_device, self.selected_preset)

        custom_mapping.changed = False
        self.unhighlight_all_rows()
