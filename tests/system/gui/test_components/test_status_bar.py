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
class TestStatusBar(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = Gtk.Statusbar()
        self.err_icon = Gtk.Image()
        self.warn_icon = Gtk.Image()
        self.statusbar = StatusBar(
            self.message_broker,
            self.controller_mock,
            self.gui,
            self.err_icon,
            self.warn_icon,
        )
        self.message_broker.signal(MessageType.init)

    def assert_empty(self):
        self.assertFalse(self.err_icon.get_visible())
        self.assertFalse(self.warn_icon.get_visible())
        self.assertEqual(self.get_text(), "")
        self.assertIsNone(self.get_tooltip())

    def assert_error_status(self):
        self.assertTrue(self.err_icon.get_visible())
        self.assertFalse(self.warn_icon.get_visible())

    def assert_warning_status(self):
        self.assertFalse(self.err_icon.get_visible())
        self.assertTrue(self.warn_icon.get_visible())

    def get_text(self) -> str:
        return self.gui.get_message_area().get_children()[0].get_text()

    def get_tooltip(self) -> str | None:
        return self.gui.get_tooltip_text()

    def test_starts_empty(self):
        self.assert_empty()

    def test_shows_error_status(self):
        self.message_broker.publish(StatusData(CTX_ERROR, "msg", "tooltip"))
        self.assertEqual(self.get_text(), "msg")
        self.assertEqual(self.get_tooltip(), "tooltip")
        self.assert_error_status()

    def test_shows_warning_status(self):
        self.message_broker.publish(StatusData(CTX_WARNING, "msg", "tooltip"))
        self.assertEqual(self.get_text(), "msg")
        self.assertEqual(self.get_tooltip(), "tooltip")
        self.assert_warning_status()

    def test_shows_newest_message(self):
        self.message_broker.publish(StatusData(CTX_ERROR, "msg", "tooltip"))
        self.message_broker.publish(StatusData(CTX_WARNING, "msg2", "tooltip2"))
        self.assertEqual(self.get_text(), "msg2")
        self.assertEqual(self.get_tooltip(), "tooltip2")
        self.assert_warning_status()

    def test_data_without_message_removes_messages(self):
        self.message_broker.publish(StatusData(CTX_WARNING, "msg", "tooltip"))
        self.message_broker.publish(StatusData(CTX_WARNING, "msg2", "tooltip2"))
        self.message_broker.publish(StatusData(CTX_WARNING))
        self.assert_empty()

    def test_restores_message_from_not_removed_ctx_id(self):
        self.message_broker.publish(StatusData(CTX_ERROR, "msg", "tooltip"))
        self.message_broker.publish(StatusData(CTX_WARNING, "msg2", "tooltip2"))
        self.message_broker.publish(StatusData(CTX_WARNING))
        self.assertEqual(self.get_text(), "msg")
        self.assert_error_status()

        # works also the other way round
        self.message_broker.publish(StatusData(CTX_ERROR))
        self.message_broker.publish(StatusData(CTX_WARNING, "msg", "tooltip"))
        self.message_broker.publish(StatusData(CTX_ERROR, "msg2", "tooltip2"))
        self.message_broker.publish(StatusData(CTX_ERROR))
        self.assertEqual(self.get_text(), "msg")
        self.assert_warning_status()

    def test_sets_msg_as_tooltip_if_tooltip_is_none(self):
        self.message_broker.publish(StatusData(CTX_ERROR, "msg"))
        self.assertEqual(self.get_tooltip(), "msg")
