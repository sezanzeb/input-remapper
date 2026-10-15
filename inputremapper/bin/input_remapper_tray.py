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

"""System tray helper process."""

from __future__ import annotations

import glob
import os
import subprocess
import sys
from argparse import ArgumentParser

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GLib", "2.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from dasbus.error import DBusError
from gi.repository import AyatanaAppIndicator3 as AppIndicator
from gi.repository import Gio, Gtk

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
    def __init__(
        self,
        global_config: GlobalConfig,
        gui_spawned: bool,
        check_autostart: bool,
    ) -> None:
        self.global_config = global_config
        self.check_autostart = check_autostart
        self.daemon: DaemonProxy | None = None
        self.indicator: AppIndicator.Indicator | None = None
        self.toggle_item: Gtk.MenuItem | None = None

        # Last known states to prevent redundant menu rebuilds
        self.last_suspended: bool | None = None
        self.config_monitor: Gio.FileMonitor | None = None
        self.presets_monitor: Gio.FileMonitor | None = None
        self.preset_subdir_monitors: dict[str, Gio.FileMonitor] = {}
        self.gui_spawned = gui_spawned

    @staticmethod
    def main() -> None:
        parser = ArgumentParser()
        parser.add_argument(
            "-d",
            "--debug",
            action="store_true",
            dest="debug",
            help="Displays additional debug information",
            default=False,
        )
        parser.add_argument(
            "--gui-spawned",
            action="store_true",
            dest="gui_spawned",
            help="The tray was spawned from the GUI",
            default=False,
        )
        parser.add_argument(
            "--check-autostart",
            action="store_true",
            dest="check_autostart",
            help="Exit if the system tray is disabled in the config",
            default=False,
        )
        options = parser.parse_args(sys.argv[1:])
        logger.update_verbosity(options.debug)
        global_config = GlobalConfig()
        tray = InputRemapperTrayBin(
            global_config,
            options.gui_spawned,
            options.check_autostart,
        )
        tray.run()

    def run(self) -> None:
        if ProcessUtils.count_python_processes("input-remapper-tray") >= 2:
            logger.info(
                "Another input-remapper tray helper is already running. Exiting."
            )
            sys.exit(0)

        # GlobalConfig() starts from defaults; make sure we act on the stored
        # values so a disabled (autostarted) tray exits quickly.
        self.global_config.load_config()
        if self.check_autostart and not self.global_config.is_systray():
            logger.info("System tray is disabled in config. Exiting.")
            sys.exit(0)

        self.daemon = Daemon.connect(fallback=False)
        if self.daemon is None:
            logger.error("Failed to connect to daemon")
            sys.exit(2)

        # Load the device groups once up front; afterwards the daemon's
        # groups_changed signal keeps them up to date.
        self._load_groups()

        self.show()
        self._subscribe_daemon_signals()
        self._setup_monitors()

        Gtk.main()

    def _subscribe_daemon_signals(self) -> None:
        """Subscribe to daemon signals to keep the menu in sync without polling."""
        if self.daemon is None:
            return
        self.daemon.suspended_changed.connect(self._on_suspended_changed)
        self.daemon.groups_changed.connect(self._on_groups_changed)
        self.daemon.state_changed.connect(self._on_state_changed)

    def _setup_monitors(self) -> None:
        """Watch config.json and the presets folder for changes."""
        config_file = Gio.File.new_for_path(self.global_config.path)
        self.config_monitor = config_file.monitor_file(Gio.FileMonitorFlags.NONE, None)
        self.config_monitor.connect("changed", self._on_config_changed)

        # inotify is not recursive, so watch the presets root (to detect device
        # subdirectories appearing/disappearing) and each device subdirectory
        # (to detect preset file changes inside them).
        self._sync_presets_monitors()

    def _sync_presets_monitors(self) -> None:
        """Attach monitors to the presets root and each device subdirectory."""
        presets_path = PathUtils.get_preset_path("")

        if self.presets_monitor is None:
            presets_dir = Gio.File.new_for_path(presets_path)
            self.presets_monitor = presets_dir.monitor_directory(
                Gio.FileMonitorFlags.WATCH_MOVES, None
            )
            self.presets_monitor.connect("changed", self._on_presets_dir_changed)

        # Match the per-device subdirectory monitors to what's on disk.
        if os.path.isdir(presets_path):
            subdirs = {
                name
                for name in os.listdir(presets_path)
                if os.path.isdir(os.path.join(presets_path, name))
            }
        else:
            subdirs = set()

        for name in list(self.preset_subdir_monitors):
            if name not in subdirs:
                self.preset_subdir_monitors.pop(name, None)

        for name in subdirs:
            if name not in self.preset_subdir_monitors:
                subdir = Gio.File.new_for_path(os.path.join(presets_path, name))
                monitor = subdir.monitor_directory(
                    Gio.FileMonitorFlags.WATCH_MOVES, None
                )
                monitor.connect("changed", self._on_presets_subdir_changed)
                self.preset_subdir_monitors[name] = monitor

    def _on_presets_dir_changed(
        self,
        _monitor: Gio.FileMonitor,
        _file: Gio.File,
        _other_file: Gio.File | None,
        _event: Gio.FileMonitorEvent,
    ) -> None:
        """A device subdirectory was added/removed/renamed; re-sync and rebuild."""
        self._sync_presets_monitors()
        self.rebuild_menu()

    def _on_presets_subdir_changed(
        self,
        _monitor: Gio.FileMonitor,
        _file: Gio.File,
        _other_file: Gio.File | None,
        _event: Gio.FileMonitorEvent,
    ) -> None:
        """A preset file inside a device subdirectory changed; rebuild the menu."""
        self.rebuild_menu()

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
        group_keys = [group.key for group in groups.get_groups()]

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

    def _on_suspended_changed(self, suspended: bool) -> None:
        """Update the menu when the daemon reports a suspend state change."""
        if suspended != self.last_suspended:
            self.last_suspended = suspended
            self.rebuild_menu()

    def _on_groups_changed(self, groups_dump: str) -> None:
        """Update the device list when the daemon reports new groups."""
        try:
            groups.loads(groups_dump)
        except ValueError:
            logger.error("Failed to process groups_changed signal")
            return
        self.rebuild_menu()

    def _on_state_changed(self, _group_key: str) -> None:
        """Rebuild the menu when injection starts or stops elsewhere."""
        self.rebuild_menu()

    def _on_config_changed(
        self,
        _monitor: Gio.FileMonitor,
        _file: Gio.File,
        _other_file: Gio.File | None,
        _event: Gio.FileMonitorEvent,
    ) -> None:
        """Reload config, exiting the tray if autostarted and now disabled."""
        self.global_config.load_config()
        if self.check_autostart and not self.global_config.is_systray():
            logger.info("System tray disabled in config. Exiting.")
            Gtk.main_quit()

    def _load_groups(self) -> None:
        """Fetch the device groups from the daemon and load them locally."""
        if self.daemon is None:
            return
        try:
            groups.loads(self.daemon.get_groups())
        except DBusError as e:
            logger.error("Failed to fetch device groups: %s", e)

    def _on_show_activate(self, _widget) -> None:
        if ProcessUtils.count_python_processes("input-remapper-gtk") > 0:
            logger.info("input-remapper-gtk is already running, not spawning a new one")
            return

        logger.info("Spawning input-remapper-gtk")
        args = ["input-remapper-gtk"]
        if logger.is_debug():
            args.append("-d")
        subprocess.Popen(args)

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
        except DBusError as e:
            logger.error("Failed to toggle global suspend state: %s", e)
            self._notify(_("Failed to toggle global suspend state"))

    def _notify(self, message: str) -> None:
        """Show a desktop notification, if possible."""
        try:
            subprocess.Popen(["notify-send", "input-remapper", message])
        except OSError as e:
            logger.error("Failed to show notification: %s", e)

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
                started = self.daemon.start_injecting(group_key, preset_name)
                self.rebuild_menu()
                if not started:
                    logger.error("Failed to start injection for device %s", group_key)
                    self._notify(_("Failed to start injection"))
            except DBusError as e:
                logger.error("Failed to start injection: %s", e)
                self._notify(_("Failed to start injection"))
        else:
            logger.info("Stopping injection for device %s", group_key)
            try:
                self.daemon.stop_injecting(group_key)
                self.rebuild_menu()
            except DBusError as e:
                logger.error("Failed to stop injection: %s", e)
                self._notify(_("Failed to stop injection"))
