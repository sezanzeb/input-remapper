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
    TargetSelection,
)
from inputremapper.gui.messages.message_data import (
    MappingData,
    UInputsData,
)
from tests.lib.test_setup import test_setup
from tests.system.gui.test_components.base import ComponentBaseTest


@test_setup
class TestTargetSelection(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = Gtk.ComboBox()
        self.selection = TargetSelection(
            self.message_broker, self.controller_mock, self.gui
        )
        self.message_broker.publish(
            UInputsData(
                {
                    "foo": {},
                    "bar": {},
                    "baz": {},
                }
            )
        )

    def test_populates_devices(self):
        names = [row[0] for row in self.gui.get_model()]
        self.assertEqual(names, ["foo", "bar", "baz"])

        self.message_broker.publish(
            UInputsData(
                {
                    "kuu": {},
                    "qux": {},
                }
            )
        )
        names = [row[0] for row in self.gui.get_model()]
        self.assertEqual(names, ["kuu", "qux"])

    def test_updates_mapping(self):
        self.gui.set_active_id("baz")
        self.controller_mock.update_mapping.assert_called_once_with(target_uinput="baz")

    def test_selects_correct_target(self):
        self.message_broker.publish(MappingData(Mapping(target_uinput="baz")))
        self.assertEqual(self.gui.get_active_id(), "baz")
        self.message_broker.publish(MappingData(Mapping(target_uinput="bar")))
        self.assertEqual(self.gui.get_active_id(), "bar")

    def test_avoids_infinite_recursion(self):
        self.message_broker.publish(MappingData(Mapping(target_uinput="baz")))
        self.controller_mock.update_mapping.assert_not_called()
