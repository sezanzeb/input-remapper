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
from inputremapper.gui.components.editor import (
    CombinationListbox,
    InputConfigEntry,
)
from inputremapper.gui.messages.message_data import (
    MappingData,
)
from tests.lib.test_setup import test_setup
from tests.system.gui.test_components.base import ComponentBaseTest


@test_setup
class TestCombinationListbox(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = Gtk.ListBox()
        self.listbox = CombinationListbox(
            self.message_broker, self.controller_mock, self.gui
        )
        self.controller_mock.is_empty_mapping.return_value = False
        combination = InputCombination(
            (
                InputConfig(type=1, code=1),
                InputConfig(type=3, code=0, analog_threshold=1),
                InputConfig(type=1, code=2),
            )
        )
        self.message_broker.publish(
            MappingData(
                Mapping(
                    input_combination=combination.to_config(), target_uinput="keyboard"
                )
            )
        )

    def get_selected_row(self) -> InputConfigEntry:
        for entry in self.gui.get_children():
            if entry.is_selected():
                return entry

        raise AssertionError("Expected one InputConfigEntry to be selected")

    def select_row(self, input_cfg: InputConfig):
        for entry in self.gui.get_children():
            if entry.input_event == input_cfg:
                self.gui.select_row(entry)

    def test_loads_selected_row(self):
        self.select_row(InputConfig(type=1, code=2))
        self.controller_mock.load_input_config.assert_called_once_with(
            InputConfig(type=1, code=2)
        )

    def test_does_not_create_rows_when_mapping_is_empty(self):
        self.controller_mock.is_empty_mapping.return_value = True
        combination = InputCombination(
            (
                InputConfig(type=1, code=1),
                InputConfig(type=3, code=0, analog_threshold=1),
            )
        )
        self.message_broker.publish(MappingData(Mapping(input_combination=combination)))
        self.assertEqual(len(self.gui.get_children()), 0)

    def test_selects_row_when_selected_event_message_arrives(self):
        self.message_broker.publish(InputConfig(type=3, code=0, analog_threshold=1))
        self.assertEqual(
            self.get_selected_row().input_event,
            InputConfig(type=3, code=0, analog_threshold=1),
        )

    def test_avoids_infinite_recursion(self):
        self.message_broker.publish(InputConfig(type=3, code=0, analog_threshold=1))
        self.controller_mock.load_event.assert_not_called()
