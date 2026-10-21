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
class TestMappingSelectionLabel(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = Gtk.ListBox()
        self.mapping_selection_label = MappingSelectionLabel(
            self.message_broker,
            self.controller_mock,
            "",
            InputCombination(
                [
                    InputConfig(type=1, code=KEY_A),
                    InputConfig(type=1, code=KEY_B),
                ]
            ),
        )
        self.gui.insert(self.mapping_selection_label, -1)

    def assert_edit_mode(self):
        self.assertTrue(self.mapping_selection_label.name_input.get_visible())
        self.assertFalse(self.mapping_selection_label.label.get_visible())

    def assert_selected(self):
        self.assertTrue(self.mapping_selection_label.label.get_visible())
        self.assertFalse(self.mapping_selection_label.name_input.get_visible())

    def test_repr(self):
        self.mapping_selection_label.name = "name"
        self.assertIn("name", repr(self.mapping_selection_label))
        self.assertIn("KEY_A", repr(self.mapping_selection_label))
        self.assertIn("KEY_B", repr(self.mapping_selection_label))

    def test_shows_combination_without_name(self):
        self.assertEqual(self.mapping_selection_label.label.get_label(), "a + b")

    def test_shows_name_when_given(self):
        self.gui = MappingSelectionLabel(
            self.message_broker,
            self.controller_mock,
            "foo",
            InputCombination(
                (
                    InputConfig(type=1, code=KEY_A),
                    InputConfig(type=1, code=KEY_B),
                )
            ),
        )
        self.assertEqual(self.gui.label.get_label(), "foo")

    def test_updates_combination_when_selected(self):
        self.gui.select_row(self.mapping_selection_label)
        self.assertEqual(
            self.mapping_selection_label.combination,
            InputCombination(
                (
                    InputConfig(type=1, code=KEY_A),
                    InputConfig(type=1, code=KEY_B),
                )
            ),
        )
        self.message_broker.publish(
            CombinationUpdate(
                InputCombination(
                    (
                        InputConfig(type=1, code=KEY_A),
                        InputConfig(type=1, code=KEY_B),
                    )
                ),
                InputCombination([InputConfig(type=1, code=KEY_A)]),
            )
        )
        self.assertEqual(
            self.mapping_selection_label.combination,
            InputCombination([InputConfig(type=1, code=KEY_A)]),
        )

    def test_doesnt_update_combination_when_not_selected(self):
        self.assertEqual(
            self.mapping_selection_label.combination,
            InputCombination(
                (
                    InputConfig(type=1, code=KEY_A),
                    InputConfig(type=1, code=KEY_B),
                )
            ),
        )
        self.message_broker.publish(
            CombinationUpdate(
                InputCombination(
                    (
                        InputConfig(type=1, code=KEY_A),
                        InputConfig(type=1, code=KEY_B),
                    )
                ),
                InputCombination([InputConfig(type=1, code=KEY_A)]),
            )
        )
        self.assertEqual(
            self.mapping_selection_label.combination,
            InputCombination(
                (
                    InputConfig(type=1, code=KEY_A),
                    InputConfig(type=1, code=KEY_B),
                )
            ),
        )

    def test_updates_name_when_mapping_changed_and_combination_matches(self):
        self.message_broker.publish(
            MappingData(
                mapping=Mapping(
                    input_combination=InputCombination(
                        (
                            InputConfig(type=1, code=KEY_A),
                            InputConfig(type=1, code=KEY_B),
                        )
                    ),
                    name="foo",
                )
            )
        )
        self.assertEqual(self.mapping_selection_label.label.get_label(), "foo")

    def test_ignores_mapping_when_combination_does_not_match(self):
        self.message_broker.publish(
            MappingData(
                mapping=Mapping(
                    input_combination=InputCombination(
                        (
                            InputConfig(type=1, code=KEY_A),
                            InputConfig(type=1, code=KEY_C),
                        )
                    ),
                    name="foo",
                )
            )
        )
        self.assertEqual(self.mapping_selection_label.label.get_label(), "a + b")

    def test_edit_button_visibility(self):
        # start off invisible
        self.assertFalse(self.mapping_selection_label.edit_btn.get_visible())

        # load the mapping associated with the ListBoxRow
        self.message_broker.publish(
            MappingData(
                mapping=Mapping(
                    input_combination=InputCombination(
                        (
                            InputConfig(type=1, code=KEY_A),
                            InputConfig(type=1, code=KEY_B),
                        )
                    ),
                )
            )
        )
        self.assertTrue(self.mapping_selection_label.edit_btn.get_visible())

        # load a different row
        self.message_broker.publish(
            MappingData(
                mapping=Mapping(
                    input_combination=InputCombination(
                        (
                            InputConfig(type=1, code=KEY_A),
                            InputConfig(type=1, code=KEY_C),
                        )
                    ),
                )
            )
        )
        self.assertFalse(self.mapping_selection_label.edit_btn.get_visible())

    def test_enter_edit_mode_focuses_name_input(self):
        self.message_broker.publish(
            MappingData(
                mapping=Mapping(
                    input_combination=InputCombination(
                        (
                            InputConfig(type=1, code=KEY_A),
                            InputConfig(type=1, code=KEY_B),
                        )
                    ),
                )
            )
        )
        self.mapping_selection_label.edit_btn.clicked()
        self.controller_mock.set_focus.assert_called_once_with(
            self.mapping_selection_label.name_input
        )

    def test_enter_edit_mode_updates_visibility(self):
        self.message_broker.publish(
            MappingData(
                mapping=Mapping(
                    input_combination=InputCombination(
                        (
                            InputConfig(type=1, code=KEY_A),
                            InputConfig(type=1, code=KEY_B),
                        )
                    ),
                )
            )
        )
        self.assert_selected()
        self.mapping_selection_label.edit_btn.clicked()
        self.assert_edit_mode()
        self.mapping_selection_label.name_input.activate()  # aka hit the return key
        self.assert_selected()

    def test_leaves_edit_mode_on_esc(self):
        self.message_broker.publish(
            MappingData(
                mapping=Mapping(
                    input_combination=InputCombination(
                        (
                            InputConfig(type=1, code=KEY_A),
                            InputConfig(type=1, code=KEY_B),
                        )
                    ),
                )
            )
        )
        self.mapping_selection_label.edit_btn.clicked()
        self.assert_edit_mode()
        self.mapping_selection_label.name_input.set_text("foo")

        event = Gdk.Event()
        event.key.keyval = Gdk.KEY_Escape
        # send the "key-press-event"
        self.mapping_selection_label._on_gtk_rename_abort(None, event.key)
        self.assert_selected()
        self.assertEqual(self.mapping_selection_label.label.get_text(), "a + b")
        self.controller_mock.update_mapping.assert_not_called()

    def test_update_name(self):
        self.message_broker.publish(
            MappingData(
                mapping=Mapping(
                    input_combination=InputCombination(
                        (
                            InputConfig(type=1, code=KEY_A),
                            InputConfig(type=1, code=KEY_B),
                        )
                    ),
                )
            )
        )
        self.mapping_selection_label.edit_btn.clicked()

        self.mapping_selection_label.name_input.set_text("foo")
        self.mapping_selection_label.name_input.activate()
        self.controller_mock.update_mapping.assert_called_once_with(name="foo")

    def test_name_input_contains_combination_when_name_not_set(self):
        self.message_broker.publish(
            MappingData(
                mapping=Mapping(
                    input_combination=InputCombination(
                        (
                            InputConfig(type=1, code=KEY_A),
                            InputConfig(type=1, code=KEY_B),
                        )
                    ),
                )
            )
        )
        self.mapping_selection_label.edit_btn.clicked()
        self.assertEqual(self.mapping_selection_label.name_input.get_text(), "a + b")

    def test_name_input_contains_name(self):
        self.message_broker.publish(
            MappingData(
                mapping=Mapping(
                    input_combination=InputCombination(
                        (
                            InputConfig(type=1, code=KEY_A),
                            InputConfig(type=1, code=KEY_B),
                        )
                    ),
                    name="foo",
                )
            )
        )
        self.mapping_selection_label.edit_btn.clicked()
        self.assertEqual(self.mapping_selection_label.name_input.get_text(), "foo")

    def test_removes_name_when_name_matches_combination(self):
        self.message_broker.publish(
            MappingData(
                mapping=Mapping(
                    input_combination=InputCombination(
                        (
                            InputConfig(type=1, code=KEY_A),
                            InputConfig(type=1, code=KEY_B),
                        )
                    ),
                    name="foo",
                )
            )
        )
        self.mapping_selection_label.edit_btn.clicked()
        self.mapping_selection_label.name_input.set_text("a + b")
        self.mapping_selection_label.name_input.activate()
        self.controller_mock.update_mapping.assert_called_once_with(name="")
