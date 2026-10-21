#!/usr/bin/env python3
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

import time
import unittest
from unittest.mock import MagicMock, call

import evdev
import gi
from evdev.ecodes import KEY_A, KEY_B, KEY_C

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GLib", "2.0")
gi.require_version("GtkSource", "4")
from gi.repository import Gdk, GLib, Gtk, GtkSource

from inputremapper.configs.input_config import InputCombination, InputConfig
from inputremapper.configs.keyboard_layout import XKB_KEYCODE_OFFSET
from inputremapper.configs.mapping import Mapping
from inputremapper.groups import DeviceType
from inputremapper.gui.components.common import Breadcrumbs, FlowBoxEntry
from inputremapper.gui.components.device_groups import (
    DeviceGroupEntry,
    DeviceGroupSelection,
)
from inputremapper.gui.components.editor import (
    AnalogInputSwitch,
    AutoloadSwitch,
    CodeEditor,
    CombinationListbox,
    GdkEventRecorder,
    InputConfigEntry,
    KeyAxisStackSwitcher,
    MappingListBox,
    MappingSelectionLabel,
    OutputAxisSelector,
    RecordingStatus,
    RecordingToggle,
    RelativeInputCutoffInput,
    ReleaseCombinationSwitch,
    ReleaseTimeoutInput,
    RequireActiveMapping,
    Sliders,
    TargetSelection,
    TransformationDrawArea,
    TriggerThresholdInput,
)
from inputremapper.gui.components.main import Stack, StatusBar
from inputremapper.gui.components.presets import PresetSelection
from inputremapper.gui.controller import Controller
from inputremapper.gui.messages.message_broker import (
    MessageBroker,
    MessageType,
)
from inputremapper.gui.messages.message_data import (
    CombinationUpdate,
    DoStackSwitch,
    GroupData,
    GroupsData,
    MappingData,
    PresetData,
    StatusData,
    UInputsData,
)
from inputremapper.gui.utils import CTX_ERROR, CTX_WARNING, gtk_iteration
from tests.lib.logger import logger
from tests.lib.spy import spy
from tests.lib.test_setup import test_setup


@test_setup
class TestCodeEditor(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = GtkSource.View()
        self.editor = CodeEditor(self.message_broker, self.controller_mock, self.gui)
        # TODO why is mocking this to False needed?
        self.controller_mock.is_empty_mapping.return_value = False

    def get_text(self) -> str:
        buffer = self.gui.get_buffer()
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)

    def test_shows_output_symbol(self):
        self.message_broker.publish(MappingData(Mapping(output_symbol="foo")))
        self.assertEqual(self.get_text(), "foo")

    def test_shows_record_input_first_message_when_mapping_is_empty(self):
        self.controller_mock.is_empty_mapping.return_value = True
        self.message_broker.publish(MappingData(Mapping(output_symbol="foo")))
        self.assertEqual(self.get_text(), "Record the input first")

    def test_active_when_mapping_is_not_empty(self):
        self.message_broker.publish(MappingData(Mapping(output_symbol="foo")))
        self.assertTrue(self.gui.get_sensitive())
        self.assertEqual(self.gui.get_opacity(), 1)

    def test_expands_to_multiline(self):
        self.message_broker.publish(MappingData(Mapping(output_symbol="foo\nbar")))
        self.assertIn("multiline", self.gui.get_style_context().list_classes())

    def test_shows_line_numbers_when_multiline(self):
        self.message_broker.publish(MappingData(Mapping(output_symbol="foo\nbar")))
        self.assertTrue(self.gui.get_show_line_numbers())

    def test_no_multiline_when_macro_not_multiline(self):
        self.message_broker.publish(MappingData(Mapping(output_symbol="foo")))
        self.assertNotIn("multiline", self.gui.get_style_context().list_classes())

    def test_no_line_numbers_macro_not_multiline(self):
        self.message_broker.publish(MappingData(Mapping(output_symbol="foo")))
        self.assertFalse(self.gui.get_show_line_numbers())

    def test_shows_placeholder_when_mapping_has_no_output_symbol(self):
        self.message_broker.publish(MappingData(Mapping()))
        self.assertEqual(self.get_text(), self.editor.placeholder)

        # there are no side-effects because the placeholder is inserted:
        self.controller_mock.update_mapping.assert_not_called()

    def test_updates_mapping(self):
        self.message_broker.publish(MappingData(Mapping()))
        buffer = self.gui.get_buffer()
        self.controller_mock.update_mapping.assert_not_called()
        buffer.set_text("foo")
        call_args_list = self.controller_mock.update_mapping.call_args_list
        # this test emits 2 events for whatever reason, the first one with an empty
        # symbol. this doesn't actually seem to happen when using it.
        self.assertEqual(call_args_list[-1], call(output_symbol="foo"))

    def test_avoids_infinite_recursion_when_loading_mapping(self):
        self.message_broker.publish(MappingData(Mapping(output_symbol="foo")))
        self.controller_mock.update_mapping.assert_not_called()

    def test_gets_focus_when_input_recording_finises(self):
        self.message_broker.signal(MessageType.recording_finished)
        self.controller_mock.set_focus.assert_called_once_with(self.gui)

    def test_placeholder(self):
        self.assertEqual(self.get_text(), self.editor.placeholder)

        window = Gtk.Window()
        window.add(self.gui)
        window.show_all()

        def focus():
            self.gui.grab_focus()
            # Do as many iterations as needed to make it work.
            gtk_iteration(15)

        def unfocus():
            window.set_focus(None)
            gtk_iteration(15)

        # clears the input when we enter the editor widget
        focus()
        self.assertEqual(self.get_text(), "")
        self.assertNotIn("opaque-text", self.gui.get_style_context().list_classes())

        # adds the placeholder back when we leave it
        unfocus()
        self.assertEqual(self.get_text(), self.editor.placeholder)
        self.assertIn("opaque-text", self.gui.get_style_context().list_classes())

        # if we enter text and then leave, it won't show the placeholder
        focus()
        self.assertEqual(self.get_text(), "")
        buffer = self.gui.get_buffer()
        buffer.set_text("foo")
        self.assertNotIn("opaque-text", self.gui.get_style_context().list_classes())
        unfocus()
        self.assertEqual(self.get_text(), "foo")
        self.assertNotIn("opaque-text", self.gui.get_style_context().list_classes())
