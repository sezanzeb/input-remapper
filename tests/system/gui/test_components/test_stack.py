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


import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GLib", "2.0")
gi.require_version("GtkSource", "4")
from gi.repository import Gtk

from inputremapper.gui.components.main import Stack
from inputremapper.gui.messages.message_data import (
    DoStackSwitch,
)
from tests.lib.test_setup import test_setup
from tests.system.gui.test_components.base import ComponentBaseTest


@test_setup
class TestStack(ComponentBaseTest):
    def test_switches_pages(self):
        self.stack = Gtk.Stack()
        self.stack.add_named(Gtk.Label(), "Devices")
        self.stack.add_named(Gtk.Label(), "Presets")
        self.stack.add_named(Gtk.Label(), "Editor")
        self.stack.show_all()
        Stack(self.message_broker, self.controller_mock, self.stack)

        self.message_broker.publish(DoStackSwitch(Stack.devices_page))
        self.assertEqual(self.stack.get_visible_child_name(), "Devices")

        self.message_broker.publish(DoStackSwitch(Stack.presets_page))
        self.assertEqual(self.stack.get_visible_child_name(), "Presets")

        self.message_broker.publish(DoStackSwitch(Stack.editor_page))
        self.assertEqual(self.stack.get_visible_child_name(), "Editor")
