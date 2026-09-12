# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2026 sezanzeb <b8x45ygc9@mozmail.com>
#
# This file is part of input-remapper.
#
# input-remapper is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your order) any later version.
#
# input-remapper is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with input-remapper.  If not, see <https://www.gnu.org/licenses/>.

"""System tray helper process."""

from __future__ import annotations

import glob
import os
import subprocess
import sys
import threading

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GLib", "2.0")
from gi.repository import GLib, Gtk

# Try importing AppIndicator
HAS_APPINDICATOR = False
AppIndicator = None

# Attempt AyatanaAppIndicator3 first (modern standard)
try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import (
        AyatanaAppIndicator3 as AppIndicator,  # type: ignore[assignment, no-redef]
    )

    HAS_APPINDICATOR = True
except (ImportError, ValueError):
    # Fallback to older AppIndicator3
    try:
        gi.require_version("AppIndicator3", "0.1")
        from gi.repository import (
            AppIndicator3 as AppIndicator,  # type: ignore[assignment, no-redef]
        )

        HAS_APPINDICATOR = True
    except (ImportError, ValueError):
        pass

from inputremapper.bin.process_utils import ProcessUtils
from inputremapper.configs.data import get_data_path
from inputremapper.configs.global_config import GlobalConfig
from inputremapper.configs.paths import PathUtils
from inputremapper.daemon import Daemon, DaemonProxy
from inputremapper.groups import groups
from inputremapper.gui.gettext import _
from inputremapper.injection.injector import InjectorState
from inputremapper.logging.logger import logger


class InputRemapperTrayBin:
    def __init__(self, global_config: GlobalConfig) -> None:
        self.global_config = global_config
        self.daemon: DaemonProxy | None = None
        self.indicator: AppIndicator.Indicator | None = None
        self.is_supported = HAS_APPINDICATOR
        self.toggle_item: Gtk.MenuItem | None = None

        # Last known states to prevent redundant menu rebuilds during polling
        self.last_suspended: bool | None = None
        self.last_states: dict[str, tuple[InjectorState, str]] = {}
        self.poll_count = 0
        self.last_config_mtime: float | None = None
        self.last_presets_mtimes: dict[str, float] = {}
        self.refresh_thread: threading.Thread | None = None
        self.refresh_lock = threading.Lock()
        self.gui_spawned = "--gui-spawned" in sys.argv

    @staticmethod
    def main() -> None:
        logger.update_verbosity(True)
        global_config = GlobalConfig()
        tray = InputRemapperTrayBin(global_config)
        tray.run()

    def run(self) -> None:
        if ProcessUtils.count_python_processes("input-remapper-tray") >= 2:
            logger.info(
                "Another input-remapper tray helper is already running. Exiting."
            )
            sys.exit(0)

        if not self.is_supported:
            try:
                dialog = Gtk.MessageDialog(
                    transient_for=None,
                    flags=0,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text=_("AppIndicator is not found"),
                )
                dialog.format_secondary_text(
                    _(
                        "The AppIndicator package (libayatana-appindicator) is "
                        "required for the system tray icon helper to run.\n"
                        "Please install it using your package manager."
                    )
                )
                dialog.run()
                dialog.destroy()
            except Exception as e:
                logger.error("Failed to show AppIndicator error dialog: %s", e)

            logger.error("AppIndicator is not found. Exiting.")
            sys.exit(1)

        try:
            self.daemon = Daemon.connect(fallback=False)
        except Exception as e:
            logger.error("Failed to connect to daemon: %s", e)
            sys.exit(2)

        self.show()

        # Check status and auto-exit settings every 2 seconds
        GLib.timeout_add_seconds(2, self._poll_state)

        Gtk.main()

    def show(self) -> None:
        icon_name = "input-remapper"
        logger.info("Starting AppIndicator system tray helper")

        self.indicator = AppIndicator.Indicator.new(
            "input-remapper",
            icon_name,
            AppIndicator.IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_icon_theme_path(get_data_path(""))
        self.indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.indicator.set_title("input remapper")
        self.rebuild_menu()

    def rebuild_menu(self) -> None:
        if self.daemon is None:
            return
        menu = Gtk.Menu()

        show_item = Gtk.MenuItem(label=_("Open GUI"))
        show_item.connect("activate", self._on_show_activate)
        menu.append(show_item)

        # Devices submenu
        devices_item = Gtk.MenuItem(label=_("Devices"))
        devices_menu = Gtk.Menu()
        devices_item.set_submenu(devices_menu)
        menu.append(devices_item)

        # Populate connected devices
        self._refresh_groups_silently()
        group_keys = [group.key for group in groups.get_groups()]
        current_states = {}

        has_any_device_with_presets = False

        if group_keys:
            for group_key in group_keys:
                group = groups.find(key=group_key)
                if not group:
                    continue

                # Get state and running preset of this device
                try:
                    state = self.daemon.get_state(group_key)
                    running_preset = self.daemon.get_running_preset(group_key)
                except Exception as e:
                    logger.error("Failed to query daemon for device state: %s", e)
                    state = InjectorState.UNKNOWN
                    running_preset = ""

                current_states[group_key] = (state, running_preset)

                # Available presets for this device group
                presets = self._get_preset_names_for_group(group.name)
                if not presets:
                    continue

                has_any_device_with_presets = True

                device_item = Gtk.MenuItem(label=group.name)
                device_menu = Gtk.Menu()
                device_item.set_submenu(device_menu)
                devices_menu.append(device_item)

                is_active = state in {
                    InjectorState.RUNNING,
                    InjectorState.STARTING,
                    InjectorState.ERROR,
                    InjectorState.NO_GRAB,
                    InjectorState.UPGRADE_EVDEV,
                }

                for preset_name in presets:
                    preset_item = Gtk.CheckMenuItem(label=preset_name)
                    preset_item.set_active(is_active and running_preset == preset_name)
                    preset_item.connect(
                        "activate",
                        self._on_device_preset_toggle,
                        group_key,
                        preset_name,
                    )
                    device_menu.append(preset_item)

        if not has_any_device_with_presets:
            empty_item = Gtk.MenuItem(label=_("No presets configured"))
            empty_item.set_sensitive(False)
            devices_menu.append(empty_item)

        # Add separator
        menu.append(Gtk.SeparatorMenuItem())

        # Toggle injection item
        self.toggle_item = Gtk.MenuItem()
        self.toggle_item.connect("activate", self._on_toggle_inject)
        menu.append(self.toggle_item)

        # Update toggle item label (suspend/resume)
        try:
            is_suspended = self.daemon.is_suspended()
        except Exception as e:
            logger.error("Failed to query suspended state: %s", e)
            is_suspended = True

        self.last_suspended = is_suspended
        self.last_states = current_states

        if is_suspended:
            self.toggle_item.set_label(_("Resume injection"))
        else:
            self.toggle_item.set_label(_("Suspend injection"))

        # Add separator
        menu.append(Gtk.SeparatorMenuItem())

        # Exit item
        exit_item = Gtk.MenuItem(label=_("Exit"))
        exit_item.connect("activate", self._on_exit_activate)
        menu.append(exit_item)

        menu.show_all()
        self.indicator.set_menu(menu)
        self.last_presets_mtimes = self._get_presets_mtimes()

    def _get_preset_names_for_group(self, group_name: str) -> list[str]:
        device_folder = PathUtils.get_preset_path(group_name)
        if not os.path.exists(device_folder):
            return []

        paths = glob.glob(os.path.join(glob.escape(device_folder), "*.json"))
        presets = [
            os.path.splitext(os.path.basename(path))[0]
            for path in sorted(paths, key=os.path.getmtime)
        ]
        presets.reverse()
        return presets

    def _poll_state(self) -> bool:
        if self.daemon is None:
            return True
        # Only reload config if file has actually been modified
        try:
            if os.path.exists(self.global_config.path):
                current_mtime = os.path.getmtime(self.global_config.path)
                if current_mtime != self.last_config_mtime:
                    self.last_config_mtime = current_mtime
                    self.global_config.load_config()
        except Exception as e:
            logger.error("Failed to check config file mtime: %s", e)

        if self.gui_spawned and not self.global_config.get_systray():
            logger.info("Systray disabled in config. Exiting tray helper.")
            Gtk.main_quit()
            return False

        try:
            is_suspended = self.daemon.is_suspended()
        except Exception:
            return True

        if is_suspended != self.last_suspended:
            self.rebuild_menu()
            return True

        # Check if any preset files/folders changed on disk
        presets_mtimes = self._get_presets_mtimes()
        if presets_mtimes != self.last_presets_mtimes:
            self.rebuild_menu()
            return True

        self.poll_count += 1
        if self.poll_count >= 5:
            self.poll_count = 0
            self._refresh_groups_async()
        else:
            self._check_device_states_only()

        return True

    def _refresh_groups_async(self) -> None:
        """Runs the silent groups refresh in a background thread to prevent UI micro-stutters."""
        if self.refresh_thread and self.refresh_thread.is_alive():
            return

        def run():
            with self.refresh_lock:
                self._refresh_groups_silently()
            GLib.idle_add(self._on_groups_refreshed)

        self.refresh_thread = threading.Thread(target=run, daemon=True)
        self.refresh_thread.start()

    def _on_groups_refreshed(self) -> bool:
        """Runs in the main GTK thread after groups.refresh() completes in background."""
        group_keys = [group.key for group in groups.get_groups()]

        if set(group_keys) != set(self.last_states.keys()):
            self.rebuild_menu()
            return False

        self._check_device_states_only()
        return False

    def _check_device_states_only(self) -> None:
        """Query state for all currently tracked groups and rebuild if any state changed."""
        if self.daemon is None:
            return
        group_keys = list(self.last_states.keys())
        for group_key in group_keys:
            try:
                state = self.daemon.get_state(group_key)
                running_preset = self.daemon.get_running_preset(group_key)
            except Exception:  # noqa: S112
                continue

            last = self.last_states.get(group_key)
            if not last or last != (state, running_preset):
                self.rebuild_menu()
                break

    def _get_presets_mtimes(self) -> dict[str, float]:
        """Compute modification times for presets folder and subfolders to detect adds/removes."""
        mtimes: dict[str, float] = {}
        base_dir = PathUtils.get_preset_path("")
        if not os.path.exists(base_dir):
            return mtimes

        try:
            mtimes[""] = os.path.getmtime(base_dir)
            for item in os.listdir(base_dir):
                sub_path = os.path.join(base_dir, item)
                if os.path.isdir(sub_path):
                    mtimes[item] = os.path.getmtime(sub_path)
        except Exception:  # noqa: S110
            pass
        return mtimes

    def _refresh_groups_silently(self) -> None:
        """Call groups.refresh() temporarily raising the log level to silence debug discovery prints."""
        import logging

        old_level = logger.level
        logger.setLevel(logging.WARNING)
        try:
            groups.refresh()
        finally:
            logger.setLevel(old_level)

    def _on_show_activate(self, _widget) -> None:
        if ProcessUtils.count_python_processes("input-remapper-gtk") > 0:
            logger.info("input-remapper-gtk is already running, not spawning a new one")
            return

        logger.info("Spawning input-remapper-gtk")
        subprocess.Popen(["input-remapper-gtk"])

    def _on_exit_activate(self, _widget) -> None:
        terminated = ProcessUtils.terminate_python_processes("input-remapper-gtk")
        if terminated:
            logger.info("Terminated %d running GUI process(es)", terminated)
        Gtk.main_quit()

    def _on_toggle_inject(self, _widget) -> None:
        if self.daemon is None:
            return
        try:
            is_suspended = self.daemon.is_suspended()
            self.daemon.set_suspended(not is_suspended)
            self.rebuild_menu()
        except Exception as e:
            logger.error("Failed to toggle global suspend state: %s", e)

    def _on_device_preset_toggle(
        self, widget: Gtk.CheckMenuItem, group_key: str, preset_name: str
    ) -> None:
        if self.daemon is None:
            return
        active = widget.get_active()
        if active:
            logger.info(
                "Starting injection of preset %s for device %s", preset_name, group_key
            )
            try:
                self.daemon.set_config_dir(self.global_config.get_dir())
                self.daemon.start_injecting(group_key, preset_name)
                self.rebuild_menu()
            except Exception as e:
                logger.error("Failed to start injection: %s", e)
        else:
            logger.info("Stopping injection for device %s", group_key)
            try:
                self.daemon.stop_injecting(group_key)
                self.rebuild_menu()
            except Exception as e:
                logger.error("Failed to stop injection: %s", e)
