#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@hip70890b.de>
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


import math

from gi.repository import Gtk, Gdk, GLib

from keymapper.data import get_data_path
from keymapper.paths import get_config_path, get_preset_path
from keymapper.state import custom_mapping
from keymapper.presets import get_presets, find_newest_preset, \
    delete_preset, rename_preset, get_available_preset_name
from keymapper.logger import logger
from keymapper.getdevices import get_devices
from keymapper.gui.row import Row, to_string
from keymapper.gui.reader import keycode_reader
from keymapper.injection.injector import RUNNING, FAILED, NO_GRAB
from keymapper.daemon import get_dbus_interface
from keymapper.config import config
from keymapper.injection.macros import is_this_a_macro, parse
from keymapper import permissions


def gtk_iteration():
    """Iterate while events are pending."""
    while Gtk.events_pending():
        Gtk.main_iteration()


CTX_SAVE = 0
CTX_APPLY = 1
CTX_ERROR = 3
CTX_WARNING = 4

CONTINUE = True
GO_BACK = False


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


def with_selected_device(func):
    """Decorate a function to only execute if a device is selected."""
    # this should only happen if no device was found at all
    def wrapped(window, *args):
        if window.selected_device is None:
            return True  # work with timeout_add

        return func(window, *args)

    return wrapped


def with_selected_preset(func):
    """Decorate a function to only execute if a preset is selected."""
    # this should only happen if no device was found at all
    def wrapped(window, *args):
        if window.selected_preset is None or window.selected_device is None:
            return True  # work with timeout_add

        return func(window, *args)

    return wrapped


class HandlerDisabled:
    """Safely modify a widget without causing handlers to be called.

    Use in a with statement.
    """
    def __init__(self, widget, handler):
        self.widget = widget
        self.handler = handler

    def __enter__(self):
        self.widget.handler_block_by_func(self.handler)

    def __exit__(self, *_):
        self.widget.handler_unblock_by_func(self.handler)


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

        self.unsaved_changes = builder.get_object('unsaved_changes')

        window = self.get('window')
        window.show()
        # hide everything until stuff is populated
        self.get('vertical-wrapper').set_opacity(0)
        self.window = window

        # if any of the next steps take a bit to complete, have the window
        # already visible (without content) to make it look more responsive.
        gtk_iteration()

        permission_errors = permissions.can_read_devices()
        if len(permission_errors) > 0:
            permission_errors = [(
                'Usually, key-mapper-gtk should be started with pkexec '
                'or sudo.'
            )] + permission_errors
            self.show_status(
                CTX_ERROR,
                'Permission error, hover for info',
                '\n\n'.join(permission_errors)
            )

        # this is not set to invisible in glade to give the ui a default
        # height that doesn't jump when a gamepad is selected
        self.get('gamepad_separator').hide()
        self.get('gamepad_config').hide()

        self.populate_devices()
        self.select_newest_preset()

        self.timeouts = [
            GLib.timeout_add(100, self.check_add_row),
            GLib.timeout_add(1000 / 30, self.consume_newest_keycode)
        ]

        # now show the proper finished content of the window
        self.get('vertical-wrapper').set_opacity(1)

        self.ctrl = 0
        self.unreleased_warn = 0

    def unsaved_changes_dialog(self):
        """Blocks until the user decided about an action."""
        self.unsaved_changes.show()
        response = self.unsaved_changes.run()
        self.unsaved_changes.hide()

        if response == Gtk.ResponseType.ACCEPT:
            return CONTINUE

        return GO_BACK

    def key_press(self, _, event):
        """To execute shortcuts.

        This has nothing to do with the keycode reader.
        """
        gdk_keycode = event.get_keyval()[1]

        if gdk_keycode in [Gdk.KEY_Control_L, Gdk.KEY_Control_R]:
            self.ctrl = True

        if gdk_keycode == Gdk.KEY_q and self.ctrl:
            self.on_close()

    def key_release(self, _, event):
        """To execute shortcuts.

        This has nothing to do with the keycode reader.
        """
        gdk_keycode = event.get_keyval()[1]

        if gdk_keycode in [Gdk.KEY_Control_L, Gdk.KEY_Control_R]:
            self.ctrl = False

    def initialize_gamepad_config(self):
        """Set slider and dropdown values when a gamepad is selected."""
        devices = get_devices()
        if devices[self.selected_device]['gamepad']:
            self.get('gamepad_separator').show()
            self.get('gamepad_config').show()
        else:
            self.get('gamepad_separator').hide()
            self.get('gamepad_config').hide()
            return

        left_purpose = self.get('left_joystick_purpose')
        right_purpose = self.get('right_joystick_purpose')
        speed = self.get('joystick_mouse_speed')

        with HandlerDisabled(left_purpose, self.on_left_joystick_changed):
            value = custom_mapping.get('gamepad.joystick.left_purpose')
            left_purpose.set_active_id(value)

        with HandlerDisabled(right_purpose, self.on_right_joystick_changed):
            value = custom_mapping.get('gamepad.joystick.right_purpose')
            right_purpose.set_active_id(value)

        with HandlerDisabled(speed, self.on_joystick_mouse_speed_changed):
            value = custom_mapping.get('gamepad.joystick.pointer_speed')
            range_value = math.log(value, 2)
            speed.set_value(range_value)

    def get(self, name):
        """Get a widget from the window"""
        return self.builder.get_object(name)

    def on_close(self, *_):
        """Safely close the application."""
        logger.debug('Closing window')
        self.window.hide()
        for timeout in self.timeouts:
            GLib.source_remove(timeout)
            self.timeouts = []
        keycode_reader.stop_reading()
        Gtk.main_quit()

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
            path = get_preset_path(self.selected_device, new_preset)
            custom_mapping.save(path)
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

    def can_modify_mapping(self, *_):
        """Show a message if changing the mapping is not possible."""
        if self.dbus.get_state(self.selected_device) != RUNNING:
            return

        # because the device is in grab mode by the daemon and
        # therefore the original keycode inaccessible
        logger.info('Cannot change keycodes while injecting')
        self.show_status(
            CTX_ERROR,
            'Use "Restore Defaults" to stop before editing'
        )

    def get_focused_row(self):
        """Get the Row and its child that is currently in focus."""
        focused = self.window.get_focus()
        if focused is None:
            return None, None

        box = focused.get_parent()
        if box is None:
            return None, None

        row = box.get_parent()
        if not isinstance(row, Row):
            return None, None

        return row, focused

    @with_selected_device
    def consume_newest_keycode(self):
        """To capture events from keyboards, mice and gamepads."""
        # the "event" event of Gtk.Window wouldn't trigger on gamepad
        # events, so it became a GLib timeout to periodically check kernel
        # events.

        # letting go of one of the keys of a combination won't just make
        # it return the leftover key, it will continue to return None because
        # they have already been read.
        key = keycode_reader.read()

        # inform the currently selected row about the new keycode
        row, focused = self.get_focused_row()
        if key is not None:
            if isinstance(focused, Gtk.ToggleButton):
                row.set_new_key(key)

            if key.is_problematic() and isinstance(focused, Gtk.ToggleButton):
                self.show_status(
                    CTX_WARNING,
                    'ctrl, alt and shift may not combine properly',
                    'Your system will probably reinterpret combinations ' +
                    'with those after they are injected, and by doing so ' +
                    'break them.'
                )

        if row is not None:
            row.refresh_state()

        return True

    @with_selected_device
    def on_apply_system_layout_clicked(self, _):
        """Stop injecting the mapping."""
        self.dbus.stop_injecting(self.selected_device)
        self.show_status(CTX_APPLY, 'Applied the system default')
        GLib.timeout_add(100, self.show_device_mapping_status)

    def show_status(self, context_id, message, tooltip=None):
        """Show a status message and set its tooltip."""
        if tooltip is None:
            tooltip = message

        self.get('error_status_icon').hide()
        self.get('warning_status_icon').hide()

        if context_id == CTX_ERROR:
            self.get('error_status_icon').show()

        if context_id == CTX_WARNING:
            self.get('warning_status_icon').show()

        if len(message) > 55:
            message = message[:52] + '...'

        status_bar = self.get('status_bar')
        status_bar.push(context_id, message)
        status_bar.set_tooltip_text(tooltip)

    def check_macro_syntax(self):
        """Check if the programmed macros are allright."""
        for key, output in custom_mapping:
            if not is_this_a_macro(output):
                continue

            error = parse(output, custom_mapping, return_errors=True)
            if error is None:
                continue

            position = to_string(key)
            msg = f'Syntax error at {position}, hover for info'
            self.show_status(CTX_ERROR, msg, error)

    @with_selected_preset
    def on_save_preset_clicked(self, _):
        """Save changes to a preset to the file system."""
        new_name = self.get('preset_name_input').get_text()
        try:
            self.save_preset()
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
            self.show_status(CTX_SAVE, f'Saved "{self.selected_preset}"')
            self.check_macro_syntax()

        except PermissionError as error:
            error = str(error)
            self.show_status(CTX_ERROR, 'Permission denied!', error)
            logger.error(error)

    @with_selected_preset
    def on_delete_preset_clicked(self, _):
        """Delete a preset from the file system."""
        delete_preset(self.selected_device, self.selected_preset)
        self.populate_presets()

    @with_selected_preset
    def on_apply_preset_clicked(self, _):
        """Apply a preset without saving changes."""
        if custom_mapping.num_saved_keys == 0:
            logger.error('Cannot apply empty preset file')
            # also helpful for first time use
            if custom_mapping.changed:
                self.show_status(
                    CTX_ERROR,
                    'You need to save your changes first',
                    'No mappings are stored in the preset .json file yet'
                )
            else:
                self.show_status(
                    CTX_ERROR,
                    'You need to add keys and save first'
                )
            return

        preset = self.selected_preset
        device = self.selected_device

        logger.info('Applying preset "%s" for "%s"', preset, device)

        if not self.unreleased_warn:
            unreleased = keycode_reader.get_unreleased_keys()
            if unreleased is not None:
                # it's super annoying if that happens and may break the user
                # input in such a way to prevent disabling the mapping
                logger.error(
                    'Tried to apply a preset while keys were held down: %s',
                    unreleased
                )
                self.show_status(
                    CTX_ERROR,
                    'Please release your pressed keys first',
                    'X11 will think they are held down forever otherwise.\n'
                    'To overwrite this warning, press apply again.'
                )
                self.unreleased_warn = True
                return

        self.unreleased_warn = False
        self.dbus.set_config_dir(get_config_path())
        self.dbus.start_injecting(device, preset)

        self.show_status(
            CTX_APPLY,
            'Starting injection...'
        )

        GLib.timeout_add(100, self.show_injection_result)

    def on_autoload_switch(self, _, active):
        """Load the preset automatically next time the user logs in."""
        device = self.selected_device
        preset = self.selected_preset
        config.set_autoload_preset(device, preset if active else None)
        config.save_config()
        # tell the service to refresh its config
        self.dbus.set_config_dir(get_config_path())

    def on_select_device(self, dropdown):
        """List all presets, create one if none exist yet."""
        if dropdown.get_active_id() == self.selected_device:
            return

        if custom_mapping.changed and self.unsaved_changes_dialog() == GO_BACK:
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

    def show_injection_result(self):
        """Show if the injection was successfully started."""
        state = self.dbus.get_state(self.selected_device)

        if state == RUNNING:
            if custom_mapping.changed:
                self.show_status(
                    CTX_WARNING,
                    'Applied without unsaved changes. shift + del to stop',
                    'Click "Save" first for changes to take effect'
                )
            else:
                self.show_status(
                    CTX_APPLY,
                    f'Applied preset "{self.selected_preset}"'
                )

            self.show_device_mapping_status()
            return False

        if state == FAILED:
            self.show_status(
                CTX_ERROR,
                f'Failed to apply preset "{self.selected_preset}"'
            )
            return False

        if state == NO_GRAB:
            self.show_status(
                CTX_ERROR,
                'The device was not grabbed',
                'Either another application is already grabbing it or '
                'your preset doesn\'t contain anything that is sent by the '
                'device.'
            )
            return False

        # keep the timeout running
        return True

    def show_device_mapping_status(self):
        """Figure out if this device is currently under keymappers control."""
        device = self.selected_device
        if self.dbus.get_state(device) == RUNNING:
            logger.info('Device "%s" is currently mapped', device)
            self.get('apply_system_layout').set_opacity(1)
        else:
            self.get('apply_system_layout').set_opacity(0.4)

    @with_selected_device
    def on_create_preset_clicked(self, _):
        """Create a new preset and select it."""
        if custom_mapping.changed and self.unsaved_changes_dialog() == GO_BACK:
            return

        try:
            new_preset = get_available_preset_name(self.selected_device)
            custom_mapping.empty()
            path = get_preset_path(self.selected_device, new_preset)
            custom_mapping.save(path)
            self.get('preset_selection').append(new_preset, new_preset)
            self.get('preset_selection').set_active_id(new_preset)
        except PermissionError as error:
            error = str(error)
            self.show_status(CTX_ERROR, 'Permission denied!', error)
            logger.error(error)

    def on_select_preset(self, dropdown):
        """Show the mappings of the preset."""
        if dropdown.get_active_id() == self.selected_preset:
            return

        if custom_mapping.changed and self.unsaved_changes_dialog() == GO_BACK:
            dropdown.set_active_id(self.selected_preset)
            return

        self.clear_mapping_table()

        preset = dropdown.get_active_text()
        logger.debug('Selecting preset "%s"', preset)
        self.selected_preset = preset

        custom_mapping.load(get_preset_path(self.selected_device, preset))

        key_list = self.get('key_list')
        for key, output in custom_mapping:
            single_key_mapping = Row(
                window=self,
                delete_callback=self.on_row_removed,
                key=key,
                character=output
            )
            key_list.insert(single_key_mapping, -1)

        autoload_switch = self.get('preset_autoload_switch')

        with HandlerDisabled(autoload_switch, self.on_autoload_switch):
            autoload_switch.set_active(config.is_autoloaded(
                self.selected_device,
                self.selected_preset
            ))

        self.get('preset_name_input').set_text('')
        self.add_empty()

        self.initialize_gamepad_config()

        custom_mapping.changed = False

    def on_left_joystick_changed(self, dropdown):
        """Set the purpose of the left joystick."""
        purpose = dropdown.get_active_id()
        custom_mapping.set('gamepad.joystick.left_purpose', purpose)

    def on_right_joystick_changed(self, dropdown):
        """Set the purpose of the right joystick."""
        purpose = dropdown.get_active_id()
        custom_mapping.set('gamepad.joystick.right_purpose', purpose)

    def on_joystick_mouse_speed_changed(self, gtk_range):
        """Set how fast the joystick moves the mouse."""
        speed = 2 ** gtk_range.get_value()
        custom_mapping.set('gamepad.joystick.pointer_speed', speed)

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

    def save_preset(self):
        """Write changes to presets to disk."""
        logger.info(
            'Updating configs for "%s", "%s"',
            self.selected_device,
            self.selected_preset
        )

        path = get_preset_path(self.selected_device, self.selected_preset)
        custom_mapping.save(path)

        custom_mapping.changed = False
        self.unhighlight_all_rows()
