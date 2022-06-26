import unittest
from typing import List
from unittest.mock import MagicMock, patch
from evdev.ecodes import EV_KEY, KEY_A

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GLib", "2.0")
gi.require_version("GtkSource", "4")
from gi.repository import Gtk, GtkSource, Gdk, GObject, GLib

from inputremapper.gui.utils import gtk_iteration
from tests.test import quick_cleanup
from inputremapper.gui.message_broker import (
    MessageBroker,
    MessageType,
    GroupData,
    GroupsData,
    UInputsData,
    PresetData,
)
from inputremapper.gui.controller import Controller
from inputremapper.groups import GAMEPAD, KEYBOARD, GRAPHICS_TABLET
from inputremapper.gui.components import (
    DeviceSelection,
    TargetSelection,
    PresetSelection,
)
from inputremapper.gui.user_interface import UserInterface
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
