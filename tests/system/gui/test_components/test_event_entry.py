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

from inputremapper.configs.input_config import InputConfig
from inputremapper.gui.components.editor import (
    InputConfigEntry,
)
from tests.lib.test_setup import test_setup
from tests.system.gui.test_components.base import ComponentBaseTest


@test_setup
class TestEventEntry(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = InputConfigEntry(
            InputConfig(type=3, code=0, analog_threshold=1), self.controller_mock
        )

    def test_move_event(self):
        self.gui._up_btn.clicked()
        self.controller_mock.move_input_config_in_combination.assert_called_once_with(
            InputConfig(type=3, code=0, analog_threshold=1), "up"
        )
        self.controller_mock.reset_mock()

        self.gui._down_btn.clicked()
        self.controller_mock.move_input_config_in_combination.assert_called_once_with(
            InputConfig(type=3, code=0, analog_threshold=1), "down"
        )
