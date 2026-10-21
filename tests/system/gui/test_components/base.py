
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2026 sezanzeb <4t1pzast9@mozmail.com>
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

import unittest
from unittest.mock import MagicMock

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GLib", "2.0")
gi.require_version("GtkSource", "4")
from gi.repository import GLib, Gtk

from inputremapper.gui.controller import Controller
from inputremapper.gui.messages.message_broker import (
    MessageBroker,
    MessageType,
)
from tests.lib.logger import logger


class ComponentBaseTest(unittest.TestCase):
    """Test a gui component."""

    def setUp(self) -> None:
        self.message_broker = MessageBroker()
        self.controller_mock: Controller = MagicMock()

    def destroy_all_member_widgets(self):
        # destroy all Gtk Widgets that are stored in self
        # TODO why is this necessary?
        for attribute in dir(self):
            stuff = getattr(self, attribute, None)
            if isinstance(stuff, Gtk.Widget):
                logger.info('destroying member "%s" %s', attribute, stuff)
                GLib.timeout_add(0, stuff.destroy)
                setattr(self, attribute, None)

    def tearDown(self) -> None:
        super().tearDown()
        self.message_broker.signal(MessageType.terminate)

        # Shut down the gui properly
        self.destroy_all_member_widgets()
        GLib.timeout_add(0, Gtk.main_quit)

        # Gtk.main() will start the Gtk event loop and process all pending events.
        # So the gui will do whatever is queued up this ensures that the next tests
        # starts without pending events.
        Gtk.main()
