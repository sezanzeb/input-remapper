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
from typing import Dict, Callable

from gi.repository import Gtk, GtkSource, Gdk, GObject

from inputremapper.configs.data import get_data_path
from inputremapper.configs.mapping import MappingData
from inputremapper.event_combination import EventCombination
from inputremapper.gui.autocompletion import Autocompletion
from inputremapper.gui.components.editor import (
    MappingListBox,
    TargetSelection,
    CodeEditor,
    RecordingToggle,
    RecordingStatus,
    AutoloadSwitch,
    ReleaseCombinationSwitch,
    CombinationListbox,
    AnalogInputSwitch,
    TriggerThresholdInput,
    OutputAxisSelector,
    ReleaseTimeoutInput,
    TransformationDrawArea,
    Sliders,
    RelativeInputCutoffInput,
    KeyAxisStackSwitcher,
    RequireActiveMapping,
)
from inputremapper.gui.components.presets import PresetSelection
from inputremapper.gui.components.main import Stack, StatusBar
from inputremapper.gui.components.common import Breadcrumbs
from inputremapper.gui.components.device_groups import DeviceGroupSelection
from inputremapper.gui.controller import Controller
from inputremapper.gui.message_broker import (
    MessageBroker,
    MessageType,
    UserConfirmRequest,
)
from inputremapper.gui.utils import (
    gtk_iteration,
)
from inputremapper.injection.injector import InjectorState
from inputremapper.logger import logger, COMMIT_HASH, VERSION, EVDEV_VERSION
from inputremapper.gui.gettext import _

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
        message_broker: MessageBroker,
        controller: Controller,
    ):
        self.message_broker = message_broker
        self.controller = controller

        # all shortcuts executed when ctrl+...
        self.shortcuts: Dict[int, Callable] = {
            Gdk.KEY_q: self.controller.close,
            Gdk.KEY_r: self.controller.refresh_groups,
            Gdk.KEY_Delete: self.controller.stop_injecting,
            Gdk.KEY_n: self.controller.add_preset,
        }

        # stores the ids for all the listeners attached to the gui
        self.gtk_listeners: Dict[Callable, int] = {}

        self.message_broker.subscribe(MessageType.terminate, lambda _: self.close())

        self.builder = Gtk.Builder()
        self._build_ui()
        self.window: Gtk.Window = self.get("window")
        self.about: Gtk.Window = self.get("about-dialog")
        self.combination_editor: Gtk.Dialog = self.get("combination-editor")

        self._create_dialogs()
        self._create_components()
        self._connect_gtk_signals()
        self._connect_message_listener()

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
        message_broker = self.message_broker
        controller = self.controller
        DeviceGroupSelection(message_broker, controller, self.get("device_selection"))
        PresetSelection(message_broker, controller, self.get("preset_selection"))
        MappingListBox(message_broker, controller, self.get("selection_label_listbox"))
        TargetSelection(message_broker, controller, self.get("target-selector"))

        Breadcrumbs(
            message_broker,
            self.get("selected_device_name"),
            show_device_group=True,
        )
        Breadcrumbs(
            message_broker,
            self.get("selected_preset_name"),
            show_device_group=True,
            show_preset=True,
        )

        Stack(message_broker, controller, self.get("main_stack"))
        RecordingToggle(message_broker, controller, self.get("key_recording_toggle"))
        StatusBar(
            message_broker,
            controller,
            self.get("status_bar"),
            self.get("error_status_icon"),
            self.get("warning_status_icon"),
        )
        RecordingStatus(message_broker, self.get("recording_status"))
        AutoloadSwitch(message_broker, controller, self.get("preset_autoload_switch"))
        ReleaseCombinationSwitch(
            message_broker, controller, self.get("release-combination-switch")
        )
        CombinationListbox(message_broker, controller, self.get("combination-listbox"))
        AnalogInputSwitch(message_broker, controller, self.get("analog-input-switch"))
        TriggerThresholdInput(
            message_broker, controller, self.get("trigger-threshold-spin-btn")
        )
        RelativeInputCutoffInput(
            message_broker, controller, self.get("input-cutoff-spin-btn")
        )
        OutputAxisSelector(message_broker, controller, self.get("output-axis-selector"))
        KeyAxisStackSwitcher(
            message_broker,
            controller,
            self.get("editor-stack"),
            self.get("key_macro_toggle_btn"),
            self.get("analog_toggle_btn"),
        )
        ReleaseTimeoutInput(
            message_broker, controller, self.get("release-timeout-spin-button")
        )
        TransformationDrawArea(
            message_broker, controller, self.get("transformation-draw-area")
        )
        Sliders(
            message_broker,
            controller,
            self.get("gain-scale"),
            self.get("deadzone-scale"),
            self.get("expo-scale"),
        )

        RequireActiveMapping(
            message_broker,
            controller,
            self.get("edit-combination-btn"),
            require_recorded_input=True,
        )
        RequireActiveMapping(
            message_broker,
            controller,
            self.get("output"),
            require_recorded_input=True,
        )
        RequireActiveMapping(
            message_broker,
            controller,
            self.get("delete-mapping"),
            require_recorded_input=False,
        )

        # code editor and autocompletion
        code_editor = CodeEditor(message_broker, controller, self.get("code_editor"))
        autocompletion = Autocompletion(message_broker, code_editor)
        autocompletion.set_relative_to(self.get("code_editor_container"))
        self.autocompletion = autocompletion  # only for testing

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
        self.get("stop_injection_preset_page").connect(
            "clicked", lambda *_: self.controller.stop_injecting()
        )
        self.get("stop_injection_editor_page").connect(
            "clicked", lambda *_: self.controller.stop_injecting()
        )
        self.get("rename-button").connect("clicked", self.on_gtk_rename_clicked)
        self.get("preset_name_input").connect(
            "key-release-event", self.on_gtk_preset_name_input_return
        )
        self.get("create_mapping_button").connect(
            "clicked", lambda *_: self.controller.create_mapping()
        )
        self.get("delete-mapping").connect(
            "clicked", lambda *_: self.controller.delete_mapping()
        )
        self.combination_editor.connect(
            # it only takes self as argument, but delete-events provides more
            # probably a gtk bug
            "delete-event",
            lambda dialog, *_: Gtk.Widget.hide_on_delete(dialog),
        )
        self.get("edit-combination-btn").connect(
            "clicked", lambda *_: self.combination_editor.show()
        )
        self.get("remove-event-btn").connect(
            "clicked", lambda *_: self.controller.remove_event()
        )
        self.connect_shortcuts()

    def _connect_message_listener(self):
        self.message_broker.subscribe(
            MessageType.mapping, self.update_combination_label
        )
        self.message_broker.subscribe(
            MessageType.injector_state, self.on_injector_state_msg
        )
        self.message_broker.subscribe(
            MessageType.user_confirm_request, self._on_user_confirm_request
        )

    def _create_dialog(self, primary: str, secondary: str) -> Gtk.MessageDialog:
        """Create a message dialog with cancel and confirm buttons."""
        message_dialog = Gtk.MessageDialog(
            self.window,
            Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
            Gtk.MessageType.QUESTION,
            Gtk.ButtonsType.NONE,
            primary,
        )

        if secondary:
            message_dialog.format_secondary_text(secondary)

        message_dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)

        confirm_button = message_dialog.add_button("Confirm", Gtk.ResponseType.ACCEPT)
        confirm_button.get_style_context().add_class(Gtk.STYLE_CLASS_DESTRUCTIVE_ACTION)

        return message_dialog

    def _on_user_confirm_request(self, msg: UserConfirmRequest):
        # if the message contains a line-break, use the first chunk for the primary
        # message, and the rest for the secondary message.
        chunks = msg.msg.split("\n")
        primary = chunks[0]
        secondary = " ".join(chunks[1:])

        message_dialog = self._create_dialog(primary, secondary)

        response = message_dialog.run()
        msg.respond(response == Gtk.ResponseType.ACCEPT)

        message_dialog.hide()

    def on_injector_state_msg(self, msg: InjectorState):
        """update the ui to reflect the status of the injector"""
        stop_injection_preset_page: Gtk.Button = self.get("stop_injection_preset_page")
        stop_injection_editor_page: Gtk.Button = self.get("stop_injection_editor_page")
        recording_toggle: Gtk.ToggleButton = self.get("key_recording_toggle")

        if msg.active():
            stop_injection_preset_page.set_opacity(1)
            stop_injection_editor_page.set_opacity(1)
            stop_injection_preset_page.set_sensitive(True)
            stop_injection_editor_page.set_sensitive(True)
            recording_toggle.set_opacity(0.5)
        else:
            stop_injection_preset_page.set_opacity(0.5)
            stop_injection_editor_page.set_opacity(0.5)
            stop_injection_preset_page.set_sensitive(True)
            stop_injection_editor_page.set_sensitive(True)
            recording_toggle.set_opacity(1)

    def disconnect_shortcuts(self):
        """Stop listening for shortcuts.

        e.g. when recording key combinations
        """
        try:
            self.window.disconnect(self.gtk_listeners.pop(self.on_gtk_shortcut))
        except KeyError:
            logger.debug("key listeners seem to be not connected")

    def connect_shortcuts(self):
        """Start listening for shortcuts."""
        if not self.gtk_listeners.get(self.on_gtk_shortcut):
            self.gtk_listeners[self.on_gtk_shortcut] = self.window.connect(
                "key-press-event", self.on_gtk_shortcut
            )

    def get(self, name):
        """Get a widget from the window"""
        return self.builder.get_object(name)

    def close(self):
        """Close the window"""
        logger.debug("Closing window")
        self.window.hide()

    def update_combination_label(self, mapping: MappingData):
        """listens for mapping and updates the combination label"""
        label: Gtk.Label = self.get("combination-label")
        if mapping.event_combination.beautify() == label.get_label():
            return
        if mapping.event_combination == EventCombination.empty_combination():
            label.set_opacity(0.5)
            label.set_label(_("no input configured"))
            return

        label.set_opacity(1)
        label.set_label(mapping.event_combination.beautify())

    def on_gtk_shortcut(self, _, event: Gdk.EventKey):
        """execute shortcuts"""
        if event.state & Gdk.ModifierType.CONTROL_MASK:
            try:
                self.shortcuts[event.keyval]()
            except KeyError:
                pass

    def on_gtk_close(self, *_):
        self.controller.close()

    def on_gtk_about_clicked(self, _):
        """Show the about/help dialog."""
        self.about.show()

    def on_gtk_about_key_press(self, _, event):
        """Hide the about/help dialog."""
        gdk_keycode = event.get_keyval()[1]
        if gdk_keycode == Gdk.KEY_Escape:
            self.about.hide()

    def on_gtk_rename_clicked(self, *_):
        name = self.get("preset_name_input").get_text()
        self.controller.rename_preset(name)
        self.get("preset_name_input").set_text("")

    def on_gtk_preset_name_input_return(self, _, event: Gdk.EventKey):
        if event.keyval == Gdk.KEY_Return:
            self.on_gtk_rename_clicked()
