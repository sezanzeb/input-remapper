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
from collections import defaultdict
from typing import Dict, Callable
from gi.repository import Gtk, GtkSource, Gdk, GObject

from inputremapper.gui.components import (
    DeviceSelection,
    PresetSelection,
    MappingListBox,
    TargetSelection,
    CodeEditor,
    RecordingToggle,
    StatusBar,
    AutoloadToggle,
)
from inputremapper.gui.controller import Controller
from inputremapper.gui.data_bus import DataBus, MessageType
from inputremapper.gui.autocompletion import Autocompletion
from inputremapper.configs.data import get_data_path
from inputremapper.configs.system_mapping import system_mapping
from inputremapper.logger import logger, COMMIT_HASH, VERSION, EVDEV_VERSION
from inputremapper.gui.utils import (
    gtk_iteration,
)


# TODO add to .deb and AUR dependencies
# https://cjenkins.wordpress.com/2012/05/08/use-gtksourceview-widget-in-glade/
GObject.type_register(GtkSource.View)
# GtkSource.View() also works:
# https://stackoverflow.com/questions/60126579/gtk-builder-error-quark-invalid-object-type-webkitwebview


def on_close_about(about, _):
    """Hide the about dialog without destroying it."""
    about.hide()
    return True


class UserInterface:
    """The input-remapper gtk window."""

    def __init__(
        self,
        data_bus: DataBus,
        controller: Controller,
    ):
        self.data_bus = data_bus
        self.controller = controller

        # all shortcuts executed when ctrl+...
        self.shortcuts: Dict[int, Callable] = {
            Gdk.KEY_q: self.controller.close,
            Gdk.KEY_r: self.controller.refresh_groups,
            Gdk.KEY_Delete: self.controller.stop_injecting,
        }

        # stores the ids for all the listeners attached to the gui
        self.gtk_listeners: Dict[Callable, int] = {}

        self.data_bus.subscribe(MessageType.terminate, lambda _: self.close())

        self.builder = Gtk.Builder()
        self._build_ui()
        self.window: Gtk.Window = self.get("window")
        self.confirm_delete_dialog: Gtk.MessageDialog = self.get("confirm-delete")
        self.about: Gtk.Window = self.get("about-dialog")

        self._create_dialogs()
        self._create_components()
        self._connect_gtk_signals()

        self.window.show()
        # hide everything until stuff is populated
        self.get("vertical-wrapper").set_opacity(0)
        # if any of the next steps take a bit to complete, have the window
        # already visible (without content) to make it look more responsive.
        gtk_iteration()

        # now show the proper finished content of the window
        self.get("vertical-wrapper").set_opacity(1)

    def _build_ui(self):
        """build the window from stylesheet and gladefile"""
        css_provider = Gtk.CssProvider()

        with open(get_data_path("style.css"), "r") as file:
            css_provider.load_from_data(bytes(file.read(), encoding="UTF-8"))

        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        gladefile = get_data_path("input-remapper.glade")
        self.builder.add_from_file(gladefile)
        self.builder.connect_signals(self)

    def _create_components(self):
        """setup all objects which manage individual components of the ui"""
        data_bus = self.data_bus
        controller = self.controller
        DeviceSelection(data_bus, controller, self.get("device_selection"))
        PresetSelection(data_bus, controller, self.get("preset_selection"))
        MappingListBox(data_bus, controller, self.get("selection_label_listbox"))
        TargetSelection(data_bus, controller, self.get("target-selector"))
        RecordingToggle(data_bus, controller, self.get("key_recording_toggle"))
        StatusBar(
            data_bus,
            controller,
            self.get("status_bar"),
            self.get("error_status_icon"),
            self.get("warning_status_icon"),
        )
        AutoloadToggle(data_bus, controller, self.get("preset_autoload_switch"))

        # code editor and autocompletion
        code_editor = CodeEditor(
            data_bus, controller, system_mapping, self.get("code_editor")
        )
        autocompletion = Autocompletion(data_bus, code_editor)
        autocompletion.set_relative_to(self.get("code_editor_container"))

    def _create_dialogs(self):
        """setup different dialogs, such as the about page"""
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

    def _connect_gtk_signals(self):
        self.get("delete_preset").connect(
            "clicked", lambda *_: self.controller.delete_preset()
        )
        self.get("copy_preset").connect(
            "clicked", lambda *_: self.controller.copy_preset()
        )
        self.get("create_preset").connect(
            "clicked", lambda *_: self.controller.add_preset()
        )
        self.get("apply_preset").connect(
            "clicked", lambda *_: self.controller.start_injecting()
        )
        self.get("apply_system_layout").connect(
            "clicked", lambda *_: self.controller.stop_injecting()
        )
        self.get("rename-button").connect("clicked", self.on_rename_clicked)
        self.get("preset_name_input").connect(
            "key-release-event", self.on_preset_name_input_return
        )
        self.get("create_mapping_button").connect(
            "clicked", lambda *_: self.controller.create_mapping()
        )
        self.get("delete-mapping").connect(
            "clicked", lambda *_: self.controller.delete_mapping()
        )
        self.connect_shortcuts()

    def on_rename_clicked(self, *_):
        name_input = self.get("preset_name_input")
        self.controller.rename_preset(name_input.get_text())
        name_input.set_text("")

    def on_preset_name_input_return(self, _, event: Gdk.EventKey):
        logger.debug(event)
        if event.keyval == Gdk.KEY_Return:
            self.on_rename_clicked()

    def confirm_delete(self, msg):
        """Blocks until the user decided about an action."""
        self.get("confirm-delete-label").set_text(msg)
        self.confirm_delete_dialog.show()
        response = self.confirm_delete_dialog.run()
        self.confirm_delete_dialog.hide()
        return response

    def disconnect_shortcuts(self):
        """stop listening for shortcuts

        e.g. when recording key combinations
        """
        try:
            self.window.disconnect(self.gtk_listeners[self.on_shortcut])
        except KeyError:
            logger.debug("key listeners seem to be not connected")

    def connect_shortcuts(self):
        """stop listening for shortcuts"""
        self.gtk_listeners[self.on_shortcut] = self.window.connect(
            "key-press-event", self.on_shortcut
        )

    def on_shortcut(self, _, event: Gdk.EventKey):
        """execute shortcuts"""
        if event.state & Gdk.ModifierType.CONTROL_MASK:
            try:
                self.shortcuts[event.keyval]()
            except KeyError:
                pass

    def get(self, name):
        """Get a widget from the window"""
        return self.builder.get_object(name)

    def on_close(self, *_):
        self.controller.close()

    def close(self):
        """Close the window"""
        logger.debug("Closing window")
        self.window.hide()

    def on_about_clicked(self, _):
        """Show the about/help dialog."""
        self.about.show()

    def on_about_key_press(self, _, event):
        """Hide the about/help dialog."""
        gdk_keycode = event.get_keyval()[1]
        if gdk_keycode == Gdk.KEY_Escape:
            self.about.hide()
