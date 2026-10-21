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

"""Testing the input-remapper-tray command and its helper class."""

import sys
import unittest
from unittest.mock import MagicMock, patch

import gi

try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
except ValueError:
    _orig_require_version = gi.require_version

    def _mock_require_version(namespace: str, version: str) -> None:
        if namespace == "AyatanaAppIndicator3":
            return
        _orig_require_version(namespace, version)

    gi.require_version = _mock_require_version
    sys.modules["gi.repository.AyatanaAppIndicator3"] = MagicMock()

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk

from inputremapper.bin.input_remapper_tray import InputRemapperTrayBin
from inputremapper.bin.process_utils import ProcessUtils
from inputremapper.configs.global_config import GlobalConfig
from tests.lib.patches import FakeDaemonProxy
from tests.lib.test_setup import test_setup


@unittest.skipIf(
    Gdk.Display.get_default() is None,
    "Display connection required for GTK widgets",
)
@test_setup
class TestTray(unittest.TestCase):
    def setUp(self):
        self.global_config = GlobalConfig()
        self.fake_daemon = FakeDaemonProxy()
        self.tray = InputRemapperTrayBin(
            self.global_config, gui_spawned=False, check_autostart=False
        )

    def _run_tray(self, tray: InputRemapperTrayBin | None = None) -> None:
        """Run the tray helper without blocking the test in Gtk.main()."""
        tray = tray or self.tray
        with (
            patch.object(ProcessUtils, "count_python_processes", return_value=1),
            patch("inputremapper.daemon.Daemon.connect", return_value=self.fake_daemon),
            patch.object(Gtk, "main", lambda: None),
        ):
            tray.run()

    def test_startup(self):
        """Startup test: verify the tray initializes cleanly without raising exceptions."""
        self._run_tray()
        self.assertIsNotNone(self.tray.indicator)
        self.assertIsNotNone(self.tray.toggle_item)
        self.assertEqual(self.tray.toggle_item.get_label(), "Suspend injection")

    def test_toggle_suspend(self):
        """Verify activating .toggle_item calls set_suspended with expected arguments."""
        self._run_tray()
        self.assertEqual(self.tray.toggle_item.get_label(), "Suspend injection")

        # Programmatically activate the toggle item to suspend
        self.tray.toggle_item.activate()
        self.assertEqual(self.fake_daemon.calls["set_suspended"], 1)
        self.assertTrue(self.fake_daemon.is_suspended())
        self.assertEqual(self.tray.toggle_item.get_label(), "Resume injection")

        # Activate again to resume
        self.tray.toggle_item.activate()
        self.assertEqual(self.fake_daemon.calls["set_suspended"], 2)
        self.assertFalse(self.fake_daemon.is_suspended())
        self.assertEqual(self.tray.toggle_item.get_label(), "Suspend injection")

    def test_on_suspended_changed_signal(self):
        """Verify D-Bus suspended_changed signal updates the UI reactively."""
        self._run_tray()

        self.fake_daemon._is_suspended = True
        self.fake_daemon.suspended_changed.emit(True)
        self.assertEqual(self.tray.toggle_item.get_label(), "Resume injection")

        self.fake_daemon._is_suspended = False
        self.fake_daemon.suspended_changed.emit(False)
        self.assertEqual(self.tray.toggle_item.get_label(), "Suspend injection")

    def test_on_groups_changed_signal(self):
        """Verify D-Bus groups_changed signal triggers menu rebuild."""
        self._run_tray()
        self.fake_daemon.groups_changed.emit("[]")
        self.assertIsNotNone(self.tray.toggle_item)

    def test_on_state_changed_signal(self):
        """Verify D-Bus state_changed signal triggers menu rebuild."""
        self._run_tray()
        self.fake_daemon.state_changed.emit("Foo Device")
        self.assertIsNotNone(self.tray.toggle_item)

    def test_autostart_disabled_exits(self):
        """Verify the tray exits when check_autostart=True and systray is disabled."""
        self.global_config.set_systray(False)
        tray = InputRemapperTrayBin(
            self.global_config, gui_spawned=False, check_autostart=True
        )
        with self.assertRaises(SystemExit) as cm:
            self._run_tray(tray)
        self.assertEqual(cm.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
