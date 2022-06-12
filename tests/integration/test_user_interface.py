import unittest
from unittest.mock import MagicMock, patch

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GLib", "2.0")
gi.require_version("GtkSource", "4")
from gi.repository import Gtk, GtkSource, Gdk, GObject, GLib

from inputremapper.gui.utils import gtk_iteration
from tests.test import quick_cleanup
from inputremapper.gui.data_bus import DataBus, MessageType
from inputremapper.gui.user_interface import UserInterface


class TestUserInterface(unittest.TestCase):
    def setUp(self) -> None:
        self.data_bus = DataBus()
        self.controller_mock = MagicMock()
        self.user_interface = UserInterface(self.data_bus, self.controller_mock)

    def tearDown(self) -> None:
        super().tearDown()
        self.data_bus.signal(MessageType.terminate)
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
        should_be_connected = {Gdk.KEY_q, Gdk.KEY_r, Gdk.KEY_Delete}
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
