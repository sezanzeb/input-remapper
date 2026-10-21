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

from inputremapper.configs.mapping import Mapping
from inputremapper.gui.components.editor import (
    KeyAxisStackSwitcher,
)
from inputremapper.gui.messages.message_data import (
    MappingData,
)
from tests.lib.test_setup import test_setup
from tests.system.gui.test_components.base import ComponentBaseTest


@test_setup
class TestKeyAxisStackSwitcher(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = Gtk.Box()
        self.gtk_stack = Gtk.Stack()
        self.analog_toggle = Gtk.ToggleButton()
        self.key_toggle = Gtk.ToggleButton()

        self.gui.add(self.gtk_stack)
        self.gui.add(self.analog_toggle)
        self.gui.add(self.key_toggle)
        self.gtk_stack.add_named(Gtk.Box(), "Analog Axis")
        self.gtk_stack.add_named(Gtk.Box(), "Key or Macro")

        self.stack = KeyAxisStackSwitcher(
            self.message_broker,
            self.controller_mock,
            self.gtk_stack,
            self.key_toggle,
            self.analog_toggle,
        )

        self.gui.show_all()
        self.gtk_stack.set_visible_child_name("Key or Macro")

    def assert_key_macro_active(self):
        self.assertEqual(self.gtk_stack.get_visible_child_name(), "Key or Macro")
        self.assertTrue(self.key_toggle.get_active())
        self.assertFalse(self.analog_toggle.get_active())

    def assert_analog_active(self):
        self.assertEqual(self.gtk_stack.get_visible_child_name(), "Analog Axis")
        self.assertFalse(self.key_toggle.get_active())
        self.assertTrue(self.analog_toggle.get_active())

    def test_switches_to_axis(self):
        self.message_broker.publish(MappingData(Mapping(mapping_type="analog")))
        self.assert_analog_active()

    def test_switches_to_key_macro(self):
        self.message_broker.publish(MappingData(Mapping(mapping_type="analog")))
        self.message_broker.publish(MappingData(Mapping(mapping_type="key_macro")))
        self.assert_key_macro_active()

    def test_updates_mapping_type(self):
        self.key_toggle.set_active(True)
        self.controller_mock.update_mapping.assert_called_once_with(
            mapping_type="key_macro"
        )
        self.controller_mock.update_mapping.reset_mock()

        self.analog_toggle.set_active(True)
        self.controller_mock.update_mapping.assert_called_once_with(
            mapping_type="analog"
        )

    def test_avoids_infinite_recursion(self):
        self.message_broker.publish(MappingData(Mapping(mapping_type="analog")))
        self.message_broker.publish(MappingData(Mapping(mapping_type="key_macro")))
        self.controller_mock.update_mapping.assert_not_called()
