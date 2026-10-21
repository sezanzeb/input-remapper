
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
    ReleaseTimeoutInput,
)
from inputremapper.gui.messages.message_data import (
    MappingData,
)
from tests.lib.test_setup import test_setup
from tests.system.gui.test_components.base import ComponentBaseTest


@test_setup
class TestReleaseTimeoutInput(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = Gtk.SpinButton()
        self.input = ReleaseTimeoutInput(
            self.message_broker, self.controller_mock, self.gui
        )
        self.message_broker.publish(
            MappingData(
                Mapping(
                    input_combination=InputCombination(
                        [InputConfig(type=2, code=0, analog_threshold=1)]
                    ),
                    target_uinput="keyboard",
                )
            )
        )

    def test_updates_timeout_on_mapping_message(self):
        self.message_broker.publish(
            MappingData(
                Mapping(
                    input_combination=InputCombination(
                        [InputConfig(type=2, code=0, analog_threshold=1)]
                    ),
                    release_timeout=1,
                )
            )
        )
        self.assertEqual(self.gui.get_value(), 1)

    def test_updates_mapping(self):
        self.gui.set_value(0.5)
        self.controller_mock.update_mapping.assert_called_once_with(release_timeout=0.5)

    def test_avoids_infinite_recursion(self):
        self.message_broker.publish(
            MappingData(
                Mapping(
                    input_combination=InputCombination(
                        [InputConfig(type=2, code=0, analog_threshold=1)]
                    ),
                    release_timeout=1,
                )
            )
        )
        self.controller_mock.update_mapping.assert_not_called()

    def test_disables_input_based_on_input_combination(self):
        self.message_broker.publish(
            MappingData(
                Mapping(
                    input_combination=InputCombination(
                        (
                            InputConfig(type=2, code=0, analog_threshold=1),
                            InputConfig(type=1, code=1),
                        )
                    )
                )
            )
        )
        self.assertTrue(self.gui.get_sensitive())
        self.assertEqual(self.gui.get_opacity(), 1)

        self.message_broker.publish(
            MappingData(
                Mapping(
                    input_combination=InputCombination(
                        (
                            InputConfig(type=1, code=1),
                            InputConfig(type=1, code=2),
                        )
                    )
                )
            )
        )
        self.assertFalse(self.gui.get_sensitive())
        self.assertLess(self.gui.get_opacity(), 0.6)

        self.message_broker.publish(
            MappingData(
                Mapping(
                    input_combination=InputCombination(
                        (
                            InputConfig(type=2, code=0, analog_threshold=1),
                            InputConfig(type=1, code=1),
                        )
                    )
                )
            )
        )
        self.message_broker.publish(
            MappingData(
                Mapping(
                    input_combination=InputCombination(
                        (
                            InputConfig(type=3, code=0, analog_threshold=1),
                            InputConfig(
                                type=1,
                                code=2,
                            ),
                        )
                    )
                )
            )
        )
        self.assertFalse(self.gui.get_sensitive())
        self.assertLess(self.gui.get_opacity(), 0.6)
