#!/usr/bin/python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2022 sezanzeb <proxima@sezanzeb.de>
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


"""User Interface."""


import math
import os
import re
import sys
from inputremapper.gui.gettext import _

from evdev._ecodes import EV_KEY
from gi.repository import Gtk, GtkSource, Gdk, GLib, GObject
from inputremapper.input_event import InputEvent

from inputremapper.configs.data import get_data_path
from inputremapper.configs.paths import get_config_path
from inputremapper.configs.system_mapping import system_mapping
from inputremapper.gui.active_preset import active_preset
from inputremapper.gui.utils import HandlerDisabled
from inputremapper.configs.preset import (
    find_newest_preset,
    get_presets,
    delete_preset,
    rename_preset,
    get_available_preset_name,
)
from inputremapper.logger import logger, COMMIT_HASH, VERSION, EVDEV_VERSION, is_debug
from inputremapper.groups import (
    groups,
    GAMEPAD,
    KEYBOARD,
    UNKNOWN,
    GRAPHICS_TABLET,
    TOUCHPAD,
    MOUSE,
)
from inputremapper.gui.editor.editor import Editor
from inputremapper.event_combination import EventCombination
from inputremapper.gui.reader import reader
from inputremapper.gui.helper import is_helper_running
from inputremapper.injection.injector import RUNNING, FAILED, NO_GRAB, UPGRADE_EVDEV
from inputremapper.daemon import Daemon
from inputremapper.configs.global_config import global_config
from inputremapper.injection.macros.parse import is_this_a_macro, parse
from inputremapper.injection.global_uinputs import global_uinputs
from inputremapper.gui.utils import (
    CTX_ERROR,
    CTX_MAPPING,
    CTX_APPLY,
    CTX_WARNING,
    gtk_iteration,
    debounce,
)


# TODO add to .deb and AUR dependencies
# https://cjenkins.wordpress.com/2012/05/08/use-gtksourceview-widget-in-glade/
GObject.type_register(GtkSource.View)
# GtkSource.View() also works:
# https://stackoverflow.com/questions/60126579/gtk-builder-error-quark-invalid-object-type-webkitwebview


CONTINUE = True
GO_BACK = False

ICON_NAMES = {
    GAMEPAD: "input-gaming",
    MOUSE: "input-mouse",
    KEYBOARD: "input-keyboard",
    GRAPHICS_TABLET: "input-tablet",
    TOUCHPAD: "input-touchpad",
    UNKNOWN: None,
}

# sort types that most devices would fall in easily to the right.
ICON_PRIORITIES = [GRAPHICS_TABLET, TOUCHPAD, GAMEPAD, MOUSE, KEYBOARD, UNKNOWN]


def if_group_selected(func):
    """Decorate a function to only execute if a device is selected."""
    # this should only happen if no device was found at all
    def wrapped(self, *args, **kwargs):
        if self.group is None:
            return True  # work with timeout_add

        return func(self, *args, **kwargs)

    return wrapped


def if_preset_selected(func):
    """Decorate a function to only execute if a preset is selected."""
    # this should only happen if no device was found at all
    def wrapped(self, *args, **kwargs):
        if self.preset_name is None or self.group is None:
            return True  # work with timeout_add

        return func(self, *args, **kwargs)

    return wrapped


def on_close_about(about, event):
    """Hide the about dialog without destroying it."""
    about.hide()
    return True


def ensure_everything_saved(func):
    """Make sure the editor has written its changes to active_preset and save."""

    def wrapped(self, *args, **kwargs):
        if self.preset_name:
            self.editor.gather_changes_and_save()

        return func(self, *args, **kwargs)

    return wrapped


class UserInterface:
    """The input-remapper gtk window."""

    def __init__(self):
        self.dbus = None

        self.start_processes()

        self.group = None
        self.preset_name = None

        global_uinputs.prepare_all()
        css_provider = Gtk.CssProvider()
        with open(get_data_path("style.css"), "r") as file:
            css_provider.load_from_data(bytes(file.read(), encoding="UTF-8"))

        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        gladefile = get_data_path("input-remapper.glade")
        builder = Gtk.Builder()
        builder.add_from_file(gladefile)
        builder.connect_signals(self)
        self.builder = builder

        self.editor = Editor(self)
        self.debounce_timeout = 100

        # set up the device selection
        # https://python-gtk-3-tutorial.readthedocs.io/en/latest/treeview.html#the-view
        combobox = self.get("device_selection")
        self.device_store = Gtk.ListStore(str, str, str)
        combobox.set_model(self.device_store)
        renderer_icon = Gtk.CellRendererPixbuf()
        renderer_text = Gtk.CellRendererText()
        renderer_text.set_padding(5, 0)
        combobox.pack_start(renderer_icon, False)
        combobox.pack_start(renderer_text, False)
        combobox.add_attribute(renderer_icon, "icon-name", 1)
        combobox.add_attribute(renderer_text, "text", 2)
        combobox.set_id_column(0)

        self.confirm_delete = builder.get_object("confirm-delete")
        self.about = builder.get_object("about-dialog")
        self.about.connect("delete-event", on_close_about)
        # set_position needs to be done once initially, otherwise the
        # dialog is not centered when it is opened for the first time
        self.about.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)

        self.get("version-label").set_text(
            f"input-remapper {VERSION} {COMMIT_HASH[:7]}"
            f"\npython-evdev {EVDEV_VERSION}"
            if EVDEV_VERSION
            else ""
        )

        window = self.get("window")
        window.show()
        # hide everything until stuff is populated
        self.get("vertical-wrapper").set_opacity(0)
        self.window = window

        source_view = self.get("code_editor")
        source_view.get_buffer().connect("changed", self.check_on_typing)

        # if any of the next steps take a bit to complete, have the window
        # already visible (without content) to make it look more responsive.
        gtk_iteration()

        # this is not set to invisible in glade to give the ui a default
        # height that doesn't jump when a gamepad is selected
        self.get("gamepad_separator").hide()
        self.get("gamepad_config").hide()

        self.populate_devices()

        self.timeouts = []
        self.setup_timeouts()

        # now show the proper finished content of the window
        self.get("vertical-wrapper").set_opacity(1)

        self.ctrl = False
        self.unreleased_warn = False
        self.button_left_warn = False

        if not is_helper_running():
            self.show_status(CTX_ERROR, _("The helper did not start"))

    def setup_timeouts(self):
        """Setup all GLib timeouts."""
        self.timeouts = [
            GLib.timeout_add(1000 / 30, self.consume_newest_keycode),
        ]

    def start_processes(self):
        """Start helper and daemon via pkexec to run in the background."""
        # this function is overwritten in tests
        self.dbus = Daemon.connect()

        debug = " -d" if is_debug() else ""
        cmd = f"pkexec input-remapper-control --command helper {debug}"

        logger.debug("Running `%s`", cmd)
        exit_code = os.system(cmd)

        if exit_code != 0:
            logger.error("Failed to pkexec the helper, code %d", exit_code)
            sys.exit(11)

    def show_confirm_delete(self):
        """Blocks until the user decided about an action."""
        text = _("Are you sure to delete preset %s?") % self.preset_name
        self.get("confirm-delete-label").set_text(text)

        self.confirm_delete.show()
        response = self.confirm_delete.run()
        self.confirm_delete.hide()
        return response

    def on_key_press(self, window, event):
        """To execute shortcuts.

        This has nothing to do with the keycode reader.
        """
        if self.editor.is_waiting_for_input():
            # don't perform shortcuts while keys are being recorded
            return

        gdk_keycode = event.get_keyval()[1]

        if gdk_keycode in [Gdk.KEY_Control_L, Gdk.KEY_Control_R]:
            self.ctrl = True

        if self.ctrl:
            # shortcuts
            if gdk_keycode == Gdk.KEY_q:
                self.on_close()

            if gdk_keycode == Gdk.KEY_r:
                reader.refresh_groups()

            if gdk_keycode == Gdk.KEY_Delete:
                self.on_stop_injecting_clicked()

    def on_key_release(self, window, event):
        """To execute shortcuts.

        This has nothing to do with the keycode reader.
        """
        gdk_keycode = event.get_keyval()[1]

        if gdk_keycode in [Gdk.KEY_Control_L, Gdk.KEY_Control_R]:
            self.ctrl = False

    def initialize_gamepad_config(self):
        """Set slider and dropdown values when a gamepad is selected."""
        if GAMEPAD in self.group.types:
            self.get("gamepad_separator").show()
            self.get("gamepad_config").show()
        else:
            self.get("gamepad_separator").hide()
            self.get("gamepad_config").hide()
            return

        left_purpose = self.get("left_joystick_purpose")
        right_purpose = self.get("right_joystick_purpose")
        speed = self.get("joystick_mouse_speed")

        with HandlerDisabled(left_purpose, self.on_left_joystick_changed):
            value = active_preset.get("gamepad.joystick.left_purpose")
            left_purpose.set_active_id(value)

        with HandlerDisabled(right_purpose, self.on_right_joystick_changed):
            value = active_preset.get("gamepad.joystick.right_purpose")
            right_purpose.set_active_id(value)

        with HandlerDisabled(speed, self.on_joystick_mouse_speed_changed):
            value = active_preset.get("gamepad.joystick.pointer_speed")
            range_value = math.log(value, 2)
            speed.set_value(range_value)

    def get(self, name):
        """Get a widget from the window"""
        return self.builder.get_object(name)

    @ensure_everything_saved
    def on_close(self, *args):
        """Safely close the application."""
        logger.debug("Closing window")
        self.window.hide()
        for timeout in self.timeouts:
            GLib.source_remove(timeout)
            self.timeouts = []
        reader.terminate()
        Gtk.main_quit()

    @ensure_everything_saved
    def select_newest_preset(self):
        """Find and select the newest preset (and its device)."""
        group_name, preset = find_newest_preset()
        if group_name is not None:
            self.get("device_selection").set_active_id(group_name)
        if preset is not None:
            self.get("preset_selection").set_active_id(preset)

    @ensure_everything_saved
    def populate_devices(self):
        """Make the devices selectable."""
        device_selection = self.get("device_selection")

        with HandlerDisabled(device_selection, self.on_select_device):
            self.device_store.clear()
            for group in groups.filter(include_inputremapper=False):
                types = group.types
                if len(types) > 0:
                    device_type = sorted(types, key=ICON_PRIORITIES.index)[0]
                    icon_name = ICON_NAMES[device_type]
                else:
                    icon_name = None

                self.device_store.append([group.key, icon_name, group.key])

        self.select_newest_preset()

    @if_group_selected
    @ensure_everything_saved
    def populate_presets(self):
        """Show the available presets for the selected device.

        This will destroy unsaved changes in the active_preset.
        """
        presets = get_presets(self.group.name)

        if len(presets) == 0:
            new_preset = get_available_preset_name(self.group.name)
            active_preset.empty()
            path = self.group.get_preset_path(new_preset)
            active_preset.save(path)
            presets = [new_preset]
        else:
            logger.debug('"%s" presets: "%s"', self.group.name, '", "'.join(presets))

        preset_selection = self.get("preset_selection")

        with HandlerDisabled(preset_selection, self.on_select_preset):
            # otherwise the handler is called with None for each preset
            preset_selection.remove_all()

        for preset in presets:
            preset_selection.append(preset, preset)

        # and select the newest one (on the top). triggers on_select_preset
        preset_selection.set_active(0)

    @if_group_selected
    def can_modify_preset(self, *args) -> bool:
        """if changing the preset is possible."""
        return self.dbus.get_state(self.group.key) != RUNNING

    def consume_newest_keycode(self):
        """To capture events from keyboards, mice and gamepads."""
        # the "event" event of Gtk.Window wouldn't trigger on gamepad
        # events, so it became a GLib timeout to periodically check kernel
        # events.

        # letting go of one of the keys of a combination won't just make
        # it return the leftover key, it will continue to return None because
        # they have already been read.
        combination = reader.read()

        if reader.are_new_groups_available():
            self.populate_devices()

        # giving editor its own interval and making it call reader.read itself causes
        # incredibly frustrating and miraculous problems. Do not do it. Observations:
        # - test_autocomplete_key fails if the gui has been launched and closed by a
        # previous test already
        # Maybe it has something to do with the order of editor.consume_newest_keycode
        # and user_interface.populate_devices.
        self.editor.consume_newest_keycode(combination)

        return True

    @if_group_selected
    def on_stop_injecting_clicked(self, *args):
        """Stop injecting the preset."""
        self.dbus.stop_injecting(self.group.key)
        self.show_status(CTX_APPLY, _("Applied the system default"))
        GLib.timeout_add(100, self.show_device_mapping_status)

    def show_status(self, context_id, message, tooltip=None):
        """Show a status message and set its tooltip.

        If message is None, it will remove the newest message of the
        given context_id.
        """
        status_bar = self.get("status_bar")

        if message is None:
            status_bar.remove_all(context_id)

            if context_id in (CTX_ERROR, CTX_MAPPING):
                self.get("error_status_icon").hide()

            if context_id == CTX_WARNING:
                self.get("warning_status_icon").hide()

            status_bar.set_tooltip_text("")
        else:
            if tooltip is None:
                tooltip = message

            self.get("error_status_icon").hide()
            self.get("warning_status_icon").hide()

            if context_id in (CTX_ERROR, CTX_MAPPING):
                self.get("error_status_icon").show()

            if context_id == CTX_WARNING:
                self.get("warning_status_icon").show()

            max_length = 45
            if len(message) > max_length:
                message = message[: max_length - 3] + "..."

            status_bar.push(context_id, message)
            status_bar.set_tooltip_text(tooltip)

    @debounce
    def check_on_typing(self, *_):
        """To save latest input from code editor and call syntax check."""
        self.editor.gather_changes_and_save()
        self.check_macro_syntax()

    def check_macro_syntax(self):
        """Check if the programmed macros are allright."""
        self.show_status(CTX_MAPPING, None)
        for key, output in active_preset:
            output = output[0]
            if not is_this_a_macro(output):
                continue

            error = parse(output, active_preset, return_errors=True)
            if error is None:
                continue

            position = key.beautify()
            msg = _("Syntax error at %s, hover for info") % position
            self.show_status(CTX_MAPPING, msg, error)

    @ensure_everything_saved
    def on_rename_button_clicked(self, button):
        """Rename the preset based on the contents of the name input."""
        new_name = self.get("preset_name_input").get_text()

        if new_name in ["", self.preset_name]:
            return

        new_name = rename_preset(self.group.name, self.preset_name, new_name)

        # if the old preset was being autoloaded, change the
        # name there as well
        is_autoloaded = global_config.is_autoloaded(self.group.key, self.preset_name)
        if is_autoloaded:
            global_config.set_autoload_preset(self.group.key, new_name)

        self.get("preset_name_input").set_text("")
        self.populate_presets()

    @if_preset_selected
    def on_delete_preset_clicked(self, *args):
        """Delete a preset from the file system."""
        accept = Gtk.ResponseType.ACCEPT
        if len(active_preset) > 0 and self.show_confirm_delete() != accept:
            return

        # avoid having the text of the symbol input leak into the active_preset again
        # via a gazillion hooks, causing the preset to be saved again after deleting.
        self.editor.clear()

        delete_preset(self.group.name, self.preset_name)

        self.populate_presets()

    @if_preset_selected
    def on_apply_preset_clicked(self, button):
        """Apply a preset without saving changes."""
        self.save_preset()

        if active_preset.num_saved_keys == 0:
            logger.error(_("Cannot apply empty preset file"))
            # also helpful for first time use
            self.show_status(CTX_ERROR, _("You need to add keys and save first"))
            return

        preset = self.preset_name
        logger.info('Applying preset "%s" for "%s"', preset, self.group.key)

        if not self.button_left_warn:
            if active_preset.dangerously_mapped_btn_left():
                self.show_status(
                    CTX_ERROR,
                    "This would disable your click button",
                    "Map a button to BTN_LEFT to avoid this.\n"
                    "To overwrite this warning, press apply again.",
                )
                self.button_left_warn = True
                return

        if not self.unreleased_warn:
            unreleased = reader.get_unreleased_keys()
            if unreleased is not None and unreleased != EventCombination(
                InputEvent.btn_left()
            ):
                # it's super annoying if that happens and may break the user
                # input in such a way to prevent disabling the preset
                logger.error(
                    "Tried to apply a preset while keys were held down: %s", unreleased
                )
                self.show_status(
                    CTX_ERROR,
                    "Please release your pressed keys first",
                    "X11 will think they are held down forever otherwise.\n"
                    "To overwrite this warning, press apply again.",
                )
                self.unreleased_warn = True
                return

        self.unreleased_warn = False
        self.button_left_warn = False
        self.dbus.set_config_dir(get_config_path())
        self.dbus.start_injecting(self.group.key, preset)

        self.show_status(CTX_APPLY, _("Starting injection..."))

        GLib.timeout_add(100, self.show_injection_result)

    def on_autoload_switch(self, switch, active):
        """Load the preset automatically next time the user logs in."""
        key = self.group.key
        preset = self.preset_name
        global_config.set_autoload_preset(key, preset if active else None)
        # tell the service to refresh its config
        self.dbus.set_config_dir(get_config_path())

    @ensure_everything_saved
    def on_select_device(self, dropdown):
        """List all presets, create one if none exist yet."""
        if self.group and dropdown.get_active_id() == self.group.key:
            return

        group_key = dropdown.get_active_id()

        if group_key is None:
            return

        logger.debug('Selecting device "%s"', group_key)

        self.group = groups.find(key=group_key)
        self.preset_name = None

        self.populate_presets()

        reader.start_reading(groups.find(key=group_key))

        self.show_device_mapping_status()

    def show_injection_result(self):
        """Show if the injection was successfully started."""
        state = self.dbus.get_state(self.group.key)

        if state == RUNNING:
            msg = _("Applied preset %s") % self.preset_name

            if active_preset.get_mapping(EventCombination(InputEvent.btn_left())):
                msg += _(", CTRL + DEL to stop")

            self.show_status(CTX_APPLY, msg)

            self.show_device_mapping_status()
            return False

        if state == FAILED:
            self.show_status(
                CTX_ERROR, _("Failed to apply preset %s") % self.preset_name
            )
            return False

        if state == NO_GRAB:
            self.show_status(
                CTX_ERROR,
                "The device was not grabbed",
                "Either another application is already grabbing it or "
                "your preset doesn't contain anything that is sent by the "
                "device.",
            )
            return False

        if state == UPGRADE_EVDEV:
            self.show_status(
                CTX_ERROR,
                "Upgrade python-evdev",
                "Your python-evdev version is too old.",
            )
            return False

        # keep the timeout running until a relevant state is found
        return True

    def show_device_mapping_status(self):
        """Figure out if this device is currently under inputremappers control."""
        self.editor.update_toggle_opacity()
        group_key = self.group.key
        state = self.dbus.get_state(group_key)
        if state == RUNNING:
            logger.info('Group "%s" is currently mapped', group_key)
            self.get("apply_system_layout").set_opacity(1)
        else:
            self.get("apply_system_layout").set_opacity(0.4)

    @if_preset_selected
    def on_copy_preset_clicked(self, *args):
        """Copy the current preset and select it."""
        self.create_preset(copy=True)

    @if_group_selected
    def on_create_preset_clicked(self, *args):
        """Create a new empty preset and select it."""
        self.create_preset()

    @ensure_everything_saved
    def create_preset(self, copy=False):
        """Create a new preset and select it."""
        name = self.group.name
        preset = self.preset_name

        try:
            if copy:
                new_preset = get_available_preset_name(name, preset, copy)
            else:
                new_preset = get_available_preset_name(name)
                self.editor.clear()
                active_preset.empty()

            path = self.group.get_preset_path(new_preset)
            active_preset.save(path)
            self.get("preset_selection").append(new_preset, new_preset)
            # triggers on_select_preset
            self.get("preset_selection").set_active_id(new_preset)
            if self.get("preset_selection").get_active_id() != new_preset:
                # for whatever reason I have to use set_active_id twice for this
                # to work in tests all of the sudden
                self.get("preset_selection").set_active_id(new_preset)
        except PermissionError as error:
            error = str(error)
            self.show_status(CTX_ERROR, _("Permission denied!"), error)
            logger.error(error)

    @ensure_everything_saved
    def on_select_preset(self, dropdown):
        """Show the mappings of the preset."""
        # beware in tests that this function won't be called at all if the
        # active_id stays the same
        if dropdown.get_active_id() == self.preset_name:
            return

        preset = dropdown.get_active_text()
        if preset is None:
            return

        logger.debug('Selecting preset "%s"', preset)
        self.editor.clear_mapping_list()
        self.preset_name = preset

        active_preset.load(self.group.get_preset_path(preset))

        self.editor.load_custom_mapping()

        autoload_switch = self.get("preset_autoload_switch")

        with HandlerDisabled(autoload_switch, self.on_autoload_switch):
            is_autoloaded = global_config.is_autoloaded(
                self.group.key, self.preset_name
            )
            autoload_switch.set_active(is_autoloaded)

        self.get("preset_name_input").set_text("")

        self.initialize_gamepad_config()

        active_preset.set_has_unsaved_changes(False)

    def on_left_joystick_changed(self, dropdown):
        """Set the purpose of the left joystick."""
        purpose = dropdown.get_active_id()
        active_preset.set("gamepad.joystick.left_purpose", purpose)
        self.save_preset()

    def on_right_joystick_changed(self, dropdown):
        """Set the purpose of the right joystick."""
        purpose = dropdown.get_active_id()
        active_preset.set("gamepad.joystick.right_purpose", purpose)
        self.save_preset()

    def on_joystick_mouse_speed_changed(self, gtk_range):
        """Set how fast the joystick moves the mouse."""
        speed = 2 ** gtk_range.get_value()
        active_preset.set("gamepad.joystick.pointer_speed", speed)

    def save_preset(self, *args):
        """Write changes in the active_preset to disk."""
        if not active_preset.has_unsaved_changes():
            # optimization, and also avoids tons of redundant logs
            logger.debug("Not saving because preset did not change")
            return

        try:
            assert self.preset_name is not None
            path = self.group.get_preset_path(self.preset_name)
            active_preset.save(path)

            # after saving the preset, its modification date will be the
            # newest, so populate_presets will automatically select the
            # right one again.
            self.populate_presets()
        except PermissionError as error:
            error = str(error)
            self.show_status(CTX_ERROR, _("Permission denied!"), error)
            logger.error(error)

        for _x, mapping in active_preset:
            if not mapping:
                continue

            symbol = mapping[0]
            target = mapping[1]
            if is_this_a_macro(symbol):
                continue

            code = system_mapping.get(symbol)
            if (
                code is None
                or code not in global_uinputs.get_uinput(target).capabilities()[EV_KEY]
            ):
                trimmed = re.sub(r"\s+", " ", symbol).strip()
                self.show_status(CTX_MAPPING, _("Unknown mapping %s") % trimmed)
                break
        else:
            # no broken mappings found
            self.show_status(CTX_MAPPING, None)

            # checking macros is probably a bit more expensive, do that if
            # the regular mappings are allright
            # self.check_macro_syntax()

    def on_about_clicked(self, button):
        """Show the about/help dialog."""
        self.about.show()

    def on_about_key_press(self, window, event):
        """Hide the about/help dialog."""
        gdk_keycode = event.get_keyval()[1]
        if gdk_keycode == Gdk.KEY_Escape:
            self.about.hide()
