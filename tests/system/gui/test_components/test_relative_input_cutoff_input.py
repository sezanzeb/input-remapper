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
class TestRelativeInputCutoffInput(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = Gtk.SpinButton()
        self.input = RelativeInputCutoffInput(
            self.message_broker, self.controller_mock, self.gui
        )
        self.message_broker.publish(
            MappingData(
                Mapping(
                    target_uinput="mouse",
                    input_combination=InputCombination([InputConfig(type=2, code=0)]),
                    rel_to_abs_input_cutoff=1,
                    output_type=3,
                    output_code=0,
                )
            )
        )

    def assert_active(self):
        self.assertTrue(self.gui.get_sensitive())
        self.assertEqual(self.gui.get_opacity(), 1)

    def assert_inactive(self):
        self.assertFalse(self.gui.get_sensitive())
        self.assertLess(self.gui.get_opacity(), 0.6)

    def test_avoids_infinite_recursion(self):
        self.message_broker.publish(
            MappingData(
                Mapping(
                    target_uinput="mouse",
                    input_combination=InputCombination([InputConfig(type=2, code=0)]),
                    rel_to_abs_input_cutoff=3,
                    output_type=3,
                    output_code=0,
                )
            )
        )
        self.controller_mock.update_mapping.assert_not_called()

    def test_updates_value(self):
        rel_to_abs_input_cutoff = 3
        self.message_broker.publish(
            MappingData(
                Mapping(
                    target_uinput="mouse",
                    input_combination=InputCombination([InputConfig(type=2, code=0)]),
                    rel_to_abs_input_cutoff=rel_to_abs_input_cutoff,
                    output_type=3,
                    output_code=0,
                )
            )
        )
        self.assertEqual(self.gui.get_value(), rel_to_abs_input_cutoff)

    def test_updates_mapping(self):
        self.gui.set_value(300)
        self.controller_mock.update_mapping.assert_called_once_with(rel_xy_cutoff=300)

    def test_disables_input_when_no_rel_axis_input(self):
        self.assert_active()
        self.message_broker.publish(
            MappingData(
                Mapping(
                    target_uinput="mouse",
                    input_combination=InputCombination([InputConfig(type=3, code=0)]),
                    output_type=3,
                    output_code=0,
                )
            )
        )
        self.assert_inactive()

    def test_disables_input_when_no_abs_axis_output(self):
        self.assert_active()
        self.message_broker.publish(
            MappingData(
                Mapping(
                    target_uinput="mouse",
                    input_combination=InputCombination([InputConfig(type=2, code=0)]),
                    rel_to_abs_input_cutoff=3,
                    output_type=2,
                    output_code=0,
                )
            )
        )
        self.assert_inactive()

    def test_enables_input(self):
        self.message_broker.publish(
            MappingData(
                Mapping(
                    target_uinput="mouse",
                    input_combination=InputCombination([InputConfig(type=3, code=0)]),
                    output_type=3,
                    output_code=0,
                )
            )
        )
        self.assert_inactive()
        self.message_broker.publish(
            MappingData(
                Mapping(
                    target_uinput="mouse",
                    input_combination=InputCombination([InputConfig(type=2, code=0)]),
                    rel_to_abs_input_cutoff=1,
                    output_type=3,
                    output_code=0,
                )
            )
        )
        self.assert_active()
