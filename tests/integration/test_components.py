import unittest
from typing import Optional
from unittest.mock import MagicMock, patch
from evdev.ecodes import EV_KEY, KEY_A, KEY_B, KEY_C

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GLib", "2.0")
gi.require_version("GtkSource", "4")
from gi.repository import Gtk, GLib, GtkSource

from inputremapper.gui.utils import gtk_iteration, CTX_ERROR, CTX_WARNING
from tests.test import quick_cleanup
from inputremapper.gui.message_broker import (
    MessageBroker,
    MessageType,
    GroupData,
    GroupsData,
    UInputsData,
    PresetData,
    CombinationUpdate,
    StatusData,
)
from inputremapper.groups import GAMEPAD, KEYBOARD, GRAPHICS_TABLET
from inputremapper.gui.components import (
    DeviceSelection,
    TargetSelection,
    PresetSelection,
    MappingListBox,
    SelectionLabel,
    CodeEditor,
    RecordingToggle,
    StatusBar,
    AutoloadSwitch,
    ReleaseCombinationSwitch,
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
        self.message_broker.send(
            GroupsData(
                {"foo": [GAMEPAD, KEYBOARD], "bar": [], "baz": [GRAPHICS_TABLET]}
            )
        )
        gtk_iteration()

    def test_populates_devices(self):
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
        self.message_broker.send(GroupData("bar", ()))
        gtk_iteration()
        self.assertEqual(self.gui.get_active_id(), "bar")
        self.message_broker.send(GroupData("baz", ()))
        gtk_iteration()
        self.assertEqual(self.gui.get_active_id(), "baz")

    def test_loads_group(self):
        self.gui.set_active_id("bar")
        gtk_iteration()
        self.controller_mock.load_group.assert_called_once_with("bar")

    def test_avoids_infinite_recursion(self):
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
        self.gui.set_active_id("baz")
        gtk_iteration()
        self.controller_mock.update_mapping.called_once_with(target_uinput="baz")

    def test_selects_correct_target(self):
        self.message_broker.send(MappingData(target_uinput="baz"))
        gtk_iteration()
        self.assertEqual(self.gui.get_active_id(), "baz")
        self.message_broker.send(MappingData(target_uinput="bar"))
        gtk_iteration()
        self.assertEqual(self.gui.get_active_id(), "bar")

    def test_avoids_infinite_recursion(self):
        self.message_broker.send(MappingData(target_uinput="baz"))
        gtk_iteration()
        self.controller_mock.update_mapping.assert_not_called()

    def test_disabled_with_invalid_mapping(self):
        self.controller_mock.is_empty_mapping.return_value = True
        self.message_broker.send(MappingData())
        gtk_iteration()
        self.assertFalse(self.gui.get_sensitive())
        self.assertLess(self.gui.get_opacity(), 0.8)

    def test_enabled_with_valid_mapping(self):
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
        self.message_broker.send(GroupData("foo", ("preset1", "preset2")))
        gtk_iteration()

    def test_populates_presets(self):
        names = [row[0] for row in self.gui.get_model()]
        self.assertEqual(names, ["preset1", "preset2"])
        self.message_broker.send(GroupData("foo", ("preset3", "preset4")))
        gtk_iteration()
        names = [row[0] for row in self.gui.get_model()]
        self.assertEqual(names, ["preset3", "preset4"])

    def test_selects_preset(self):
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
        self.message_broker.send(
            PresetData("preset2", (("m1", EventCombination((1, 2, 3))),))
        )
        gtk_iteration()
        self.controller_mock.load_preset.assert_not_called()

    def test_loads_preset(self):
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
        labels = {row.name for row in self.gui.get_children()}
        self.assertEqual(labels, {"mapping1", "mapping2", "a + b"})

    def test_alphanumerically_sorted(self):
        labels = [row.name for row in self.gui.get_children()]
        self.assertEqual(labels, ["a + b", "mapping1", "mapping2"])

    def test_activates_correct_row(self):
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
        self.select_row(EventCombination((1, KEY_B, 1)))
        gtk_iteration()
        self.controller_mock.load_mapping.assert_called_once_with(
            EventCombination((1, KEY_B, 1))
        )

    def test_avoids_infinite_recursion(self):
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
        self.label = SelectionLabel(
            self.message_broker,
            self.controller_mock,
            "",
            EventCombination([(1, KEY_A, 1), (1, KEY_B, 1)]),
        )
        self.gui.insert(self.label, -1)

    def test_shows_combination_without_name(self):
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
        self.message_broker.send(
            MappingData(
                event_combination=EventCombination([(1, KEY_A, 1), (1, KEY_B, 1)]),
                name="foo",
            )
        )
        gtk_iteration()
        self.assertEqual(self.label.label.get_label(), "foo")

    def test_ignores_mapping_when_combination_does_not_match(self):
        self.message_broker.send(
            MappingData(
                event_combination=EventCombination([(1, KEY_A, 1), (1, KEY_C, 1)]),
                name="foo",
            )
        )
        gtk_iteration()
        self.assertEqual(self.label.label.get_label(), "a + b")

    def test_edit_button_visibility(self):
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
        self.message_broker.send(
            MappingData(
                event_combination=EventCombination([(1, KEY_A, 1), (1, KEY_B, 1)]),
            )
        )
        self.label.edit_btn.clicked()
        gtk_iteration()
        self.controller_mock.set_focus.assert_called_once_with(self.label.name_input)

    def test_enter_edit_mode_updates_visibility(self):
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
        self.message_broker.send(
            MappingData(
                event_combination=EventCombination([(1, KEY_A, 1), (1, KEY_B, 1)]),
            )
        )
        self.label.edit_btn.clicked()
        gtk_iteration()
        self.assertEqual(self.label.name_input.get_text(), "a + b")

    def test_name_input_contains_name(self):
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


class TestCodeEditor(ComponentBaseTest):
    def setUp(self) -> None:
        super(TestCodeEditor, self).setUp()
        self.gui = GtkSource.View()
        self.editor = CodeEditor(self.message_broker, self.controller_mock, self.gui)
        self.controller_mock.is_empty_mapping.return_value = False

    def get_text(self) -> str:
        buffer = self.gui.get_buffer()
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)

    def test_shows_output_symbol(self):
        self.message_broker.send(MappingData(output_symbol="foo"))
        self.assertEqual(self.get_text(), "foo")

    def test_shows_record_input_first_message_when_mapping_is_empty(self):
        self.controller_mock.is_empty_mapping.return_value = True
        self.message_broker.send(MappingData(output_symbol="foo"))
        self.assertEqual(self.get_text(), "Record the input first")

    def test_inactive_when_mapping_is_empty(self):
        self.controller_mock.is_empty_mapping.return_value = True
        self.message_broker.send(MappingData(output_symbol="foo"))
        self.assertFalse(self.gui.get_sensitive())
        self.assertLess(self.gui.get_opacity(), 0.6)

    def test_active_when_mapping_is_not_empty(self):
        self.message_broker.send(MappingData(output_symbol="foo"))
        self.assertTrue(self.gui.get_sensitive())
        self.assertEqual(self.gui.get_opacity(), 1)

    def test_expands_to_multiline(self):
        self.message_broker.send(MappingData(output_symbol="foo\nbar"))
        self.assertIn("multiline", self.gui.get_style_context().list_classes())

    def test_shows_line_numbers_when_multiline(self):
        self.message_broker.send(MappingData(output_symbol="foo\nbar"))
        self.assertTrue(self.gui.get_show_line_numbers())

    def test_no_multiline_when_macro_not_multiline(self):
        self.message_broker.send(MappingData(output_symbol="foo"))
        self.assertNotIn("multiline", self.gui.get_style_context().list_classes())

    def test_no_line_numbers_macro_not_multiline(self):
        self.message_broker.send(MappingData(output_symbol="foo"))
        self.assertFalse(self.gui.get_show_line_numbers())

    def test_is_empty_when_mapping_has_no_output_symbol(self):
        self.message_broker.send(MappingData())
        self.assertEqual(self.get_text(), "")

    def test_updates_mapping(self):
        self.message_broker.send(MappingData())
        buffer = self.gui.get_buffer()
        buffer.set_text("foo")
        self.controller_mock.update_mapping.assert_called_once_with(output_symbol="foo")

    def test_avoids_infinite_recursion_when_loading_mapping(self):
        self.message_broker.send(MappingData(output_symbol="foo"))
        self.controller_mock.update_mapping.assert_not_called()

    def test_gets_focus_when_input_recording_finises(self):
        self.message_broker.signal(MessageType.recording_finished)
        self.controller_mock.set_focus.assert_called_once_with(self.gui)


class TestRecordingToggle(ComponentBaseTest):
    def setUp(self) -> None:
        super(TestRecordingToggle, self).setUp()
        self.gui = Gtk.ToggleButton()
        self.toggle = RecordingToggle(
            self.message_broker, self.controller_mock, self.gui
        )

    def assert_recording(self):
        self.assertEqual(self.gui.get_label(), "Recording ...")
        self.assertTrue(self.gui.get_active())

    def assert_not_recording(self):
        self.assertEqual(self.gui.get_label(), "Record Input")
        self.assertFalse(self.gui.get_active())

    def test_starts_recording(self):
        self.gui.set_active(True)
        self.controller_mock.start_key_recording.assert_called_once()

    def test_stops_recording_when_clicked(self):
        self.gui.set_active(True)
        self.gui.set_active(False)
        self.controller_mock.stop_key_recording.assert_called_once()

    def test_not_recording_initially(self):
        self.assert_not_recording()

    def test_shows_recording_when_toggled(self):
        self.gui.set_active(True)
        self.assert_recording()

    def test_shows_not_recording_after_toggle(self):
        self.gui.set_active(True)
        self.gui.set_active(False)
        self.assert_not_recording()

    def test_shows_not_recording_when_recording_finished(self):
        self.gui.set_active(True)
        self.message_broker.signal(MessageType.recording_finished)
        self.assert_not_recording()


class TestStatusBar(ComponentBaseTest):
    def setUp(self) -> None:
        super(TestStatusBar, self).setUp()
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
        self.message_broker.send(StatusData(CTX_ERROR, "msg", "tooltip"))
        self.assertEqual(self.get_text(), "msg")
        self.assertEqual(self.get_tooltip(), "tooltip")
        self.assert_error_status()

    def test_shows_warning_status(self):
        self.message_broker.send(StatusData(CTX_WARNING, "msg", "tooltip"))
        self.assertEqual(self.get_text(), "msg")
        self.assertEqual(self.get_tooltip(), "tooltip")
        self.assert_warning_status()

    def test_shows_newest_message(self):
        self.message_broker.send(StatusData(CTX_ERROR, "msg", "tooltip"))
        self.message_broker.send(StatusData(CTX_WARNING, "msg2", "tooltip2"))
        self.assertEqual(self.get_text(), "msg2")
        self.assertEqual(self.get_tooltip(), "tooltip2")
        self.assert_warning_status()

    def test_data_without_message_removes_messages(self):
        self.message_broker.send(StatusData(CTX_WARNING, "msg", "tooltip"))
        self.message_broker.send(StatusData(CTX_WARNING, "msg2", "tooltip2"))
        self.message_broker.send(StatusData(CTX_WARNING))
        self.assert_empty()

    def test_restores_message_from_not_removed_ctx_id(self):
        self.message_broker.send(StatusData(CTX_ERROR, "msg", "tooltip"))
        self.message_broker.send(StatusData(CTX_WARNING, "msg2", "tooltip2"))
        self.message_broker.send(StatusData(CTX_WARNING))
        self.assertEqual(self.get_text(), "msg")
        self.assert_error_status()

        # works also the other way round
        self.message_broker.send(StatusData(CTX_ERROR))
        self.message_broker.send(StatusData(CTX_WARNING, "msg", "tooltip"))
        self.message_broker.send(StatusData(CTX_ERROR, "msg2", "tooltip2"))
        self.message_broker.send(StatusData(CTX_ERROR))
        self.assertEqual(self.get_text(), "msg")
        self.assert_warning_status()

    def test_sets_msg_as_tooltip_if_tooltip_is_none(self):
        self.message_broker.send(StatusData(CTX_ERROR, "msg"))
        self.assertEqual(self.get_tooltip(), "msg")


class TestAutoloadSwitch(ComponentBaseTest):
    def setUp(self) -> None:
        super(TestAutoloadSwitch, self).setUp()
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
        self.message_broker.send(PresetData(None, None, autoload=True))
        self.assertTrue(self.gui.get_active())
        self.message_broker.send(PresetData(None, None, autoload=False))
        self.assertFalse(self.gui.get_active())

    def test_avoids_infinite_recursion(self):
        self.message_broker.send(PresetData(None, None, autoload=True))
        self.message_broker.send(PresetData(None, None, autoload=False))
        self.controller_mock.set_autoload.assert_not_called()


class TestReleaseCombinationSwitch(ComponentBaseTest):
    def setUp(self) -> None:
        super(TestReleaseCombinationSwitch, self).setUp()
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
        self.message_broker.send(MappingData(release_combination_keys=True))
        self.assertTrue(self.gui.get_active())
        self.message_broker.send(MappingData(release_combination_keys=False))
        self.assertFalse(self.gui.get_active())

    def test_avoids_infinite_recursion(self):
        self.message_broker.send(MappingData(release_combination_keys=True))
        self.message_broker.send(MappingData(release_combination_keys=False))
        self.controller_mock.update_mapping.assert_not_called()
