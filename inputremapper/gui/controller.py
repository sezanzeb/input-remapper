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
from __future__ import annotations  # needed for the TYPE_CHECKING import

from typing import TYPE_CHECKING, Optional, List, Tuple

from gi.repository import Gtk, GLib

from .data_bus import DataBus, MessageType, PresetData, StatusData
from .gettext import _
from .data_manager import DataManager, DEFAULT_PRESET_NAME
from ..event_combination import EventCombination
from ..injection.injector import RUNNING, FAILED, NO_GRAB, UPGRADE_EVDEV
from ..input_event import InputEvent
from ..logger import logger
from .utils import CTX_SAVE, CTX_APPLY, CTX_KEYCODE, CTX_ERROR, CTX_WARNING, CTX_MAPPING

if TYPE_CHECKING:
    # avoids gtk import error in tests
    from .user_interface import UserInterface


class Controller:
    """implements the behaviour of the gui"""

    def __init__(self, data_bus: DataBus, data_manager: DataManager):
        self.data_bus = data_bus
        self.data_manager = data_manager
        self.gui = None

        self.button_left_warn = False
        self.attach_to_events()

    def set_gui(self, gui: UserInterface):
        self.gui = gui

    def attach_to_events(self) -> None:
        self.data_bus.subscribe(MessageType.groups, self.on_groups_changed)
        self.data_bus.subscribe(MessageType.preset, self.on_preset_changed)
        self.data_bus.subscribe(MessageType.init, self.on_init)

    def get_a_preset(self) -> str:
        """attempts to get the newest preset in the current group
        creates a new preset if that fails"""
        try:
            return self.data_manager.newest_preset()
        except FileNotFoundError:
            pass
        self.data_manager.add_preset(self.data_manager.get_available_preset_name())
        return self.data_manager.newest_preset()

    def get_a_group(self) -> str:
        """attempts to get the group with the newest preset
        returns any if that fails"""
        try:
            return self.data_manager.newest_group()
        except FileNotFoundError:
            pass

        return self.data_manager.available_groups[0]

    def on_init(self, _):
        # make sure we get a groups_changed event when everything is ready
        # this might not be necessary if the helper takes longer to provide the
        # initial groups
        self.data_manager.backend.emit_groups()
        self.data_manager.emit_uinputs()

    def on_groups_changed(self, _):
        """load the newest group as soon as everyone got notified
        about the updated groups"""
        self.load_group(self.get_a_group())

    def on_preset_changed(self, data: PresetData):
        """load a mapping as soon as everyone got notified about the new preset"""
        if not data.mappings:
            return
        mappings = list(data.mappings)
        mappings.sort(key=lambda t: t[0] or t[1].beautify())
        combination = mappings[0][1]
        self.load_mapping(combination)

    def copy_preset(self):
        raise NotImplementedError

    def update_combination(self, combination: EventCombination):
        try:
            self.data_manager.update_mapping(event_combination=combination)
            self.save()
        except KeyError:
            # the combination was a duplicate
            pass

    def load_groups(self):
        self.data_manager.backend.refresh_groups()

    def load_group(self, group_key: str):
        self.data_manager.load_group(group_key)
        self.data_manager.load_preset(self.get_a_preset())

    def load_preset(self, name: str):
        self.data_manager.load_preset(name)

    def rename_preset(self, new_name: str):
        name = self.data_manager.get_available_preset_name(new_name)
        self.data_manager.rename_preset(name)

    def add_preset(self, name: str = DEFAULT_PRESET_NAME):
        name = self.data_manager.get_available_preset_name(name)
        self.data_manager.add_preset(name)
        self.data_manager.load_preset(name)

    def delete_preset(self):
        accept = Gtk.ResponseType.ACCEPT
        msg = (
            _("Are you sure to delete preset %s?") % self.data_manager.get_preset_name()
        )
        if self.data_manager.get_mappings() and self.gui.confirm_delete(msg) != accept:
            return
        self.data_manager.delete_preset()
        self.data_manager.load_preset(self.get_a_preset())

    def load_mapping(self, event_combination: EventCombination):
        self.data_manager.load_mapping(event_combination)

    def update_mapping(self, **kwargs):
        self.data_manager.update_mapping(**kwargs)
        self.save()

    def create_mapping(self):
        self.data_manager.create_mapping()
        self.data_manager.load_mapping(combination=EventCombination.empty_combination())

    def delete_mapping(self):
        accept = Gtk.ResponseType.ACCEPT
        if (
            self.data_manager.get_mappings()
            and self.gui.confirm_delete(_("Are you sure to delete this mapping?"))
            != accept
        ):
            return
        self.data_manager.delete_mapping()

    def set_autoload(self, autoload: bool):
        self.data_manager.set_autoload(autoload)

    def get_uinputs(self):
        self.data_manager.emit_uinputs()

    def save(self):
        self.data_manager.save()

    def start_key_recording(self):
        self.data_manager.backend.start_key_recording()

    def start_injecting(self):
        if len(self.data_manager.active_preset) == 0:
            logger.error(_("Cannot apply empty preset file"))
            # also helpful for first time use
            self.show_status(CTX_ERROR, _("You need to add keys and save first"))
            return

        if not self.button_left_warn:
            if self.data_manager.active_preset.dangerously_mapped_btn_left():
                self.show_status(
                    CTX_ERROR,
                    "This would disable your click button",
                    "Map a button to BTN_LEFT to avoid this.\n"
                    "To overwrite this warning, press apply again.",
                )
                self.button_left_warn = True
                return

        # todo: warn about unreleased keys

        self.button_left_warn = False
        if self.data_manager.start_injecting():
            self.show_status(CTX_APPLY, _("Starting injection..."))
        else:
            self.show_status(
                CTX_APPLY,
                _("Failed to apply preset %s") % self.data_manager.get_preset_name(),
            )
            pass

    def stop_injecting(self):
        self.data_manager.stop_injecting()
        self.show_status(CTX_APPLY, _("Applied the system default"))

    def show_status(self, ctx_id: int, msg: str, tooltip: Optional[str] = None):
        self.data_bus.send(StatusData(ctx_id, msg, tooltip))
