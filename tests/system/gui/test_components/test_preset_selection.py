
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

from inputremapper.configs.input_config import InputCombination, InputConfig
from inputremapper.configs.mapping import Mapping
from inputremapper.gui.components.presets import PresetSelection
from inputremapper.gui.messages.message_data import (
    GroupData,
    PresetData,
)
from tests.lib.test_setup import test_setup
from tests.system.gui.test_components.base import ComponentBaseTest
from tests.system.gui.test_components.flowbox_test_utils import FlowBoxTestUtils


@test_setup
class TestPresetSelection(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = Gtk.FlowBox()
        self.selection = PresetSelection(
            self.message_broker, self.controller_mock, self.gui
        )
        self.message_broker.publish(GroupData("foo", ("preset1", "preset2")))

    def test_populates_presets(self):
        names = FlowBoxTestUtils.get_child_names(self.gui)
        self.assertEqual(names, ["preset1", "preset2"])

        self.message_broker.publish(GroupData("foo", ("preset3", "preset4")))
        names = FlowBoxTestUtils.get_child_names(self.gui)
        self.assertEqual(names, ["preset3", "preset4"])

    def test_selects_preset(self):
        self.message_broker.publish(
            PresetData(
                "preset2",
                (
                    Mapping(
                        name="m1",
                        input_combination=InputCombination(
                            [InputConfig(type=1, code=2)]
                        ),
                    ),
                ),
            )
        )
        self.assertEqual(FlowBoxTestUtils.get_active_entry(self.gui).name, "preset2")

        self.message_broker.publish(
            PresetData(
                "preset1",
                (
                    Mapping(
                        name="m1",
                        input_combination=InputCombination(
                            [InputConfig(type=1, code=2)]
                        ),
                    ),
                ),
            )
        )
        self.assertEqual(FlowBoxTestUtils.get_active_entry(self.gui).name, "preset1")

    def test_avoids_infinite_recursion(self):
        self.message_broker.publish(
            PresetData(
                "preset2",
                (
                    Mapping(
                        name="m1",
                        input_combination=InputCombination(
                            [InputConfig(type=1, code=2)]
                        ),
                    ),
                ),
            )
        )
        self.controller_mock.load_preset.assert_not_called()

    def test_loads_preset(self):
        FlowBoxTestUtils.set_active(self.gui, "preset2")
        self.controller_mock.load_preset.assert_called_once_with("preset2")
