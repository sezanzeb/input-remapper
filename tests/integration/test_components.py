#!/usr/bin/python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2022 sezanzeb <proxima@sezanzeb.de>
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

import unittest
from typing import Optional, Tuple, Union
from unittest.mock import MagicMock
import time

import evdev
from evdev.ecodes import KEY_A, KEY_B, KEY_C

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GLib", "2.0")
gi.require_version("GtkSource", "4")
from gi.repository import Gtk, GLib, GtkSource, Gdk

from tests.lib.cleanup import quick_cleanup
from tests.lib.stuff import spy
from tests.lib.logger import logger

from inputremapper.gui.controller import Controller
from inputremapper.configs.system_mapping import XKB_KEYCODE_OFFSET
from inputremapper.gui.utils import CTX_ERROR, CTX_WARNING, gtk_iteration
from inputremapper.gui.messages.message_broker import (
    MessageBroker,
    MessageType,
)
from inputremapper.gui.messages.message_data import (
    UInputsData,
    GroupsData,
    GroupData,
    PresetData,
    StatusData,
    CombinationUpdate,
    DoStackSwitch,
)
from inputremapper.groups import DeviceType
from inputremapper.gui.components.editor import (
    TargetSelection,
    MappingListBox,
    MappingSelectionLabel,
    CodeEditor,
    RecordingToggle,
    AutoloadSwitch,
    ReleaseCombinationSwitch,
    CombinationListbox,
    InputConfigEntry,
    AnalogInputSwitch,
    TriggerThresholdInput,
    ReleaseTimeoutInput,
    OutputAxisSelector,
    KeyAxisStackSwitcher,
    Sliders,
    TransformationDrawArea,
    RelativeInputCutoffInput,
    RecordingStatus,
    RequireActiveMapping,
    GdkEventRecorder,
)
from inputremapper.gui.components.main import Stack, StatusBar
from inputremapper.gui.components.common import (
    FlowBoxEntry,
    Breadcrumbs,
    ListFilterControl,
)
from inputremapper.gui.components.presets import PresetSelection
from inputremapper.gui.components.device_groups import (
    DeviceGroupEntry,
    DeviceGroupSelection,
)
from inputremapper.configs.mapping import MappingData
from inputremapper.configs.input_config import InputCombination, InputConfig


class GtkKeyEvent:

    KEY_RELEASE = "key-release-event"
    KEY_PRESS = "key-press-event"

    def __init__(self, keyval):
        self.keyval = keyval

    def get_keyval(self):
        return True, self.keyval

    def emit_to(self, target:Gtk.Widget, event_type=KEY_RELEASE):
        ev = Gdk.Event()
        ev.key.keyval = self.keyval
        target.emit(event_type, ev)
        gtk_iteration()


class ComponentBaseTest(unittest.TestCase):
    """Test a gui component."""

    def setUp(self) -> None:
        self.message_broker = MessageBroker()
        self.controller_mock: Controller = MagicMock()

    def destroy_all_member_widgets(self):
        # destroy all Gtk Widgets that are stored in self
        # TODO why is this necessary?
        for attribute in dir(self):
            stuff = getattr(self, attribute, None)
            if isinstance(stuff, Gtk.Widget):
                logger.info('destroying member "%s" %s', attribute, stuff)
                GLib.timeout_add(0, stuff.destroy)
                setattr(self, attribute, None)

    def tearDown(self) -> None:
        super().tearDown()
        self.message_broker.signal(MessageType.terminate)

        # Shut down the gui properly
        self.destroy_all_member_widgets()
        GLib.timeout_add(0, Gtk.main_quit)

        # Gtk.main() will start the Gtk event loop and process all pending events.
        # So the gui will do whatever is queued up this ensures that the next tests
        # starts without pending events.
        Gtk.main()

        quick_cleanup()


class FlowBoxTestUtils:
    """Methods to test the FlowBoxes that contain presets and devices.

    Those are only used in tests, so I moved them here instead.
    """

    @staticmethod
    def set_active(flow_box: Gtk.FlowBox, name: str):
        """Change the currently selected group."""
        for child in flow_box.get_children():
            flow_box_entry: FlowBoxEntry = child.get_children()[0]
            flow_box_entry.set_active(flow_box_entry.name == name)

    @staticmethod
    def get_active_entry(flow_box: Gtk.FlowBox) -> Union[DeviceGroupEntry, None]:
        """Find the currently selected DeviceGroupEntry."""
        children = flow_box.get_children()

        if len(children) == 0:
            return None

        for child in children:
            flow_box_entry: FlowBoxEntry = child.get_children()[0]

            if flow_box_entry.get_active():
                return flow_box_entry

        raise AssertionError("Expected one entry to be selected.")

    @staticmethod
    def get_child_names(flow_box: Gtk.FlowBox):
        names = []
        for child in flow_box.get_children():
            flow_box_entry: FlowBoxEntry = child.get_children()[0]
            names.append(flow_box_entry.name)

        return names

    @staticmethod
    def get_child_icons(flow_box: Gtk.FlowBox):
        icon_names = []
        for child in flow_box.get_children():
            flow_box_entry: FlowBoxEntry = child.get_children()[0]
            icon_names.append(flow_box_entry.icon_name)

        return icon_names


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


class TestTargetSelection(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = Gtk.ComboBox()
        self.selection = TargetSelection(
            self.message_broker, self.controller_mock, self.gui
        )
        self.message_broker.publish(
            UInputsData(
                {
                    "foo": {},
                    "bar": {},
                    "baz": {},
                }
            )
        )

    def test_populates_devices(self):
        names = [row[0] for row in self.gui.get_model()]
        self.assertEqual(names, ["foo", "bar", "baz"])

        self.message_broker.publish(
            UInputsData(
                {
                    "kuu": {},
                    "qux": {},
                }
            )
        )
        names = [row[0] for row in self.gui.get_model()]
        self.assertEqual(names, ["kuu", "qux"])

    def test_updates_mapping(self):
        self.gui.set_active_id("baz")
        self.controller_mock.update_mapping.called_once_with(target_uinput="baz")

    def test_selects_correct_target(self):
        self.message_broker.publish(MappingData(target_uinput="baz"))
        self.assertEqual(self.gui.get_active_id(), "baz")
        self.message_broker.publish(MappingData(target_uinput="bar"))
        self.assertEqual(self.gui.get_active_id(), "bar")

    def test_avoids_infinite_recursion(self):
        self.message_broker.publish(MappingData(target_uinput="baz"))
        self.controller_mock.update_mapping.assert_not_called()


class TestPresetSelection(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = Gtk.FlowBox()
        self.selection = PresetSelection(
            self.message_broker, self.controller_mock, self.gui
        )
        self.message_broker.publish(GroupData("foo", ("preset1", "preset2")))

    def test_populates_presets(self):
        names = FlowBoxTestUtils.get_child_names(self.gui)
        self.assertEqual(names, ["preset1", "preset2"])

        self.message_broker.publish(GroupData("foo", ("preset3", "preset4")))
        names = FlowBoxTestUtils.get_child_names(self.gui)
        self.assertEqual(names, ["preset3", "preset4"])

    def test_selects_preset(self):
        self.message_broker.publish(
            PresetData(
                "preset2",
                (
                    MappingData(
                        name="m1",
                        input_combination=InputCombination(InputConfig(type=1, code=2)),
                    ),
                ),
            )
        )
        self.assertEqual(FlowBoxTestUtils.get_active_entry(self.gui).name, "preset2")

        self.message_broker.publish(
            PresetData(
                "preset1",
                (
                    MappingData(
                        name="m1",
                        input_combination=InputCombination(InputConfig(type=1, code=2)),
                    ),
                ),
            )
        )
        self.assertEqual(FlowBoxTestUtils.get_active_entry(self.gui).name, "preset1")

    def test_avoids_infinite_recursion(self):
        self.message_broker.publish(
            PresetData(
                "preset2",
                (
                    MappingData(
                        name="m1",
                        input_combination=InputCombination(InputConfig(type=1, code=2)),
                    ),
                ),
            )
        )
        self.controller_mock.load_preset.assert_not_called()

    def test_loads_preset(self):
        FlowBoxTestUtils.set_active(self.gui, "preset2")
        self.controller_mock.load_preset.assert_called_once_with("preset2")


class TestMappingListboxBase(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = Gtk.ListBox()
        self.listbox = MappingListBox(
            self.message_broker, self.controller_mock, self.gui
        )

        self.message_broker.publish(
            PresetData(
                "preset1",
                (
                    MappingData(
                        name="mapping1",
                        input_combination=InputCombination(
                            InputConfig(type=1, code=KEY_C)
                        ),
                    ),
                    MappingData(
                        name="",
                        input_combination=InputCombination(
                            (
                                InputConfig(type=1, code=KEY_A),
                                InputConfig(type=1, code=KEY_B),
                            )
                        ),
                    ),
                    MappingData(
                        name="mapping2",
                        input_combination=InputCombination(
                            InputConfig(type=1, code=KEY_B)
                        ),
                    ),
                ),
            )
        )

    def get_selected_row(self) -> MappingSelectionLabel:
        for label in self.gui.get_children():
            if label.is_selected():
                return label

        raise Exception("Expected one MappingSelectionLabel to be selected")

    def select_row(self, combination: InputCombination):
        def select(label_: MappingSelectionLabel):
            if label_.combination == combination:
                self.gui.select_row(label_)

        for label in self.gui.get_children():
            select(label)


class TestMappingListbox(TestMappingListboxBase):
    def setUp(self) -> None:
        super().setUp()

    def test_populates_listbox(self):
        labels = {row.name for row in self.gui.get_children()}
        self.assertEqual(labels, {"mapping1", "mapping2", "a + b"})

    def test_alphanumerically_sorted(self):
        labels = [row.name for row in self.gui.get_children()]
        self.assertEqual(labels, ["a + b", "mapping1", "mapping2"])

    def test_activates_correct_row(self):
        self.message_broker.publish(
            MappingData(
                name="mapping1",
                input_combination=InputCombination(InputConfig(type=1, code=KEY_C)),
            )
        )
        selected = self.get_selected_row()
        self.assertEqual(selected.name, "mapping1")
        self.assertEqual(
            selected.combination,
            InputCombination(InputConfig(type=1, code=KEY_C)),
        )

    def test_loads_mapping(self):
        self.select_row(InputCombination(InputConfig(type=1, code=KEY_B)))
        self.controller_mock.load_mapping.assert_called_once_with(
            InputCombination(InputConfig(type=1, code=KEY_B))
        )

    def test_avoids_infinite_recursion(self):
        self.message_broker.publish(
            MappingData(
                name="mapping1",
                input_combination=InputCombination(InputConfig(type=1, code=KEY_C)),
            )
        )
        self.controller_mock.load_mapping.assert_not_called()

    def test_sorts_empty_mapping_to_bottom(self):
        self.message_broker.publish(
            PresetData(
                "preset1",
                (
                    MappingData(
                        name="qux",
                        input_combination=InputCombination(
                            InputConfig(type=1, code=KEY_C)
                        ),
                    ),
                    MappingData(
                        name="foo",
                        input_combination=InputCombination.empty_combination(),
                    ),
                    MappingData(
                        name="bar",
                        input_combination=InputCombination(
                            InputConfig(type=1, code=KEY_B)
                        ),
                    ),
                ),
            )
        )
        bottom_row: MappingSelectionLabel = self.gui.get_row_at_index(2)
        self.assertEqual(bottom_row.combination, InputCombination.empty_combination())
        self.message_broker.publish(
            PresetData(
                "preset1",
                (
                    MappingData(
                        name="foo",
                        input_combination=InputCombination.empty_combination(),
                    ),
                    MappingData(
                        name="qux",
                        input_combination=InputCombination(
                            InputConfig(type=1, code=KEY_C)
                        ),
                    ),
                    MappingData(
                        name="bar",
                        input_combination=InputCombination(
                            InputConfig(type=1, code=KEY_B)
                        ),
                    ),
                ),
            )
        )
        bottom_row: MappingSelectionLabel = self.gui.get_row_at_index(2)
        self.assertEqual(bottom_row.combination, InputCombination.empty_combination())


class TestMappingFilterListbox(TestMappingListboxBase):
    def setUp(self) -> None:
        super().setUp()
        self.entry = Gtk.Entry()
        self.button = Gtk.Button()
        self.control = ListFilterControl(
            self.gui,
            self.entry,
            clear_button=self.button,
        )

    def get_num_visible(self):
        return len([c for c in self.gui.get_children() if c.get_visible()])

    def test_filter_entry(self):
        n = len(list(self.gui.get_children()))

        self.assertGreater(n, 2, "some mappings must be loaded")
        self.assertEqual(self.get_num_visible(), n, "all mappings must be visible")

        self.entry.set_text("not in preset")
        GtkKeyEvent(Gdk.KEY_Escape).emit_to(self.entry)
        self.assertEqual(self.entry.get_text(), "not in preset")
        self.assertEqual(self.get_num_visible(), 0 , "mappings must not be visible")

        self.button.clicked()
        gtk_iteration()
        self.assertEqual(self.entry.get_text(), "", "filter must be cleared")
        self.assertEqual(self.get_num_visible(), n, "all mappings must be visible again")

        self.entry.set_text("mapping1")
        GtkKeyEvent(Gdk.KEY_Escape).emit_to(self.entry)
        self.assertEqual(self.get_num_visible(), 1, "only one mapping must be visible")


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
        self.assertEqual(
            repr(self.mapping_selection_label),
            "MappingSelectionLabel for a + b as name",
        )

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
                InputCombination(InputConfig(type=1, code=KEY_A)),
            )
        )
        self.assertEqual(
            self.mapping_selection_label.combination,
            InputCombination(InputConfig(type=1, code=KEY_A)),
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
                InputCombination(InputConfig(type=1, code=KEY_A)),
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
                input_combination=InputCombination(
                    (
                        InputConfig(type=1, code=KEY_A),
                        InputConfig(type=1, code=KEY_B),
                    )
                ),
                name="foo",
            )
        )
        self.assertEqual(self.mapping_selection_label.label.get_label(), "foo")

    def test_ignores_mapping_when_combination_does_not_match(self):
        self.message_broker.publish(
            MappingData(
                input_combination=InputCombination(
                    (
                        InputConfig(type=1, code=KEY_A),
                        InputConfig(type=1, code=KEY_C),
                    )
                ),
                name="foo",
            )
        )
        self.assertEqual(self.mapping_selection_label.label.get_label(), "a + b")

    def test_edit_button_visibility(self):
        # start off invisible
        self.assertFalse(self.mapping_selection_label.edit_btn.get_visible())

        # load the mapping associated with the ListBoxRow
        self.message_broker.publish(
            MappingData(
                input_combination=InputCombination(
                    (
                        InputConfig(type=1, code=KEY_A),
                        InputConfig(type=1, code=KEY_B),
                    )
                ),
            )
        )
        self.assertTrue(self.mapping_selection_label.edit_btn.get_visible())

        # load a different row
        self.message_broker.publish(
            MappingData(
                input_combination=InputCombination(
                    (
                        InputConfig(type=1, code=KEY_A),
                        InputConfig(type=1, code=KEY_C),
                    )
                ),
            )
        )
        self.assertFalse(self.mapping_selection_label.edit_btn.get_visible())

    def test_enter_edit_mode_focuses_name_input(self):
        self.message_broker.publish(
            MappingData(
                input_combination=InputCombination(
                    (
                        InputConfig(type=1, code=KEY_A),
                        InputConfig(type=1, code=KEY_B),
                    )
                ),
            )
        )
        self.mapping_selection_label.edit_btn.clicked()
        self.controller_mock.set_focus.assert_called_once_with(
            self.mapping_selection_label.name_input
        )

    def test_enter_edit_mode_updates_visibility(self):
        self.message_broker.publish(
            MappingData(
                input_combination=InputCombination(
                    (
                        InputConfig(type=1, code=KEY_A),
                        InputConfig(type=1, code=KEY_B),
                    )
                ),
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
                input_combination=InputCombination(
                    (
                        InputConfig(type=1, code=KEY_A),
                        InputConfig(type=1, code=KEY_B),
                    )
                ),
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
                input_combination=InputCombination(
                    (
                        InputConfig(type=1, code=KEY_A),
                        InputConfig(type=1, code=KEY_B),
                    )
                ),
            )
        )
        self.mapping_selection_label.edit_btn.clicked()

        self.mapping_selection_label.name_input.set_text("foo")
        self.mapping_selection_label.name_input.activate()
        self.controller_mock.update_mapping.assert_called_once_with(name="foo")

    def test_name_input_contains_combination_when_name_not_set(self):
        self.message_broker.publish(
            MappingData(
                input_combination=InputCombination(
                    (
                        InputConfig(type=1, code=KEY_A),
                        InputConfig(type=1, code=KEY_B),
                    )
                ),
            )
        )
        self.mapping_selection_label.edit_btn.clicked()
        self.assertEqual(self.mapping_selection_label.name_input.get_text(), "a + b")

    def test_name_input_contains_name(self):
        self.message_broker.publish(
            MappingData(
                input_combination=InputCombination(
                    (
                        InputConfig(type=1, code=KEY_A),
                        InputConfig(type=1, code=KEY_B),
                    )
                ),
                name="foo",
            )
        )
        self.mapping_selection_label.edit_btn.clicked()
        self.assertEqual(self.mapping_selection_label.name_input.get_text(), "foo")

    def test_removes_name_when_name_matches_combination(self):
        self.message_broker.publish(
            MappingData(
                input_combination=InputCombination(
                    (
                        InputConfig(type=1, code=KEY_A),
                        InputConfig(type=1, code=KEY_B),
                    )
                ),
                name="foo",
            )
        )
        self.mapping_selection_label.edit_btn.clicked()
        self.mapping_selection_label.name_input.set_text("a + b")
        self.mapping_selection_label.name_input.activate()
        self.controller_mock.update_mapping.assert_called_once_with(name="")


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
        self.message_broker.publish(MappingData(output_symbol="foo"))
        self.assertEqual(self.get_text(), "foo")

    def test_shows_record_input_first_message_when_mapping_is_empty(self):
        self.controller_mock.is_empty_mapping.return_value = True
        self.message_broker.publish(MappingData(output_symbol="foo"))
        self.assertEqual(self.get_text(), "Record the input first")

    def test_active_when_mapping_is_not_empty(self):
        self.message_broker.publish(MappingData(output_symbol="foo"))
        self.assertTrue(self.gui.get_sensitive())
        self.assertEqual(self.gui.get_opacity(), 1)

    def test_expands_to_multiline(self):
        self.message_broker.publish(MappingData(output_symbol="foo\nbar"))
        self.assertIn("multiline", self.gui.get_style_context().list_classes())

    def test_shows_line_numbers_when_multiline(self):
        self.message_broker.publish(MappingData(output_symbol="foo\nbar"))
        self.assertTrue(self.gui.get_show_line_numbers())

    def test_no_multiline_when_macro_not_multiline(self):
        self.message_broker.publish(MappingData(output_symbol="foo"))
        self.assertNotIn("multiline", self.gui.get_style_context().list_classes())

    def test_no_line_numbers_macro_not_multiline(self):
        self.message_broker.publish(MappingData(output_symbol="foo"))
        self.assertFalse(self.gui.get_show_line_numbers())

    def test_is_empty_when_mapping_has_no_output_symbol(self):
        self.message_broker.publish(MappingData())
        self.assertEqual(self.get_text(), "")

    def test_updates_mapping(self):
        self.message_broker.publish(MappingData())
        buffer = self.gui.get_buffer()
        buffer.set_text("foo")
        self.controller_mock.update_mapping.assert_called_once_with(output_symbol="foo")

    def test_avoids_infinite_recursion_when_loading_mapping(self):
        self.message_broker.publish(MappingData(output_symbol="foo"))
        self.controller_mock.update_mapping.assert_not_called()

    def test_gets_focus_when_input_recording_finises(self):
        self.message_broker.signal(MessageType.recording_finished)
        self.controller_mock.set_focus.assert_called_once_with(self.gui)


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

    def get_tooltip(self) -> Optional[str]:
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


class TestAutoloadSwitch(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = Gtk.Switch()
        self.switch = AutoloadSwitch(
            self.message_broker, self.controller_mock, self.gui
        )

    def test_sets_autoload(self):
        self.gui.set_active(True)
        self.controller_mock.set_autoload.assert_called_once_with(True)
        self.controller_mock.reset_mock()
        self.gui.set_active(False)
        self.controller_mock.set_autoload.assert_called_once_with(False)

    def test_updates_state(self):
        self.message_broker.publish(PresetData(None, None, autoload=True))
        self.assertTrue(self.gui.get_active())
        self.message_broker.publish(PresetData(None, None, autoload=False))
        self.assertFalse(self.gui.get_active())

    def test_avoids_infinite_recursion(self):
        self.message_broker.publish(PresetData(None, None, autoload=True))
        self.message_broker.publish(PresetData(None, None, autoload=False))
        self.controller_mock.set_autoload.assert_not_called()


class TestReleaseCombinationSwitch(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = Gtk.Switch()
        self.switch = ReleaseCombinationSwitch(
            self.message_broker, self.controller_mock, self.gui
        )

    def test_updates_mapping(self):
        self.gui.set_active(True)
        self.controller_mock.update_mapping.assert_called_once_with(
            release_combination_keys=True
        )
        self.controller_mock.reset_mock()
        self.gui.set_active(False)
        self.controller_mock.update_mapping.assert_called_once_with(
            release_combination_keys=False
        )

    def test_updates_state(self):
        self.message_broker.publish(MappingData(release_combination_keys=True))
        self.assertTrue(self.gui.get_active())
        self.message_broker.publish(MappingData(release_combination_keys=False))
        self.assertFalse(self.gui.get_active())

    def test_avoids_infinite_recursion(self):
        self.message_broker.publish(MappingData(release_combination_keys=True))
        self.message_broker.publish(MappingData(release_combination_keys=False))
        self.controller_mock.update_mapping.assert_not_called()


class TestEventEntry(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = InputConfigEntry(
            InputConfig(type=3, code=0, analog_threshold=1), self.controller_mock
        )

    def test_move_event(self):
        self.gui._up_btn.clicked()
        self.controller_mock.move_input_config_in_combination.assert_called_once_with(
            InputConfig(type=3, code=0, analog_threshold=1), "up"
        )
        self.controller_mock.reset_mock()

        self.gui._down_btn.clicked()
        self.controller_mock.move_input_config_in_combination.assert_called_once_with(
            InputConfig(type=3, code=0, analog_threshold=1), "down"
        )


class TestCombinationListbox(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = Gtk.ListBox()
        self.listbox = CombinationListbox(
            self.message_broker, self.controller_mock, self.gui
        )
        self.controller_mock.is_empty_mapping.return_value = False
        combination = InputCombination(
            (
                InputConfig(type=1, code=1),
                InputConfig(type=3, code=0, analog_threshold=1),
                InputConfig(type=1, code=2),
            )
        )
        self.message_broker.publish(
            MappingData(
                input_combination=combination.to_config(), target_uinput="keyboard"
            )
        )

    def get_selected_row(self) -> InputConfigEntry:
        for entry in self.gui.get_children():
            if entry.is_selected():
                return entry

        raise Exception("Expected one InputConfigEntry to be selected")

    def select_row(self, input_cfg: InputConfig):
        for entry in self.gui.get_children():
            if entry.input_event == input_cfg:
                self.gui.select_row(entry)

    def test_loads_selected_row(self):
        self.select_row(InputConfig(type=1, code=2))
        self.controller_mock.load_input_config.assert_called_once_with(
            InputConfig(type=1, code=2)
        )

    def test_does_not_create_rows_when_mapping_is_empty(self):
        self.controller_mock.is_empty_mapping.return_value = True
        combination = InputCombination(
            (
                InputConfig(type=1, code=1),
                InputConfig(type=3, code=0, analog_threshold=1),
            )
        )
        self.message_broker.publish(MappingData(input_combination=combination))
        self.assertEqual(len(self.gui.get_children()), 0)

    def test_selects_row_when_selected_event_message_arrives(self):
        self.message_broker.publish(InputConfig(type=3, code=0, analog_threshold=1))
        self.assertEqual(
            self.get_selected_row().input_event,
            InputConfig(type=3, code=0, analog_threshold=1),
        )

    def test_avoids_infinite_recursion(self):
        self.message_broker.publish(InputConfig(type=3, code=0, analog_threshold=1))
        self.controller_mock.load_event.assert_not_called()


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


class TestTriggerThresholdInput(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = Gtk.SpinButton()
        self.input = TriggerThresholdInput(
            self.message_broker, self.controller_mock, self.gui
        )
        self.message_broker.publish(InputConfig(type=3, code=0, analog_threshold=-10))

    def assert_abs_event_config(self):
        self.assertEqual(self.gui.get_range(), (-99, 99))
        self.assertTrue(self.gui.get_sensitive())
        self.assertEqual(self.gui.get_opacity(), 1)

    def assert_rel_event_config(self):
        self.assertEqual(self.gui.get_range(), (-999, 999))
        self.assertTrue(self.gui.get_sensitive())
        self.assertEqual(self.gui.get_opacity(), 1)

    def assert_key_event_config(self):
        self.assertFalse(self.gui.get_sensitive())
        self.assertLess(self.gui.get_opacity(), 0.6)

    def test_updates_event(self):
        self.gui.set_value(15)
        self.controller_mock.update_input_config.assert_called_once_with(
            InputConfig(type=3, code=0, analog_threshold=15)
        )

    def test_sets_value_on_selected_event_message(self):
        self.message_broker.publish(InputConfig(type=3, code=0, analog_threshold=10))
        self.assertEqual(self.gui.get_value(), 10)

    def test_avoids_infinite_recursion(self):
        self.message_broker.publish(InputConfig(type=3, code=0, analog_threshold=10))
        self.controller_mock.update_input_config.assert_not_called()

    def test_updates_configuration_according_to_selected_event(self):
        self.assert_abs_event_config()
        self.message_broker.publish(InputConfig(type=2, code=0, analog_threshold=-10))
        self.assert_rel_event_config()
        self.message_broker.publish(InputConfig(type=1, code=1))
        self.assert_key_event_config()


class TestReleaseTimeoutInput(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = Gtk.SpinButton()
        self.input = ReleaseTimeoutInput(
            self.message_broker, self.controller_mock, self.gui
        )
        self.message_broker.publish(
            MappingData(
                input_combination=InputCombination(
                    InputConfig(type=2, code=0, analog_threshold=1)
                ),
                target_uinput="keyboard",
            )
        )

    def test_updates_timeout_on_mapping_message(self):
        self.message_broker.publish(
            MappingData(
                input_combination=InputCombination(
                    InputConfig(type=2, code=0, analog_threshold=1)
                ),
                release_timeout=1,
            )
        )
        self.assertEqual(self.gui.get_value(), 1)

    def test_updates_mapping(self):
        self.gui.set_value(0.5)
        self.controller_mock.update_mapping.assert_called_once_with(release_timeout=0.5)

    def test_avoids_infinite_recursion(self):
        self.message_broker.publish(
            MappingData(
                input_combination=InputCombination(
                    InputConfig(type=2, code=0, analog_threshold=1)
                ),
                release_timeout=1,
            )
        )
        self.controller_mock.update_mapping.assert_not_called()

    def test_disables_input_based_on_input_combination(self):
        self.message_broker.publish(
            MappingData(
                input_combination=InputCombination(
                    (
                        InputConfig(type=2, code=0, analog_threshold=1),
                        InputConfig(type=1, code=1),
                    )
                )
            )
        )
        self.assertTrue(self.gui.get_sensitive())
        self.assertEqual(self.gui.get_opacity(), 1)

        self.message_broker.publish(
            MappingData(
                input_combination=InputCombination(
                    (
                        InputConfig(type=1, code=1),
                        InputConfig(type=1, code=2),
                    )
                )
            )
        )
        self.assertFalse(self.gui.get_sensitive())
        self.assertLess(self.gui.get_opacity(), 0.6)

        self.message_broker.publish(
            MappingData(
                input_combination=InputCombination(
                    (
                        InputConfig(type=2, code=0, analog_threshold=1),
                        InputConfig(type=1, code=1),
                    )
                )
            )
        )
        self.message_broker.publish(
            MappingData(
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
        self.assertFalse(self.gui.get_sensitive())
        self.assertLess(self.gui.get_opacity(), 0.6)


class TestOutputAxisSelector(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = Gtk.ComboBox()
        self.selection = OutputAxisSelector(
            self.message_broker, self.controller_mock, self.gui
        )
        absinfo = evdev.AbsInfo(0, -10, 10, 0, 0, 0)
        self.message_broker.publish(
            UInputsData(
                {
                    "mouse": {1: [1, 2, 3, 4], 2: [0, 1, 2, 3]},
                    "keyboard": {1: [1, 2, 3, 4]},
                    "gamepad": {
                        2: [0, 1, 2, 3],
                        3: [(0, absinfo), (1, absinfo), (2, absinfo), (3, absinfo)],
                    },
                }
            )
        )
        self.message_broker.publish(
            MappingData(
                target_uinput="mouse",
                input_combination=InputCombination(InputConfig(type=1, code=1)),
            )
        )

    def set_active_selection(self, selection: Tuple):
        self.gui.set_active_id(f"{selection[0]}, {selection[1]}")

    def get_active_selection(self) -> Tuple[int, int]:
        return tuple(int(i) for i in self.gui.get_active_id().split(","))  # type: ignore

    def test_updates_mapping(self):
        self.set_active_selection((2, 0))
        self.controller_mock.update_mapping.assert_called_once_with(
            output_type=2, output_code=0
        )

    def test_updates_mapping_with_none(self):
        self.set_active_selection((2, 0))
        self.controller_mock.reset_mock()
        self.set_active_selection((None, None))
        self.controller_mock.update_mapping.assert_called_once_with(
            output_type=None, output_code=None
        )

    def test_selects_correct_entry(self):
        self.assertEqual(self.gui.get_active_id(), "None, None")
        self.message_broker.publish(
            MappingData(target_uinput="mouse", output_type=2, output_code=3)
        )
        self.assertEqual(self.get_active_selection(), (2, 3))

    def test_avoids_infinite_recursion(self):
        self.message_broker.publish(
            MappingData(target_uinput="mouse", output_type=2, output_code=3)
        )
        self.controller_mock.update_mapping.assert_not_called()

    def test_updates_dropdown_model(self):
        self.assertEqual(len(self.gui.get_model()), 5)
        self.message_broker.publish(MappingData(target_uinput="keyboard"))
        self.assertEqual(len(self.gui.get_model()), 1)
        self.message_broker.publish(MappingData(target_uinput="gamepad"))
        self.assertEqual(len(self.gui.get_model()), 9)


class TestKeyAxisStackSwitcher(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = Gtk.Box()
        self.gtk_stack = Gtk.Stack()
        self.analog_toggle = Gtk.ToggleButton()
        self.key_toggle = Gtk.ToggleButton()

        self.gui.add(self.gtk_stack)
        self.gui.add(self.analog_toggle)
        self.gui.add(self.key_toggle)
        self.gtk_stack.add_named(Gtk.Box(), "Analog Axis")
        self.gtk_stack.add_named(Gtk.Box(), "Key or Macro")

        self.stack = KeyAxisStackSwitcher(
            self.message_broker,
            self.controller_mock,
            self.gtk_stack,
            self.key_toggle,
            self.analog_toggle,
        )

        self.gui.show_all()
        self.gtk_stack.set_visible_child_name("Key or Macro")

    def assert_key_macro_active(self):
        self.assertEqual(self.gtk_stack.get_visible_child_name(), "Key or Macro")
        self.assertTrue(self.key_toggle.get_active())
        self.assertFalse(self.analog_toggle.get_active())

    def assert_analog_active(self):
        self.assertEqual(self.gtk_stack.get_visible_child_name(), "Analog Axis")
        self.assertFalse(self.key_toggle.get_active())
        self.assertTrue(self.analog_toggle.get_active())

    def test_switches_to_axis(self):
        self.message_broker.publish(MappingData(mapping_type="analog"))
        self.assert_analog_active()

    def test_switches_to_key_macro(self):
        self.message_broker.publish(MappingData(mapping_type="analog"))
        self.message_broker.publish(MappingData(mapping_type="key_macro"))
        self.assert_key_macro_active()

    def test_updates_mapping_type(self):
        self.key_toggle.set_active(True)
        self.controller_mock.update_mapping.assert_called_once_with(
            mapping_type="key_macro"
        )
        self.controller_mock.update_mapping.reset_mock()

        self.analog_toggle.set_active(True)
        self.controller_mock.update_mapping.assert_called_once_with(
            mapping_type="analog"
        )

    def test_avoids_infinite_recursion(self):
        self.message_broker.publish(MappingData(mapping_type="analog"))
        self.message_broker.publish(MappingData(mapping_type="key_macro"))
        self.controller_mock.update_mapping.assert_not_called()


class TestTransformationDrawArea(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = Gtk.Window()
        self.draw_area = Gtk.DrawingArea()
        self.gui.add(self.draw_area)
        self.transform_draw_area = TransformationDrawArea(
            self.message_broker,
            self.controller_mock,
            self.draw_area,
        )

    def test_draws_transform(self):
        with spy(self.transform_draw_area, "_transformation") as mock:
            # show the window, it takes some time and iterations until it pops up
            self.gui.show_all()
            for _ in range(5):
                gtk_iteration()
                time.sleep(0.01)

            mock.assert_called()

    def test_updates_transform_when_mapping_updates(self):
        old_tf = self.transform_draw_area._transformation
        self.message_broker.publish(MappingData(gain=2))
        self.assertIsNot(old_tf, self.transform_draw_area._transformation)

    def test_redraws_when_mapping_updates(self):
        self.gui.show_all()
        gtk_iteration(20)
        mock = MagicMock()
        self.draw_area.connect("draw", mock)
        self.message_broker.publish(MappingData(gain=2))
        gtk_iteration(20)
        mock.assert_called()


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
                input_combination=InputCombination(InputConfig(type=3, code=0)),
                target_uinput="mouse",
            )
        )

    @staticmethod
    def get_range(range: Gtk.Range) -> Tuple[int, int]:
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
                gain=0.5,
                deadzone=0.6,
                expo=0.3,
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
        self.message_broker.publish(MappingData(gain=0.5))
        self.controller_mock.update_mapping.assert_not_called()
        self.message_broker.publish(MappingData(expo=0.5))
        self.controller_mock.update_mapping.assert_not_called()
        self.message_broker.publish(MappingData(deadzone=0.5))
        self.controller_mock.update_mapping.assert_not_called()


class TestRelativeInputCutoffInput(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = Gtk.SpinButton()
        self.input = RelativeInputCutoffInput(
            self.message_broker, self.controller_mock, self.gui
        )
        self.message_broker.publish(
            MappingData(
                target_uinput="mouse",
                input_combination=InputCombination(InputConfig(type=2, code=0)),
                rel_to_abs_input_cutoff=1,
                output_type=3,
                output_code=0,
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
                target_uinput="mouse",
                input_combination=InputCombination(InputConfig(type=2, code=0)),
                rel_to_abs_input_cutoff=3,
                output_type=3,
                output_code=0,
            )
        )
        self.controller_mock.update_mapping.assert_not_called()

    def test_updates_value(self):
        rel_to_abs_input_cutoff = 3
        self.message_broker.publish(
            MappingData(
                target_uinput="mouse",
                input_combination=InputCombination(InputConfig(type=2, code=0)),
                rel_to_abs_input_cutoff=rel_to_abs_input_cutoff,
                output_type=3,
                output_code=0,
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
                target_uinput="mouse",
                input_combination=InputCombination(InputConfig(type=3, code=0)),
                output_type=3,
                output_code=0,
            )
        )
        self.assert_inactive()

    def test_disables_input_when_no_abs_axis_output(self):
        self.assert_active()
        self.message_broker.publish(
            MappingData(
                target_uinput="mouse",
                input_combination=InputCombination(InputConfig(type=2, code=0)),
                rel_to_abs_input_cutoff=3,
                output_type=2,
                output_code=0,
            )
        )
        self.assert_inactive()

    def test_enables_input(self):
        self.message_broker.publish(
            MappingData(
                target_uinput="mouse",
                input_combination=InputCombination(InputConfig(type=3, code=0)),
                output_type=3,
                output_code=0,
            )
        )
        self.assert_inactive()
        self.message_broker.publish(
            MappingData(
                target_uinput="mouse",
                input_combination=InputCombination(InputConfig(type=2, code=0)),
                rel_to_abs_input_cutoff=1,
                output_type=3,
                output_code=0,
            )
        )
        self.assert_active()


class TestRequireActiveMapping(ComponentBaseTest):
    def test_no_reqorded_input_required(self):
        self.box = Gtk.Box()
        RequireActiveMapping(
            self.message_broker,
            self.box,
            require_recorded_input=False,
        )
        combination = InputCombination(InputConfig(type=1, code=KEY_A))

        self.message_broker.publish(MappingData())
        self.assert_inactive(self.box)

        self.message_broker.publish(PresetData(name="preset", mappings=()))
        self.assert_inactive(self.box)

        # a mapping is available, that is all the widget needs to be activated. one
        # mapping is always selected, so there is no need to check the mapping message
        self.message_broker.publish(PresetData(name="preset", mappings=(combination,)))
        self.assert_active(self.box)

        self.message_broker.publish(MappingData(input_combination=combination))
        self.assert_active(self.box)

        self.message_broker.publish(MappingData())
        self.assert_active(self.box)

    def test_recorded_input_required(self):
        self.box = Gtk.Box()
        RequireActiveMapping(
            self.message_broker,
            self.box,
            require_recorded_input=True,
        )
        combination = InputCombination(InputConfig(type=1, code=KEY_A))

        self.message_broker.publish(MappingData())
        self.assert_inactive(self.box)

        self.message_broker.publish(PresetData(name="preset", mappings=()))
        self.assert_inactive(self.box)

        self.message_broker.publish(PresetData(name="preset", mappings=(combination,)))
        self.assert_inactive(self.box)

        # the widget will be enabled once a mapping with recorded input is selected
        self.message_broker.publish(MappingData(input_combination=combination))
        self.assert_active(self.box)

        # this mapping doesn't have input recorded, so the box is disabled
        self.message_broker.publish(MappingData())
        self.assert_inactive(self.box)

    def assert_inactive(self, widget: Gtk.Widget):
        self.assertFalse(widget.get_sensitive())
        self.assertLess(widget.get_opacity(), 0.6)
        self.assertGreater(widget.get_opacity(), 0.4)

    def assert_active(self, widget: Gtk.Widget):
        self.assertTrue(widget.get_sensitive())
        self.assertEqual(widget.get_opacity(), 1)


class TestStack(ComponentBaseTest):
    def test_switches_pages(self):
        self.stack = Gtk.Stack()
        self.stack.add_named(Gtk.Label(), "Devices")
        self.stack.add_named(Gtk.Label(), "Presets")
        self.stack.add_named(Gtk.Label(), "Editor")
        self.stack.show_all()
        stack_wrapper = Stack(self.message_broker, self.controller_mock, self.stack)

        self.message_broker.publish(DoStackSwitch(Stack.devices_page))
        self.assertEqual(self.stack.get_visible_child_name(), "Devices")

        self.message_broker.publish(DoStackSwitch(Stack.presets_page))
        self.assertEqual(self.stack.get_visible_child_name(), "Presets")

        self.message_broker.publish(DoStackSwitch(Stack.editor_page))
        self.assertEqual(self.stack.get_visible_child_name(), "Editor")


class TestBreadcrumbs(ComponentBaseTest):
    def test_breadcrumbs(self):
        self.label_1 = Gtk.Label()
        self.label_2 = Gtk.Label()
        self.label_3 = Gtk.Label()
        self.label_4 = Gtk.Label()
        self.label_5 = Gtk.Label()

        Breadcrumbs(
            self.message_broker,
            self.label_1,
            show_device_group=False,
            show_preset=False,
            show_mapping=False,
        )
        Breadcrumbs(
            self.message_broker,
            self.label_2,
            show_device_group=True,
            show_preset=False,
            show_mapping=False,
        )
        Breadcrumbs(
            self.message_broker,
            self.label_3,
            show_device_group=True,
            show_preset=True,
            show_mapping=False,
        )
        Breadcrumbs(
            self.message_broker,
            self.label_4,
            show_device_group=True,
            show_preset=True,
            show_mapping=True,
        )
        Breadcrumbs(
            self.message_broker,
            self.label_5,
            show_device_group=False,
            show_preset=False,
            show_mapping=True,
        )

        self.assertEqual(self.label_1.get_text(), "")
        self.assertEqual(self.label_2.get_text(), "?")
        self.assertEqual(self.label_3.get_text(), "?  /  ?")
        self.assertEqual(self.label_4.get_text(), "?  /  ?  /  ?")
        self.assertEqual(self.label_5.get_text(), "?")

        self.message_broker.publish(PresetData("preset", None))

        self.assertEqual(self.label_1.get_text(), "")
        self.assertEqual(self.label_2.get_text(), "?")
        self.assertEqual(self.label_3.get_text(), "?  /  preset")
        self.assertEqual(self.label_4.get_text(), "?  /  preset  /  ?")
        self.assertEqual(self.label_5.get_text(), "?")

        self.message_broker.publish(GroupData("group", ()))

        self.assertEqual(self.label_1.get_text(), "")
        self.assertEqual(self.label_2.get_text(), "group")
        self.assertEqual(self.label_3.get_text(), "group  /  preset")
        self.assertEqual(self.label_4.get_text(), "group  /  preset  /  ?")
        self.assertEqual(self.label_5.get_text(), "?")

        self.message_broker.publish(MappingData())

        self.assertEqual(self.label_1.get_text(), "")
        self.assertEqual(self.label_2.get_text(), "group")
        self.assertEqual(self.label_3.get_text(), "group  /  preset")
        self.assertEqual(self.label_4.get_text(), "group  /  preset  /  Empty Mapping")
        self.assertEqual(self.label_5.get_text(), "Empty Mapping")

        self.message_broker.publish(MappingData(name="mapping"))
        self.assertEqual(self.label_4.get_text(), "group  /  preset  /  mapping")
        self.assertEqual(self.label_5.get_text(), "mapping")

        combination = InputCombination(
            (
                InputConfig(type=1, code=KEY_A),
                InputConfig(type=1, code=KEY_B),
            )
        )
        self.message_broker.publish(MappingData(input_combination=combination))
        self.assertEqual(self.label_4.get_text(), "group  /  preset  /  a + b")
        self.assertEqual(self.label_5.get_text(), "a + b")

        combination = InputCombination(InputConfig(type=1, code=KEY_A))
        self.message_broker.publish(
            MappingData(name="qux", input_combination=combination)
        )
        self.assertEqual(self.label_4.get_text(), "group  /  preset  /  qux")
        self.assertEqual(self.label_5.get_text(), "qux")

if __name__ == "__main__":
    unittest.main()
