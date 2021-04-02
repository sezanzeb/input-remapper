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


"""User Interface."""


import math
import os
import sys

from gi.repository import Gtk, Gdk, GLib

from keymapper.data import get_data_path
from keymapper.paths import get_config_path, get_preset_path
from keymapper.state import custom_mapping, system_mapping
from keymapper.presets import get_presets, find_newest_preset, \
    delete_preset, rename_preset, get_available_preset_name
from keymapper.logger import logger, COMMIT_HASH, VERSION, EVDEV_VERSION, \
    is_debug
from keymapper.getdevices import get_devices, GAMEPAD, KEYBOARD, UNKNOWN, \
    GRAPHICS_TABLET, TOUCHPAD, MOUSE
from keymapper.gui.row import Row, to_string
from keymapper.key import Key
from keymapper.gui.reader import reader
from keymapper.gui.helper import is_helper_running
from keymapper.injection.injector import RUNNING, FAILED, NO_GRAB
from keymapper.daemon import Daemon
from keymapper.config import config
from keymapper.injection.macros import is_this_a_macro, parse


def gtk_iteration():
    """Iterate while events are pending."""
    while Gtk.events_pending():
        Gtk.main_iteration()


CTX_SAVE = 0
CTX_APPLY = 1
CTX_ERROR = 3
CTX_WARNING = 4
CTX_MAPPING = 5

CONTINUE = True
GO_BACK = False

ICON_NAMES = {
    GAMEPAD: 'input-gaming',
    MOUSE: 'input-mouse',
    KEYBOARD: 'input-keyboard',
    GRAPHICS_TABLET: 'input-tablet',
    TOUCHPAD: 'input-touchpad',
    UNKNOWN: None,
}

# sort types that most devices would fall in easily to the right.
ICON_PRIORITIES = [
    GRAPHICS_TABLET, TOUCHPAD, GAMEPAD, MOUSE, KEYBOARD, UNKNOWN
]


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


def on_close_about(about, _):
    """Hide the about dialog without destroying it."""
    about.hide()
    return True


class Window:
    """User Interface."""
    def __init__(self):
        self.dbus = None

        self.start_processes()

        self.selected_device = None
        self.selected_preset = None

        css_provider = Gtk.CssProvider()
        with open(get_data_path('style.css'), 'r') as file:
            css_provider.load_from_data(bytes(file.read(), encoding='UTF-8'))

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

        # set up the device selection
        # https://python-gtk-3-tutorial.readthedocs.io/en/latest/treeview.html#the-view
        combobox = self.get('device_selection')
        self.device_store = Gtk.ListStore(str, str)
        combobox.set_model(self.device_store)
        renderer_icon = Gtk.CellRendererPixbuf()
        renderer_text = Gtk.CellRendererText()
        renderer_text.set_padding(5, 0)
        combobox.set_id_column(1)
        combobox.pack_start(renderer_icon, False)
        combobox.pack_start(renderer_text, False)
        combobox.add_attribute(renderer_icon, 'icon-name', 0)
        combobox.add_attribute(renderer_text, 'text', 1)

        self.confirm_delete = builder.get_object('confirm-delete')
        self.about = builder.get_object('about-dialog')
        self.about.connect('delete-event', on_close_about)
        # set_position needs to be done once initially, otherwise the
        # dialog is not centered when it is opened for the first time
        self.about.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)

        self.get('version-label').set_text(
            f'key-mapper {VERSION} {COMMIT_HASH[:7]}'
            f'\npython-evdev {EVDEV_VERSION}' if EVDEV_VERSION else ''
        )

        window = self.get('window')
        window.show()
        # hide everything until stuff is populated
        self.get('vertical-wrapper').set_opacity(0)
        self.window = window

        # if any of the next steps take a bit to complete, have the window
        # already visible (without content) to make it look more responsive.
        gtk_iteration()

        # this is not set to invisible in glade to give the ui a default
        # height that doesn't jump when a gamepad is selected
        self.get('gamepad_separator').hide()
        self.get('gamepad_config').hide()

        self.populate_devices()

        self.timeouts = [
            GLib.timeout_add(100, self.check_add_row),
            GLib.timeout_add(1000 / 30, self.consume_newest_keycode)
        ]

        # now show the proper finished content of the window
        self.get('vertical-wrapper').set_opacity(1)

        self.ctrl = False
        self.unreleased_warn = False
        self.button_left_warn = False

        if not is_helper_running():
            self.show_status(CTX_ERROR, 'The helper did not start')

    def start_processes(self):
        """Start helper and daemon via pkexec to run in the background."""
        # this function is overwritten in tests
        self.dbus = Daemon.connect()

        debug = ' -d' if is_debug() else ''
        cmd = f'pkexec key-mapper-control --command helper {debug}'

        logger.debug('Running `%s`', cmd)
        exit_code = os.system(cmd)

        if exit_code != 0:
            logger.error('Failed to pkexec the helper, code %d', exit_code)
            sys.exit()

    def show_confirm_delete(self):
        """Blocks until the user decided about an action."""
        text = f'Are you sure to delete preset "{self.selected_preset}"?'
        self.get('confirm-delete-label').set_text(text)

        self.confirm_delete.show()
        response = self.confirm_delete.run()
        self.confirm_delete.hide()
        return response

    def key_press(self, _, event):
        """To execute shortcuts.

        This has nothing to do with the keycode reader.
        """
        _, focused = self.get_focused_row()
        if isinstance(focused, Gtk.ToggleButton):
            return

        gdk_keycode = event.get_keyval()[1]

        if gdk_keycode in [Gdk.KEY_Control_L, Gdk.KEY_Control_R]:
            self.ctrl = True

        if self.ctrl:
            # shortcuts
            if gdk_keycode == Gdk.KEY_q:
                self.on_close()

            if gdk_keycode == Gdk.KEY_r:
                reader.get_devices()

            if gdk_keycode == Gdk.KEY_Delete:
                self.on_restore_defaults_clicked()

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
        if GAMEPAD in devices[self.selected_device]['types']:
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
        self.save_preset()
        self.window.hide()
        for timeout in self.timeouts:
            GLib.source_remove(timeout)
            self.timeouts = []
        reader.terminate()
        Gtk.main_quit()

    def check_add_row(self):
        """Ensure that one empty row is available at all times."""
        rows = self.get('key_list').get_children()

        # verify that all mappings are displayed.
        # One of them is possibly the empty row
        num_rows = len(rows)
        num_maps = len(custom_mapping)
        if num_rows < num_maps or num_rows > num_maps + 1:
            logger.error(
                'custom_mapping contains %d rows, '
                'but %d are displayed',
                len(custom_mapping), num_rows
            )
            logger.spam(
                'Mapping %s',
                list(custom_mapping)
            )
            logger.spam(
                'Rows    %s',
                [(row.get_key(), row.get_character()) for row in rows]
            )

        # iterating over that 10 times per second is a bit wasteful,
        # but the old approach which involved just counting the number of
        # mappings and rows didn't seem very robust.
        for row in rows:
            if row.get_key() is None or row.get_character() is None:
                # unfinished row found
                break
        else:
            self.add_empty()

        return True

    def select_newest_preset(self):
        """Find and select the newest preset (and its device)."""
        device, preset = find_newest_preset()
        if device is not None:
            self.get('device_selection').set_active_id(device)
        if preset is not None:
            self.get('preset_selection').set_active_id(preset)

    def populate_devices(self):
        """Make the devices selectable."""
        devices = get_devices()
        device_selection = self.get('device_selection')

        with HandlerDisabled(device_selection, self.on_select_device):
            self.device_store.clear()
            for device in devices:
                types = devices[device]['types']
                significant_type = sorted(types, key=ICON_PRIORITIES.index)[0]
                icon_name = ICON_NAMES[significant_type]
                self.device_store.append([icon_name, device])

        self.select_newest_preset()

    def populate_presets(self):
        """Show the available presets for the selected device.

        This will destroy unsaved changes in the custom_mapping.
        """
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

        with HandlerDisabled(preset_selection, self.on_select_preset):
            # otherwise the handler is called with None for each preset
            preset_selection.remove_all()

        for preset in presets:
            preset_selection.append(preset, preset)
        # and select the newest one (on the top). triggers on_select_preset
        preset_selection.set_active(0)

    def clear_mapping_table(self):
        """Remove all rows from the mappings table."""
        key_list = self.get('key_list')
        key_list.forall(key_list.remove)
        custom_mapping.empty()

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

    def consume_newest_keycode(self):
        """To capture events from keyboards, mice and gamepads."""
        # the "event" event of Gtk.Window wouldn't trigger on gamepad
        # events, so it became a GLib timeout to periodically check kernel
        # events.

        # letting go of one of the keys of a combination won't just make
        # it return the leftover key, it will continue to return None because
        # they have already been read.
        key = reader.read()

        if reader.are_new_devices_available():
            self.populate_devices()

        # TODO highlight if a row for that key exists or something

        # inform the currently selected row about the new keycode
        row, focused = self.get_focused_row()
        if key is not None:
            if isinstance(focused, Gtk.ToggleButton):
                row.set_new_key(key)

            if key.is_problematic() and isinstance(focused, Gtk.ToggleButton):
                self.show_status(
                    CTX_WARNING,
                    'ctrl, alt and shift may not combine properly',
                    'Your system might reinterpret combinations ' +
                    'with those after they are injected, and by doing so ' +
                    'break them.'
                )

        if row is not None:
            row.refresh_state()

        return True

    @with_selected_device
    def on_restore_defaults_clicked(self, *_):
        """Stop injecting the mapping."""
        self.dbus.stop_injecting(self.selected_device)
        self.show_status(CTX_APPLY, 'Applied the system default')
        GLib.timeout_add(100, self.show_device_mapping_status)

    def show_status(self, context_id, message, tooltip=None):
        """Show a status message and set its tooltip.

        If message is None, it will remove the newest message of the
        given context_id.
        """
        status_bar = self.get('status_bar')

        if message is None:
            status_bar.remove_all(context_id)

            if context_id in (CTX_ERROR, CTX_MAPPING):
                self.get('error_status_icon').hide()

            if context_id == CTX_WARNING:
                self.get('warning_status_icon').hide()

            status_bar.set_tooltip_text('')
        else:
            if tooltip is None:
                tooltip = message

            self.get('error_status_icon').hide()
            self.get('warning_status_icon').hide()

            if context_id in (CTX_ERROR, CTX_MAPPING):
                self.get('error_status_icon').show()

            if context_id == CTX_WARNING:
                self.get('warning_status_icon').show()

            if len(message) > 55:
                message = message[:52] + '...'

            status_bar.push(context_id, message)
            status_bar.set_tooltip_text(tooltip)

    def check_macro_syntax(self):
        """Check if the programmed macros are allright."""
        self.show_status(CTX_MAPPING, None)
        for key, output in custom_mapping:
            if not is_this_a_macro(output):
                continue

            error = parse(output, custom_mapping, return_errors=True)
            if error is None:
                continue

            position = to_string(key)
            msg = f'Syntax error at {position}, hover for info'
            self.show_status(CTX_MAPPING, msg, error)

    def on_rename_button_clicked(self, _):
        """Rename the preset based on the contents of the name input."""
        new_name = self.get('preset_name_input').get_text()

        if new_name in ['', self.selected_preset]:
            return

        self.save_preset()

        new_name = rename_preset(
            self.selected_device,
            self.selected_preset,
            new_name
        )

        # if the old preset was being autoloaded, change the
        # name there as well
        is_autoloaded = config.is_autoloaded(
            self.selected_device,
            self.selected_preset
        )
        if is_autoloaded:
            config.set_autoload_preset(self.selected_device, new_name)

        self.get('preset_name_input').set_text('')
        self.populate_presets()

    @with_selected_preset
    def on_delete_preset_clicked(self, _):
        """Delete a preset from the file system."""
        accept = Gtk.ResponseType.ACCEPT
        if len(custom_mapping) > 0 and self.show_confirm_delete() != accept:
            return

        custom_mapping.changed = False
        delete_preset(self.selected_device, self.selected_preset)
        self.populate_presets()

    @with_selected_preset
    def on_apply_preset_clicked(self, _):
        """Apply a preset without saving changes."""
        self.save_preset()

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

        if not self.button_left_warn:
            if custom_mapping.dangerously_mapped_btn_left():
                self.show_status(
                    CTX_ERROR,
                    'This would disable your click button',
                    'Map a button to BTN_Left to avoid this.\n'
                    'To overwrite this warning, press apply again.'
                )
                self.button_left_warn = True
                return

        if not self.unreleased_warn:
            unreleased = reader.get_unreleased_keys()
            if unreleased is not None and unreleased != Key.btn_left():
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
        self.button_left_warn = False
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
        self.save_preset()

        if dropdown.get_active_id() == self.selected_device:
            return

        # selecting a device will also automatically select a different
        # preset. Prevent another unsaved-changes dialog to pop up
        custom_mapping.changed = False

        device = dropdown.get_active_id()

        if device is None:
            return

        logger.debug('Selecting device "%s"', device)

        self.selected_device = device
        self.selected_preset = None

        self.populate_presets()

        reader.start_reading(device)

        self.show_device_mapping_status()

    def show_injection_result(self):
        """Show if the injection was successfully started."""
        state = self.dbus.get_state(self.selected_device)

        if state == RUNNING:
            msg = f'Applied preset "{self.selected_preset}"'

            if custom_mapping.get_character(Key.btn_left()):
                msg += ', CTRL + DEL to stop'

            self.show_status(CTX_APPLY, msg)

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
        state = self.dbus.get_state(device)
        if state == RUNNING:
            logger.info('Device "%s" is currently mapped', device)
            self.get('apply_system_layout').set_opacity(1)
        else:
            self.get('apply_system_layout').set_opacity(0.4)

    @with_selected_preset
    def on_copy_preset_clicked(self, _):
        """Copy the current preset and select it."""
        self.create_preset(True)

    @with_selected_device
    def on_create_preset_clicked(self, _):
        """Create a new preset and select it."""
        self.create_preset()

    def create_preset(self, copy=False):
        """Create a new preset and select it."""
        self.save_preset()

        try:
            if copy:
                new_preset = get_available_preset_name(
                    self.selected_device,
                    self.selected_preset,
                    copy
                )
            else:
                new_preset = get_available_preset_name(
                    self.selected_device
                )
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
        # beware in tests that this function won't be called at all if the
        # active_id stays the same
        self.save_preset()

        if dropdown.get_active_id() == self.selected_preset:
            return

        self.clear_mapping_table()

        preset = dropdown.get_active_text()
        if preset is None:
            return

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
        self.save_preset()

    def on_right_joystick_changed(self, dropdown):
        """Set the purpose of the right joystick."""
        purpose = dropdown.get_active_id()
        custom_mapping.set('gamepad.joystick.right_purpose', purpose)
        self.save_preset()

    def on_joystick_mouse_speed_changed(self, gtk_range):
        """Set how fast the joystick moves the mouse."""
        speed = 2 ** gtk_range.get_value()
        custom_mapping.set('gamepad.joystick.pointer_speed', speed)

    def add_empty(self):
        """Add one empty row for a single mapped key."""
        empty = Row(window=self, delete_callback=self.on_row_removed)
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

    def save_preset(self, *_):
        """Write changes to presets to disk."""
        if not custom_mapping.changed:
            return

        try:
            path = get_preset_path(self.selected_device, self.selected_preset)
            custom_mapping.save(path)

            custom_mapping.changed = False

            # after saving the config, its modification date will be the
            # newest, so populate_presets will automatically select the
            # right one again.
            self.populate_presets()
        except PermissionError as error:
            error = str(error)
            self.show_status(CTX_ERROR, 'Permission denied!', error)
            logger.error(error)

        for _, character in custom_mapping:
            if is_this_a_macro(character):
                continue

            if system_mapping.get(character) is None:
                self.show_status(CTX_MAPPING, f'Unknown mapping "{character}"')
                break
        else:
            # no broken mappings found
            self.show_status(CTX_MAPPING, None)

            # checking macros is probably a bit more expensive, do that if
            # the regular mappings are allright
            self.check_macro_syntax()

    def on_about_clicked(self, _):
        """Show the about/help dialog."""
        self.about.show()

    def on_about_key_press(self, _, event):
        """Hide the about/help dialog."""
        gdk_keycode = event.get_keyval()[1]
        if gdk_keycode == Gdk.KEY_Escape:
            self.about.hide()
