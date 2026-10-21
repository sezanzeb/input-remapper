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
