import unittest
from unittest.mock import MagicMock, patch
from evdev.ecodes import EV_KEY, KEY_A, KEY_B, KEY_C

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GLib", "2.0")
gi.require_version("GtkSource", "4")
from gi.repository import Gtk, GLib

from inputremapper.gui.utils import gtk_iteration
from tests.test import quick_cleanup
from inputremapper.gui.message_broker import (
    MessageBroker,
    MessageType,
    GroupData,
    GroupsData,
    UInputsData,
    PresetData,
    CombinationUpdate,
)
from inputremapper.groups import GAMEPAD, KEYBOARD, GRAPHICS_TABLET
from inputremapper.gui.components import (
    DeviceSelection,
    TargetSelection,
    PresetSelection,
    MappingListBox,
    SelectionLabel,
)
from inputremapper.configs.mapping import MappingData
from inputremapper.event_combination import EventCombination


class ComponentBaseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.message_broker = MessageBroker()
        self.controller_mock = MagicMock()
        self.gui = MagicMock()

    def tearDown(self) -> None:
        super().tearDown()
        self.message_broker.signal(MessageType.terminate)
        GLib.timeout_add(0, self.gui.destroy)
        GLib.timeout_add(0, Gtk.main_quit)
        Gtk.main()
        quick_cleanup()


class TestDeviceSelection(ComponentBaseTest):
    def setUp(self) -> None:
        super(TestDeviceSelection, self).setUp()
        self.gui = Gtk.ComboBox()
        self.selection = DeviceSelection(
            self.message_broker, self.controller_mock, self.gui
        )

    def init(self):
        self.message_broker.send(
            GroupsData(
                {"foo": [GAMEPAD, KEYBOARD], "bar": [], "baz": [GRAPHICS_TABLET]}
            )
        )
        gtk_iteration()

    def test_populates_devices(self):
        self.init()
        names = [row[0] for row in self.gui.get_model()]
        self.assertEqual(names, ["foo", "bar", "baz"])
        icons = [row[1] for row in self.gui.get_model()]
        self.assertEqual(icons, ["input-gaming", None, "input-tablet"])

        self.message_broker.send(
            GroupsData(
                {
                    "kuu": [KEYBOARD],
                    "qux": [GAMEPAD],
                }
            )
        )
        gtk_iteration()
        names = [row[0] for row in self.gui.get_model()]
        self.assertEqual(names, ["kuu", "qux"])
        icons = [row[1] for row in self.gui.get_model()]
        self.assertEqual(icons, ["input-keyboard", "input-gaming"])

    def test_selects_correct_device(self):
        self.init()
        self.message_broker.send(GroupData("bar", ()))
        gtk_iteration()
        self.assertEqual(self.gui.get_active_id(), "bar")
        self.message_broker.send(GroupData("baz", ()))
        gtk_iteration()
        self.assertEqual(self.gui.get_active_id(), "baz")

    def test_loads_group(self):
        self.init()
        self.gui.set_active_id("bar")
        gtk_iteration()
        self.controller_mock.load_group.assert_called_once_with("bar")

    def test_avoids_infinite_recursion(self):
        self.init()
        self.message_broker.send(GroupData("bar", ()))
        gtk_iteration()
        self.controller_mock.load_group.assert_not_called()


class TestTargetSelection(ComponentBaseTest):
    def setUp(self) -> None:
        super(TestTargetSelection, self).setUp()
        self.gui = Gtk.ComboBox()
        self.selection = TargetSelection(
            self.message_broker, self.controller_mock, self.gui
        )

    def init(self):
        self.message_broker.send(
            UInputsData(
                {
                    "foo": {},
                    "bar": {},
                    "baz": {},
                }
            )
        )
        gtk_iteration()

    def test_populates_devices(self):
        self.init()
        names = [row[0] for row in self.gui.get_model()]
        self.assertEqual(names, ["foo", "bar", "baz"])

        self.message_broker.send(
            UInputsData(
                {
                    "kuu": {},
                    "qux": {},
                }
            )
        )
        gtk_iteration()
        names = [row[0] for row in self.gui.get_model()]
        self.assertEqual(names, ["kuu", "qux"])

    def test_updates_mapping(self):
        self.init()
        self.gui.set_active_id("baz")
        gtk_iteration()
        self.controller_mock.update_mapping.called_once_with(target_uinput="baz")

    def test_selects_correct_target(self):
        self.init()
        self.message_broker.send(MappingData(target_uinput="baz"))
        gtk_iteration()
        self.assertEqual(self.gui.get_active_id(), "baz")
        self.message_broker.send(MappingData(target_uinput="bar"))
        gtk_iteration()
        self.assertEqual(self.gui.get_active_id(), "bar")

    def test_avoids_infinite_recursion(self):
        self.init()
        self.message_broker.send(MappingData(target_uinput="baz"))
        gtk_iteration()
        self.controller_mock.update_mapping.assert_not_called()

    def test_disabled_with_invalid_mapping(self):
        self.init()
        self.controller_mock.is_empty_mapping.return_value = True
        self.message_broker.send(MappingData())
        gtk_iteration()
        self.assertFalse(self.gui.get_sensitive())
        self.assertLess(self.gui.get_opacity(), 0.8)

    def test_enabled_with_valid_mapping(self):
        self.init()
        self.controller_mock.is_empty_mapping.return_value = False
        self.message_broker.send(MappingData())
        gtk_iteration()
        self.assertTrue(self.gui.get_sensitive())
        self.assertEqual(self.gui.get_opacity(), 1)


class TestPresetSelection(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = Gtk.ComboBoxText()
        self.selection = PresetSelection(
            self.message_broker, self.controller_mock, self.gui
        )

    def init(self):
        self.message_broker.send(GroupData("foo", ("preset1", "preset2")))
        gtk_iteration()

    def test_populates_presets(self):
        self.init()
        names = [row[0] for row in self.gui.get_model()]
        self.assertEqual(names, ["preset1", "preset2"])
        self.message_broker.send(GroupData("foo", ("preset3", "preset4")))
        gtk_iteration()
        names = [row[0] for row in self.gui.get_model()]
        self.assertEqual(names, ["preset3", "preset4"])

    def test_selects_preset(self):
        self.init()
        self.message_broker.send(
            PresetData("preset2", (("m1", EventCombination((1, 2, 3))),))
        )
        gtk_iteration()
        self.assertEqual(self.gui.get_active_id(), "preset2")
        self.message_broker.send(
            PresetData("preset1", (("m1", EventCombination((1, 2, 3))),))
        )
        gtk_iteration()
        self.assertEqual(self.gui.get_active_id(), "preset1")

    def test_avoids_infinite_recursion(self):
        self.init()
        self.message_broker.send(
            PresetData("preset2", (("m1", EventCombination((1, 2, 3))),))
        )
        gtk_iteration()
        self.controller_mock.load_preset.assert_not_called()

    def test_loads_preset(self):
        self.init()
        self.gui.set_active_id("preset2")
        gtk_iteration()
        self.controller_mock.load_preset.assert_called_once_with("preset2")


class TestMappingListbox(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = Gtk.ListBox()
        self.listbox = MappingListBox(
            self.message_broker, self.controller_mock, self.gui
        )

    def init(self):
        self.message_broker.send(
            PresetData(
                "preset1",
                (
                    ("mapping1", EventCombination((1, KEY_C, 1))),
                    ("", EventCombination([(1, KEY_A, 1), (1, KEY_B, 1)])),
                    ("mapping2", EventCombination((1, KEY_B, 1))),
                ),
            )
        )
        gtk_iteration()

    def get_selected_row(self) -> SelectionLabel:
        row = None

        def find_row(r: SelectionLabel):
            nonlocal row
            if r.is_selected():
                row = r

        self.gui.foreach(find_row)
        gtk_iteration()
        return row

    def select_row(self, combination: EventCombination):
        def select(row: SelectionLabel):
            if row.combination == combination:
                self.gui.select_row(row)

        self.gui.foreach(select)

    def test_populates_listbox(self):
        self.init()
        labels = {row.name for row in self.gui.get_children()}
        self.assertEqual(labels, {"mapping1", "mapping2", "a + b"})

    def test_alphanumerically_sorted(self):
        self.init()
        labels = [row.name for row in self.gui.get_children()]
        self.assertEqual(labels, ["a + b", "mapping1", "mapping2"])

    def test_activates_correct_row(self):
        self.init()
        self.message_broker.send(
            MappingData(
                name="mapping1", event_combination=EventCombination((1, KEY_C, 1))
            )
        )
        gtk_iteration()
        selected = self.get_selected_row()
        self.assertEqual(selected.name, "mapping1")
        self.assertEqual(selected.combination, EventCombination((1, KEY_C, 1)))

    def test_loads_mapping(self):
        self.init()
        self.select_row(EventCombination((1, KEY_B, 1)))
        gtk_iteration()
        self.controller_mock.load_mapping.assert_called_once_with(
            EventCombination((1, KEY_B, 1))
        )

    def test_avoids_infinite_recursion(self):
        self.init()
        self.message_broker.send(
            MappingData(
                name="mapping1", event_combination=EventCombination((1, KEY_C, 1))
            )
        )
        gtk_iteration()
        self.controller_mock.load_mapping.assert_not_called()

    def test_sorts_empty_mapping_to_bottom(self):
        self.message_broker.send(
            PresetData(
                "preset1",
                (
                    ("qux", EventCombination((1, KEY_C, 1))),
                    ("foo", EventCombination.empty_combination()),
                    ("bar", EventCombination((1, KEY_B, 1))),
                ),
            )
        )
        gtk_iteration()
        bottom_row: SelectionLabel = self.gui.get_row_at_index(2)
        self.assertEqual(bottom_row.combination, EventCombination.empty_combination())
        self.message_broker.send(
            PresetData(
                "preset1",
                (
                    ("foo", EventCombination.empty_combination()),
                    ("qux", EventCombination((1, KEY_C, 1))),
                    ("bar", EventCombination((1, KEY_B, 1))),
                ),
            )
        )
        gtk_iteration()
        bottom_row: SelectionLabel = self.gui.get_row_at_index(2)
        self.assertEqual(bottom_row.combination, EventCombination.empty_combination())


class TestSelectionLabel(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = Gtk.ListBox()

    def init(self):
        self.label = SelectionLabel(
            self.message_broker,
            self.controller_mock,
            "",
            EventCombination([(1, KEY_A, 1), (1, KEY_B, 1)]),
        )
        self.gui.insert(self.label, -1)

    def test_shows_combination_without_name(self):
        self.init()
        self.assertEqual(self.label.label.get_label(), "a + b")

    def test_shows_name_when_given(self):
        self.gui = SelectionLabel(
            self.message_broker,
            self.controller_mock,
            "foo",
            EventCombination([(1, KEY_A, 1), (1, KEY_B, 1)]),
        )
        self.assertEqual(self.gui.label.get_label(), "foo")

    def test_updates_combination_when_selected(self):
        self.init()
        self.gui.select_row(self.label)
        gtk_iteration()
        self.assertEqual(
            self.label.combination, EventCombination([(1, KEY_A, 1), (1, KEY_B, 1)])
        )
        self.message_broker.send(
            CombinationUpdate(
                EventCombination([(1, KEY_A, 1), (1, KEY_B, 1)]),
                EventCombination((1, KEY_A, 1)),
            )
        )
        gtk_iteration()
        self.assertEqual(self.label.combination, EventCombination((1, KEY_A, 1)))

    def test_doesnt_update_combination_when_not_selected(self):
        self.init()
        self.assertEqual(
            self.label.combination, EventCombination([(1, KEY_A, 1), (1, KEY_B, 1)])
        )
        self.message_broker.send(
            CombinationUpdate(
                EventCombination([(1, KEY_A, 1), (1, KEY_B, 1)]),
                EventCombination((1, KEY_A, 1)),
            )
        )
        gtk_iteration()
        self.assertEqual(
            self.label.combination, EventCombination([(1, KEY_A, 1), (1, KEY_B, 1)])
        )

    def test_updates_name_when_mapping_changed_and_combination_matches(self):
        self.init()
        self.message_broker.send(
            MappingData(
                event_combination=EventCombination([(1, KEY_A, 1), (1, KEY_B, 1)]),
                name="foo",
            )
        )
        gtk_iteration()
        self.assertEqual(self.label.label.get_label(), "foo")

    def test_ignores_mapping_when_combination_does_not_match(self):
        self.init()
        self.message_broker.send(
            MappingData(
                event_combination=EventCombination([(1, KEY_A, 1), (1, KEY_C, 1)]),
                name="foo",
            )
        )
        gtk_iteration()
        self.assertEqual(self.label.label.get_label(), "a + b")

    def test_edit_button_visibility(self):
        self.init()
        # start off invisible
        self.assertFalse(self.label.edit_btn.get_visible())

        # load the mapping associated with the ListBoxRow
        self.message_broker.send(
            MappingData(
                event_combination=EventCombination([(1, KEY_A, 1), (1, KEY_B, 1)]),
            )
        )
        gtk_iteration()
        self.assertTrue(self.label.edit_btn.get_visible())

        # load a different row
        self.message_broker.send(
            MappingData(
                event_combination=EventCombination([(1, KEY_A, 1), (1, KEY_C, 1)]),
            )
        )
        gtk_iteration()
        self.assertFalse(self.label.edit_btn.get_visible())

    def test_enter_edit_mode_focuses_name_input(self):
        self.init()
        self.message_broker.send(
            MappingData(
                event_combination=EventCombination([(1, KEY_A, 1), (1, KEY_B, 1)]),
            )
        )
        self.label.edit_btn.clicked()
        gtk_iteration()
        self.controller_mock.set_focus.assert_called_once_with(self.label.name_input)

    def test_enter_edit_mode_updates_visibility(self):
        self.init()
        self.message_broker.send(
            MappingData(
                event_combination=EventCombination([(1, KEY_A, 1), (1, KEY_B, 1)]),
            )
        )

        self.assertTrue(self.label.label.get_visible())
        self.assertFalse(self.label.name_input.get_visible())

        self.label.edit_btn.clicked()
        gtk_iteration()
        self.assertTrue(self.label.name_input.get_visible())
        self.assertFalse(self.label.label.get_visible())

        self.label.name_input.activate()  # aka hit the return key
        gtk_iteration()
        self.assertTrue(self.label.label.get_visible())
        self.assertFalse(self.label.name_input.get_visible())

    def test_update_name(self):
        self.init()
        self.message_broker.send(
            MappingData(
                event_combination=EventCombination([(1, KEY_A, 1), (1, KEY_B, 1)]),
            )
        )
        self.label.edit_btn.clicked()
        gtk_iteration()

        self.label.name_input.set_text("foo")
        self.label.name_input.activate()
        gtk_iteration()
        self.controller_mock.update_mapping.assert_called_once_with(name="foo")

    def test_name_input_contains_combination_when_name_not_set(self):
        self.init()
        self.message_broker.send(
            MappingData(
                event_combination=EventCombination([(1, KEY_A, 1), (1, KEY_B, 1)]),
            )
        )
        self.label.edit_btn.clicked()
        gtk_iteration()
        self.assertEqual(self.label.name_input.get_text(), "a + b")

    def test_name_input_contains_name(self):
        self.init()
        self.message_broker.send(
            MappingData(
                event_combination=EventCombination([(1, KEY_A, 1), (1, KEY_B, 1)]),
                name="foo",
            )
        )
        self.label.edit_btn.clicked()
        gtk_iteration()
        self.assertEqual(self.label.name_input.get_text(), "foo")

    def test_removes_name_when_name_matches_combination(self):
        self.init()
        self.message_broker.send(
            MappingData(
                event_combination=EventCombination([(1, KEY_A, 1), (1, KEY_B, 1)]),
                name="foo",
            )
        )
        self.label.edit_btn.clicked()
        gtk_iteration()
        self.label.name_input.set_text("a + b")
        self.label.name_input.activate()
        gtk_iteration()
        self.controller_mock.update_mapping.assert_called_once_with(name="")
