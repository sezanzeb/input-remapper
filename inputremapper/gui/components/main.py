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


"""Components that wrap everything."""


from __future__ import annotations

from gi.repository import Gtk, Pango

from inputremapper.gui.controller import Controller
from inputremapper.gui.messages.message_broker import (
    MessageBroker,
    MessageType,
)
from inputremapper.gui.messages.message_data import StatusData, DoStackSwitch
from inputremapper.gui.utils import CTX_ERROR, CTX_MAPPING, CTX_WARNING


class Stack:
    """Wraps the Stack, which contains the main menu pages."""

    devices_page = 0
    presets_page = 1
    editor_page = 2

    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        stack: Gtk.Stack,
    ):
        self._message_broker = message_broker
        self._controller = controller
        self._gui = stack

        self._message_broker.subscribe(
            MessageType.do_stack_switch, self._do_stack_switch
        )

    def _do_stack_switch(self, msg: DoStackSwitch):
        self._gui.set_visible_child(self._gui.get_children()[msg.page_index])


class StatusBar:
    """The status bar on the bottom of the main window."""

    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        status_bar: Gtk.Statusbar,
        error_icon: Gtk.Image,
        warning_icon: Gtk.Image,
    ):
        self._message_broker = message_broker
        self._controller = controller
        self._gui = status_bar
        self._error_icon = error_icon
        self._warning_icon = warning_icon

        label = self._gui.get_message_area().get_children()[0]
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_selectable(True)

        self._message_broker.subscribe(MessageType.status_msg, self._on_status_update)

        # keep track if there is an error or warning in the stack of statusbar
        # unfortunately this is not exposed over the api
        self._error = False
        self._warning = False

    def _on_status_update(self, data: StatusData):
        """Show a status message and set its tooltip.

        If message is None, it will remove the newest message of the
        given context_id.
        """
        context_id = data.ctx_id
        message = data.msg
        tooltip = data.tooltip
        status_bar = self._gui

        if message is None:
            status_bar.remove_all(context_id)

            if context_id in (CTX_ERROR, CTX_MAPPING):
                self._error_icon.hide()
                self._error = False
                if self._warning:
                    self._warning_icon.show()

            if context_id == CTX_WARNING:
                self._warning_icon.hide()
                self._warning = False
                if self._error:
                    self._error_icon.show()

            status_bar.set_tooltip_text("")
            return

        if tooltip is None:
            tooltip = message

        self._error_icon.hide()
        self._warning_icon.hide()

        if context_id in (CTX_ERROR, CTX_MAPPING):
            self._error_icon.show()
            self._error = True

        if context_id == CTX_WARNING:
            self._warning_icon.show()
            self._warning = True

        status_bar.push(context_id, message)
        status_bar.set_tooltip_text(tooltip)
