# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2026 sezanzeb <b8x45ygc9@mozmail.com>
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

"""Settings popover menu component."""

from __future__ import annotations

import subprocess
import gi
from gi.repository import Gtk

from inputremapper.bin.process_utils import ProcessUtils

from inputremapper.gui.controller import Controller
from inputremapper.gui.gettext import _
from inputremapper.logging.logger import logger

# Try importing AppIndicator to check if system tray is supported
HAS_APPINDICATOR = False
try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    HAS_APPINDICATOR = True
except (ImportError, ValueError):
    try:
        gi.require_version("AppIndicator3", "0.1")
        HAS_APPINDICATOR = True
    except (ImportError, ValueError):
        pass


class SettingsMenu:
    """Manages the settings menu popover in the window header bar."""

    def __init__(
        self,
        controller: Controller,
        systray_switch: Gtk.Switch,
        systray_row: Gtk.Box,
        systray_label: Gtk.Label,
    ):
        self.controller = controller
        self._switch = systray_switch
        self._row = systray_row
        self._label = systray_label

        # Detect if system tray was started standalone (independently of this GUI)
        is_standalone_running = False
        if HAS_APPINDICATOR:
            try:
                is_standalone_running = ProcessUtils.count_python_processes(
                    "input-remapper-tray"
                ) > ProcessUtils.count_python_processes(
                    "input-remapper-tray", ["--gui-spawned"]
                )
            except Exception:
                pass

        enabled = (
            HAS_APPINDICATOR
            and self.controller.data_manager.global_config.get_systray()
        )

        self._is_standalone_running = is_standalone_running

        if is_standalone_running:
            self._switch.set_active(True)
            self._row.set_sensitive(False)
            self._label.set_text(_("Close to system tray (Standalone)"))
        elif not HAS_APPINDICATOR:
            self._row.set_sensitive(False)
            self._label.set_text(_("Close to system tray (Requires AppIndicator)"))
        else:
            self._row.set_sensitive(True)
            self._label.set_text(_("Close to system tray"))
            self._switch.set_active(enabled)

        # Start the tray helper process if it is enabled and not already running
        if enabled:
            self._spawn_tray_if_needed()

        self._switch.connect("notify::active", self._on_switch_active_changed)

    def _on_switch_active_changed(self, widget: Gtk.Switch, _gparam) -> None:
        active = widget.get_active()
        self.controller.data_manager.global_config.set_systray(active)
        if active:
            self._spawn_tray_if_needed()

    def _spawn_tray_if_needed(self) -> None:
        """Start the tray helper process if not already running."""
        try:
            if ProcessUtils.count_python_processes("input-remapper-tray") == 0:
                logger.info("Spawning detached system tray process")
                subprocess.Popen(["input-remapper-tray", "--gui-spawned"])
        except Exception as e:
            logger.error("Failed to spawn input-remapper-tray: %s", e)
