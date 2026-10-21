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


import evdev
import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GLib", "2.0")
gi.require_version("GtkSource", "4")
from gi.repository import Gtk

from inputremapper.configs.input_config import InputCombination, InputConfig
from inputremapper.configs.mapping import Mapping
from inputremapper.gui.components.editor import (
    OutputAxisSelector,
)
from inputremapper.gui.messages.message_data import (
    MappingData,
    UInputsData,
)
from tests.lib.test_setup import test_setup
from tests.system.gui.test_components.base import ComponentBaseTest


@test_setup
class TestOutputAxisSelector(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = Gtk.ComboBox()
        self.selection = OutputAxisSelector(
            self.message_broker, self.controller_mock, self.gui
        )
        absinfo = evdev.AbsInfo(0, -10, 10, 0, 0, 0)
        self.message_broker.publish(
            UInputsData(
                {
                    "mouse": {1: [1, 2, 3, 4], 2: [0, 1, 2, 3]},
                    "keyboard": {1: [1, 2, 3, 4]},
                    "gamepad": {
                        2: [0, 1, 2, 3],
                        3: [(0, absinfo), (1, absinfo), (2, absinfo), (3, absinfo)],
                    },
                }
            )
        )
        self.message_broker.publish(
            MappingData(
                Mapping(
                    target_uinput="mouse",
                    input_combination=InputCombination([InputConfig(type=1, code=1)]),
                )
            )
        )

    def set_active_selection(self, selection: tuple):
        self.gui.set_active_id(f"{selection[0]}, {selection[1]}")

    def get_active_selection(self) -> tuple[int, int]:
        return tuple(int(i) for i in self.gui.get_active_id().split(","))  # type: ignore

    def test_updates_mapping(self):
        self.set_active_selection((2, 0))
        self.controller_mock.update_mapping.assert_called_once_with(
            output_type=2, output_code=0
        )

    def test_updates_mapping_with_none(self):
        self.set_active_selection((2, 0))
        self.controller_mock.reset_mock()
        self.set_active_selection((None, None))
        self.controller_mock.update_mapping.assert_called_once_with(
            output_type=None, output_code=None
        )

    def test_selects_correct_entry(self):
        self.assertEqual(self.gui.get_active_id(), "None, None")
        self.message_broker.publish(
            MappingData(Mapping(target_uinput="mouse", output_type=2, output_code=3))
        )
        self.assertEqual(self.get_active_selection(), (2, 3))

    def test_avoids_infinite_recursion(self):
        self.message_broker.publish(
            MappingData(Mapping(target_uinput="mouse", output_type=2, output_code=3))
        )
        self.controller_mock.update_mapping.assert_not_called()

    def test_updates_dropdown_model(self):
        self.assertEqual(len(self.gui.get_model()), 5)
        self.message_broker.publish(MappingData(Mapping(target_uinput="keyboard")))
        self.assertEqual(len(self.gui.get_model()), 1)
        self.message_broker.publish(MappingData(Mapping(target_uinput="gamepad")))
        self.assertEqual(len(self.gui.get_model()), 9)
