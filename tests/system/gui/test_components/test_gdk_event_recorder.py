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
class TestGdkEventRecorder(ComponentBaseTest):
    def _emit_key(self, window, code, type_):
        event = Gdk.Event()
        event.type = type_
        event.hardware_keycode = code + XKB_KEYCODE_OFFSET
        window.emit("event", event)
        gtk_iteration()

    def _emit_button(self, window, button, type_):
        event = Gdk.Event()
        event.type = type_
        event.button = button
        window.emit("event", event)
        gtk_iteration()

    def test_records_combinations(self):
        label = Gtk.Label()
        window = Gtk.Window()
        GdkEventRecorder(window, label)

        self._emit_key(window, KEY_A, Gdk.EventType.KEY_PRESS)
        self._emit_key(window, KEY_B, Gdk.EventType.KEY_PRESS)
        self.assertEqual(label.get_text(), "a + b")

        self._emit_key(window, KEY_A, Gdk.EventType.KEY_RELEASE)
        self._emit_key(window, KEY_B, Gdk.EventType.KEY_RELEASE)
        self.assertEqual(label.get_text(), "a + b")

        self._emit_key(window, KEY_C, Gdk.EventType.KEY_PRESS)
        self.assertEqual(label.get_text(), "c")

        # buttons
        self._emit_button(window, Gdk.BUTTON_PRIMARY, Gdk.EventType.BUTTON_PRESS)
        self._emit_button(window, Gdk.BUTTON_SECONDARY, Gdk.EventType.BUTTON_PRESS)
        self._emit_button(window, Gdk.BUTTON_MIDDLE, Gdk.EventType.BUTTON_PRESS)
        # no constants seem to exist, but this is the value that was observed during
        # usage:
        self._emit_button(window, 8, Gdk.EventType.BUTTON_PRESS)
        self._emit_button(window, 9, Gdk.EventType.BUTTON_PRESS)
        self.assertEqual(
            label.get_text(),
            "c + BTN_LEFT + BTN_RIGHT + BTN_MIDDLE + BTN_SIDE + BTN_EXTRA",
        )

        # releasing anything resets the combination
        self._emit_button(window, 9, Gdk.EventType.BUTTON_RELEASE)
        self._emit_key(window, KEY_A, Gdk.EventType.KEY_PRESS)
        self.assertEqual(label.get_text(), "a")
