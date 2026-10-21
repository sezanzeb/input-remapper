
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

from inputremapper.groups import DeviceType
from inputremapper.gui.components.device_groups import (
    DeviceGroupSelection,
)
from inputremapper.gui.messages.message_data import (
    GroupData,
    GroupsData,
)
from tests.lib.test_setup import test_setup
from tests.system.gui.test_components.base import ComponentBaseTest
from tests.system.gui.test_components.flowbox_test_utils import FlowBoxTestUtils


@test_setup
class TestDeviceGroupSelection(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = Gtk.FlowBox()
        self.selection = DeviceGroupSelection(
            self.message_broker,
            self.controller_mock,
            self.gui,
        )
        self.message_broker.publish(
            GroupsData(
                {
                    "foo": [DeviceType.GAMEPAD, DeviceType.KEYBOARD],
                    "bar": [],
                    "baz": [DeviceType.GRAPHICS_TABLET],
                }
            )
        )

    def get_displayed_group_keys_and_icons(self):
        """Get a list of all group_keys and icons of the displayed groups."""
        group_keys = []
        icons = []
        for child in self.gui.get_children():
            device_group_entry = child.get_children()[0]
            group_keys.append(device_group_entry.group_key)
            icons.append(device_group_entry.icon_name)

        return group_keys, icons

    def test_populates_devices(self):
        # tests that all devices sent via the broker end up in the gui
        group_keys, icons = self.get_displayed_group_keys_and_icons()
        self.assertEqual(group_keys, ["foo", "bar", "baz"])
        self.assertEqual(icons, ["input-gaming", None, "input-tablet"])

        self.message_broker.publish(
            GroupsData(
                {
                    "kuu": [DeviceType.KEYBOARD],
                    "qux": [DeviceType.GAMEPAD],
                }
            )
        )

        group_keys, icons = self.get_displayed_group_keys_and_icons()
        self.assertEqual(group_keys, ["kuu", "qux"])
        self.assertEqual(icons, ["input-keyboard", "input-gaming"])

    def test_selects_correct_device(self):
        self.message_broker.publish(GroupData("bar", ()))
        self.assertEqual(FlowBoxTestUtils.get_active_entry(self.gui).group_key, "bar")
        self.message_broker.publish(GroupData("baz", ()))
        self.assertEqual(FlowBoxTestUtils.get_active_entry(self.gui).group_key, "baz")

    def test_loads_group(self):
        FlowBoxTestUtils.set_active(self.gui, "bar")
        self.controller_mock.load_group.assert_called_once_with("bar")

    def test_avoids_infinite_recursion(self):
        self.message_broker.publish(GroupData("bar", ()))
        self.controller_mock.load_group.assert_not_called()
