
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

from inputremapper.gui.components.editor import (
    RecordingStatus,
    RecordingToggle,
)
from inputremapper.gui.messages.message_broker import (
    MessageType,
)
from tests.lib.test_setup import test_setup
from tests.system.gui.test_components.base import ComponentBaseTest


@test_setup
class TestRecordingToggle(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()

        self.toggle_button = Gtk.ToggleButton()
        self.recording_toggle = RecordingToggle(
            self.message_broker,
            self.controller_mock,
            self.toggle_button,
        )

        self.label = Gtk.Label()
        self.recording_status = RecordingStatus(self.message_broker, self.label)

    def assert_not_recording(self):
        self.assertFalse(self.label.get_visible())
        self.assertFalse(self.toggle_button.get_active())

    def test_starts_recording(self):
        self.toggle_button.set_active(True)
        self.controller_mock.start_key_recording.assert_called_once()

    def test_stops_recording_when_clicked(self):
        self.toggle_button.set_active(True)
        self.toggle_button.set_active(False)
        self.controller_mock.stop_key_recording.assert_called_once()

    def test_not_recording_initially(self):
        self.assert_not_recording()

    def test_shows_recording_when_message_sent(self):
        self.assertFalse(self.label.get_visible())
        self.message_broker.signal(MessageType.recording_started)
        self.assertTrue(self.label.get_visible())

    def test_shows_not_recording_after_toggle(self):
        self.toggle_button.set_active(True)
        self.toggle_button.set_active(False)
        self.assert_not_recording()

    def test_shows_not_recording_when_recording_finished(self):
        self.toggle_button.set_active(True)
        self.message_broker.signal(MessageType.recording_finished)
        self.assert_not_recording()
