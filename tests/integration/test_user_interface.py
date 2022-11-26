import unittest
from unittest.mock import MagicMock

import gi
from evdev.ecodes import EV_KEY, KEY_A

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GLib", "2.0")
gi.require_version("GtkSource", "4")
from gi.repository import Gtk, Gdk, GLib

from tests.lib.cleanup import quick_cleanup
from inputremapper.gui.utils import gtk_iteration
from inputremapper.gui.messages.message_broker import MessageBroker, MessageType
from inputremapper.gui.user_interface import UserInterface
from inputremapper.configs.mapping import MappingData
from configs.input_config import InputCombination, InputConfig


class TestUserInterface(unittest.TestCase):
    def setUp(self) -> None:
        self.message_broker = MessageBroker()
        self.controller_mock = MagicMock()
        self.user_interface = UserInterface(self.message_broker, self.controller_mock)

    def tearDown(self) -> None:
        super().tearDown()
        self.message_broker.signal(MessageType.terminate)
        GLib.timeout_add(0, self.user_interface.window.destroy)
        GLib.timeout_add(0, Gtk.main_quit)
        Gtk.main()
        quick_cleanup()

    def test_shortcut(self):
        mock = MagicMock()
        self.user_interface.shortcuts[Gdk.KEY_x] = mock

        event = Gdk.Event()
        event.key.keyval = Gdk.KEY_x
        event.key.state = Gdk.ModifierType.SHIFT_MASK
        self.user_interface.window.emit("key-press-event", event)
        gtk_iteration()
        mock.assert_not_called()

        event.key.state = Gdk.ModifierType.CONTROL_MASK
        self.user_interface.window.emit("key-press-event", event)
        gtk_iteration()
        mock.assert_called_once()

        mock.reset_mock()
        event.key.keyval = Gdk.KEY_y
        self.user_interface.window.emit("key-press-event", event)
        gtk_iteration()
        mock.assert_not_called()

    def test_connected_shortcuts(self):
        should_be_connected = {Gdk.KEY_q, Gdk.KEY_r, Gdk.KEY_Delete, Gdk.KEY_n}
        connected = set(self.user_interface.shortcuts.keys())
        self.assertEqual(connected, should_be_connected)

        self.assertIs(
            self.user_interface.shortcuts[Gdk.KEY_q], self.controller_mock.close
        )
        self.assertIs(
            self.user_interface.shortcuts[Gdk.KEY_r],
            self.controller_mock.refresh_groups,
        )
        self.assertIs(
            self.user_interface.shortcuts[Gdk.KEY_Delete],
            self.controller_mock.stop_injecting,
        )

    def test_connect_disconnect_shortcuts(self):
        mock = MagicMock()
        self.user_interface.shortcuts[Gdk.KEY_x] = mock

        event = Gdk.Event()
        event.key.keyval = Gdk.KEY_x
        event.key.state = Gdk.ModifierType.CONTROL_MASK
        self.user_interface.disconnect_shortcuts()
        self.user_interface.window.emit("key-press-event", event)
        gtk_iteration()
        mock.assert_not_called()

        self.user_interface.connect_shortcuts()
        gtk_iteration()
        self.user_interface.window.emit("key-press-event", event)
        gtk_iteration()
        mock.assert_called_once()

    def test_combination_label_shows_combination(self):
        self.message_broker.publish(
            MappingData(
                event_combination=InputCombination(
                    InputConfig(type=EV_KEY, code=KEY_A)
                ),
                name="foo",
            )
        )
        gtk_iteration()
        label: Gtk.Label = self.user_interface.get("combination-label")
        self.assertEqual(label.get_text(), "a")
        self.assertEqual(label.get_opacity(), 1)

    def test_combination_label_shows_text_when_empty_mapping(self):
        self.message_broker.publish(MappingData())
        gtk_iteration()
        label: Gtk.Label = self.user_interface.get("combination-label")
        self.assertEqual(label.get_text(), "no input configured")

        # 0.5 != 0.501960..., for whatever reason this number is all screwed up
        self.assertAlmostEqual(label.get_opacity(), 0.5, delta=0.1)
