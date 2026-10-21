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

from inputremapper.configs.input_config import InputConfig
from inputremapper.gui.components.editor import (
    AnalogInputSwitch,
)
from tests.lib.test_setup import test_setup
from tests.system.gui.test_components.base import ComponentBaseTest


@test_setup
class TestAnalogInputSwitch(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = Gtk.Switch()
        self.switch = AnalogInputSwitch(
            self.message_broker, self.controller_mock, self.gui
        )

    def test_updates_event_as_analog(self):
        self.gui.set_active(True)
        self.controller_mock.set_event_as_analog.assert_called_once_with(True)
        self.controller_mock.reset_mock()
        self.gui.set_active(False)
        self.controller_mock.set_event_as_analog.assert_called_once_with(False)

    def test_updates_state(self):
        self.message_broker.publish(InputConfig(type=3, code=0))
        self.assertTrue(self.gui.get_active())
        self.message_broker.publish(InputConfig(type=3, code=0, analog_threshold=10))
        self.assertFalse(self.gui.get_active())

    def test_avoids_infinite_recursion(self):
        self.message_broker.publish(InputConfig(type=3, code=0))
        self.message_broker.publish(InputConfig(type=3, code=0, analog_threshold=-10))
        self.controller_mock.set_event_as_analog.assert_not_called()

    def test_disables_switch_when_key_event(self):
        self.message_broker.publish(InputConfig(type=1, code=1))
        self.assertLess(self.gui.get_opacity(), 0.6)
        self.assertFalse(self.gui.get_sensitive())

    def test_enables_switch_when_axis_event(self):
        self.message_broker.publish(InputConfig(type=1, code=1))
        self.message_broker.publish(InputConfig(type=3, code=0, analog_threshold=10))
        self.assertEqual(self.gui.get_opacity(), 1)
        self.assertTrue(self.gui.get_sensitive())

        self.message_broker.publish(InputConfig(type=1, code=1))
        self.message_broker.publish(InputConfig(type=2, code=0, analog_threshold=10))
        self.assertEqual(self.gui.get_opacity(), 1)
        self.assertTrue(self.gui.get_sensitive())
