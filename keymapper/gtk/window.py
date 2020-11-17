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


import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GLib', '2.0')
from gi.repository import Gtk, Gdk, GLib

from keymapper.data import get_data_path
from keymapper.X import create_setxkbmap_config, apply_preset, \
    create_preset, custom_mapping, system_mapping, parse_symbols_file, \
    setxkbmap
from keymapper.presets import get_presets, find_newest_preset, \
    delete_preset, rename_preset
from keymapper.logger import logger
from keymapper.linux import get_devices, KeycodeReader
from keymapper.gtk.row import Row
from keymapper.gtk.unsaved import unsaved_changes_dialog, GO_BACK


def gtk_iteration():
    """Iterate while events are pending."""
    while Gtk.events_pending():
        Gtk.main_iteration()


CTX_SAVE = 0
CTX_APPLY = 1
CTX_ERROR = 3


# TODO test on wayland


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
        self.selected_device = None
        self.selected_preset = None

        css_provider = Gtk.CssProvider()
        with open(get_data_path('style.css'), 'r') as f:
            data = (
                f.read() +
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
        self.get('wrapper').set_opacity(0)
        self.window = window

        # if any of the next steps take a bit to complete, have the window
        # already visible to make it look more responsive.
        gtk_iteration()

        self.populate_devices()

        self.select_newest_preset()

        self.timeout = GLib.timeout_add(100, self.check_add_row)

        # now show the proper finished content of the window
        self.get('wrapper').set_opacity(1)

    def get(self, name):
        """Get a widget from the window"""
        return self.builder.get_object(name)

    def on_close(self, *_):
        """Safely close the application."""
        GLib.source_remove(self.timeout)
        Gtk.main_quit()

    def check_add_row(self):
        """Ensure that one empty row is available at all times."""
        num_rows = len(self.get('key_list').get_children())

        # verify that all mappings are displayed
        if num_rows < len(custom_mapping):
            raise AssertionError(
                f'custom_mapping contains {len(custom_mapping)} rows, '
                f'but only {num_rows} are displayed'
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
        """Show the available presets for the selected device."""
        device = self.selected_device
        presets = get_presets(device)
        self.get('preset_name_input').set_text('')
        if len(presets) == 0:
            presets = [create_preset(device)]
        else:
            logger.debug('Presets for "%s": %s', device, ', '.join(presets))
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

    def on_window_key_press_event(self, window, event):
        """Write down the pressed key on the UI.

        Helps to understand what the numbers in the mapping are about.
        """
        self.get('keycode').set_text(str(event.get_keycode()[1]))

    def on_apply_system_layout_clicked(self, button):
        """Load the mapping."""
        setxkbmap(self.selected_device, None)
        self.get('status_bar').push(
            CTX_APPLY,
            f'Applied the system default'
        )

    def on_save_preset_clicked(self, button):
        """Save changes to a preset to the file system."""
        new_name = self.get('preset_name_input').get_text()
        try:
            self.save_config()
            if new_name != '' and new_name != self.selected_preset:
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
        except PermissionError as e:
            self.get('status_bar').push(
                CTX_ERROR,
                'Error: Permission denied!'
            )
            logger.error(str(e))

    def on_delete_preset_clicked(self, button):
        """Delete a preset from the file system."""
        delete_preset(self.selected_device, self.selected_preset)
        self.populate_presets()

    def on_apply_preset_clicked(self, button):
        """Apply a preset without saving changes."""
        logger.debug(
            'Applying preset "%s" for "%s"',
            self.selected_preset,
            self.selected_device
        )
        apply_preset(self.selected_device, self.selected_preset)
        self.get('status_bar').push(
            CTX_APPLY,
            f'Applied "{self.selected_preset}"'
        )
        keycode_reader = KeycodeReader(self.selected_device)

    def on_select_device(self, dropdown):
        """List all presets, create one if none exist yet."""
        if dropdown.get_active_id() == self.selected_device:
            return

        if custom_mapping.changed and unsaved_changes_dialog() == GO_BACK:
            dropdown.set_active_id(self.selected_device)
            return

        device = dropdown.get_active_text()

        logger.debug('Selecting device "%s"', device)

        self.selected_device = device
        self.selected_preset = None

        self.populate_presets()

    def on_create_preset_clicked(self, button):
        """Create a new preset and select it."""
        if custom_mapping.changed:
            if unsaved_changes_dialog() == GO_BACK:
                return

        try:
            new_preset = create_preset(self.selected_device)
            self.get('preset_selection').append(new_preset, new_preset)
            self.get('preset_selection').set_active_id(new_preset)
        except PermissionError as e:
            self.get('status_bar').push(
                CTX_ERROR,
                'Error: Permission denied!'
            )
            logger.error(str(e))

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
        parse_symbols_file(self.selected_device, self.selected_preset)

        key_list = self.get('key_list')
        for keycode, output in custom_mapping:
            single_key_mapping = Row(
                window=self,
                delete_callback=self.on_row_removed,
                keycode=keycode,
                character=output[1]
            )
            key_list.insert(single_key_mapping, -1)

        self.get('preset_name_input').set_text('')
        self.add_empty()

    def add_empty(self):
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
        """Write changes to disk"""
        if self.selected_device is None or self.selected_preset is None:
            return

        logger.info(
            'Updating configs for "%s", "%s"',
            self.selected_device,
            self.selected_preset
        )

        create_setxkbmap_config(
            self.selected_device,
            self.selected_preset
        )

        custom_mapping.changed = False
        self.unhighlight_all_rows()
