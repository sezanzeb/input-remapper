# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2025 sezanzeb <b8x45ygc9@mozmail.com>
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


"""Components used in multiple places."""

from __future__ import annotations

from gi.repository import Gtk

from inputremapper.gui.controller import Controller
from inputremapper.gui.messages.message_broker import (
    MessageBroker,
    MessageType,
)
from inputremapper.gui.utils import HandlerDisabled
from inputremapper.gui.gettext import _
from inputremapper.logging.logger import logger


class SuspendButton:
    """A button that suspends all injections or resumes them."""

    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        toggle_button: Gtk.ToggleButton,
    ):
        self._message_broker = message_broker
        self._gui = toggle_button
        self.controller = controller

        self.global_switch_handler = self._gui.connect(
            "toggled",
            self._on_global_switch_toggled,
        )

        # Initialize the toggled state and tooltip
        self._update_global_switch()

    def _update_global_switch(self, *_args) -> None:
        is_suspended = True
        try:
            is_suspended = self.controller.data_manager._daemon.is_suspended()
        except Exception as e:
            logger.error("Failed to query suspended state from daemon: %s", e)

        if is_suspended:
            self._gui.set_tooltip_text(_("Enable all suspended presets"))
            self._gui.set_image(Gtk.Image.new_from_icon_name("media-playback-start", Gtk.IconSize.MENU))
            self._gui.set_label("Resume ")
        else:
            self._gui.set_tooltip_text(_("Temporarily pause all active presets"))
            self._gui.set_image(Gtk.Image.new_from_icon_name("media-playback-pause", Gtk.IconSize.MENU))
            self._gui.set_label("Suspend")

        with HandlerDisabled(self._gui, self._on_global_switch_toggled):
            self._gui.set_active(is_suspended)

    def _on_global_switch_toggled(self, widget) -> bool:
        state = widget.get_active()
        try:
            self.controller.data_manager._daemon.set_suspended(state)
        except Exception as e:
            logger.error("Failed to toggle global suspend state: %s", e)
        self._update_global_switch()
        return False

    def _connect_message_listener(self):
        self._message_broker.subscribe(MessageType.preset, self._update_global_switch)
        self._message_broker.subscribe(MessageType.group, self._update_global_switch)
