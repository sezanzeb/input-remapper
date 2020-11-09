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
    create_preset, mapping
from keymapper.presets import get_presets, find_newest_preset, \
    delete_preset, rename_preset
from keymapper.logger import logger
from keymapper.linux import get_devices, keycode_reader
from keymapper.gtk.row import Row


def gtk_iteration():
    """Iterate while events are pending."""
    while Gtk.events_pending():
        Gtk.main_iteration()


CTX_SAVE = 0
CTX_APPLY = 1
CTX_ERROR = 3


# TODO test on wayland


class Window:
    """User Interface."""
    def __init__(self):
        self.selected_device = None
        self.selected_preset = None

        css_provider = Gtk.CssProvider()
        css_provider.load_from_path(get_data_path('style.css'))
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
        self.window = window

        self.populate_devices()

        self.select_newest_preset()

        GLib.timeout_add(100, self.check_add_row)

    def get(self, name):
        """Get a widget from the window"""
        return self.builder.get_object(name)

    def on_close(self, *_):
        """Safely close the application."""
        Gtk.main_quit()

    def check_add_row(self):
        """Ensure that one empty row is available at all times."""
        rows = len(self.get('key_list').get_children())

        # verify that all mappings are displayed
        assert rows >= len(mapping)

        if rows == len(mapping):
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
            window.get('status_bar').push(
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

    def on_select_device(self, dropdown):
        """List all presets, create one if none exist yet."""
        device = dropdown.get_active_text()

        logger.debug('Selecting device "%s"', device)

        self.selected_device = device
        self.selected_preset = None

        self.populate_presets()
        GLib.idle_add(
            lambda: keycode_reader.start_reading(self.selected_device)
        )

    def on_create_preset_clicked(self, button):
        """Create a new preset and select it."""
        new_preset = create_preset(self.selected_device)
        self.get('preset_selection').append(new_preset, new_preset)
        self.get('preset_selection').set_active_id(new_preset)
        self.save_config()

    def on_select_preset(self, dropdown):
        """Show the mappings of the preset."""
        self.clear_mapping_table()

        preset = dropdown.get_active_text()
        logger.debug('Selecting preset "%s"', preset)

        self.selected_preset = preset
        mapping.load(
            self.selected_device,
            self.selected_preset
        )

        key_list = self.get('key_list')
        for keycode, character in mapping:
            single_key_mapping = Row(
                window=self,
                delete_callback=self.on_row_removed,
                keycode=keycode,
                character=character
            )
            key_list.insert(single_key_mapping.get_widget(), -1)

        self.add_empty()

    def add_empty(self):
        empty = Row(
            window=self,
            delete_callback=self.on_row_removed
        )
        key_list = self.get('key_list')
        key_list.insert(empty.get_widget(), -1)

    def on_row_removed(self, single_key_mapping):
        """Stuff to do when a row was removed

        Parameters
        ----------
        single_key_mapping : Row
        """
        key_list = self.get('key_list')
        # https://stackoverflow.com/a/30329591/4417769
        key_list.remove(single_key_mapping.get_widget().get_parent())
        # shrink the window down as much as possible, otherwise it
        # will increase with each added mapping but won't go back when they
        # are removed.
        window = self.get('window')
        window.resize(window.get_size()[0], 1)

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


window = Window()
