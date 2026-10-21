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


@test_setup
class TestSliders(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = Gtk.Box()
        self.gain = Gtk.Scale()
        self.deadzone = Gtk.Scale()
        self.expo = Gtk.Scale()

        # add everything to a box: it will be cleand up properly
        self.gui.add(self.gain)
        self.gui.add(self.deadzone)
        self.gui.add(self.expo)

        self.sliders = Sliders(
            self.message_broker,
            self.controller_mock,
            self.gain,
            self.deadzone,
            self.expo,
        )
        self.message_broker.publish(
            MappingData(
                Mapping(
                    input_combination=InputCombination([InputConfig(type=3, code=0)]),
                    target_uinput="mouse",
                )
            )
        )

    @staticmethod
    def get_range(range: Gtk.Range) -> tuple[int, int]:
        """the Gtk.Range, has no get_range method. this is a workaround"""
        v = range.get_value()
        range.set_value(-(2**16))
        min_ = range.get_value()
        range.set_value(2**16)
        max_ = range.get_value()
        range.set_value(v)
        return min_, max_

    def test_slider_ranges(self):
        self.assertEqual(self.get_range(self.gain), (-2, 2))
        self.assertEqual(self.get_range(self.deadzone), (0, 0.9))
        self.assertEqual(self.get_range(self.expo), (-1, 1))

    def test_updates_value(self):
        self.message_broker.publish(
            MappingData(
                Mapping(
                    gain=0.5,
                    deadzone=0.6,
                    expo=0.3,
                )
            )
        )
        self.assertEqual(self.gain.get_value(), 0.5)
        self.assertEqual(self.expo.get_value(), 0.3)
        self.assertEqual(self.deadzone.get_value(), 0.6)

    def test_gain_updates_mapping(self):
        self.gain.set_value(0.5)
        self.controller_mock.update_mapping.assert_called_once_with(gain=0.5)

    def test_expo_updates_mapping(self):
        self.expo.set_value(0.5)
        self.controller_mock.update_mapping.assert_called_once_with(expo=0.5)

    def test_deadzone_updates_mapping(self):
        self.deadzone.set_value(0.5)
        self.controller_mock.update_mapping.assert_called_once_with(deadzone=0.5)

    def test_avoids_recursion(self):
        self.message_broker.publish(MappingData(Mapping(gain=0.5)))
        self.controller_mock.update_mapping.assert_not_called()
        self.message_broker.publish(MappingData(Mapping(expo=0.5)))
        self.controller_mock.update_mapping.assert_not_called()
        self.message_broker.publish(MappingData(Mapping(deadzone=0.5)))
        self.controller_mock.update_mapping.assert_not_called()
