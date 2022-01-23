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


"""Starts injecting keycodes based on the configuration.

https://github.com/LEW21/pydbus/tree/cc407c8b1d25b7e28a6d661a29f9e661b1c9b964/examples/clientserver  # noqa pylint: disable=line-too-long
"""


import os
import sys
import json
import time
import atexit

from pydbus import SystemBus
import gi

gi.require_version("GLib", "2.0")
from gi.repository import GLib

from inputremapper.logger import logger, is_debug
from inputremapper.injection.injector import Injector, UNKNOWN
from inputremapper.preset import Preset
from inputremapper.config import config
from inputremapper.system_mapping import system_mapping
from inputremapper.groups import groups
from inputremapper.paths import get_config_path, USER
from inputremapper.injection.macros.macro import macro_variables
from inputremapper.injection.global_uinputs import global_uinputs


BUS_NAME = "inputremapper.Control"
# timeout in seconds, see
# https://github.com/LEW21/pydbus/blob/cc407c8b1d25b7e28a6d661a29f9e661b1c9b964/pydbus/proxy.py
BUS_TIMEOUT = 10


class AutoloadHistory:
    """Contains the autoloading history and constraints."""

    def __init__(self):
        """Construct this with an empty history."""
        # mapping of device -> (timestamp, preset)
        self._autoload_history = {}

    def remember(self, group_key, preset):
        """Remember when this preset was autoloaded for the device."""
        self._autoload_history[group_key] = (time.time(), preset)

    def forget(self, group_key):
        """The injection was stopped or started by hand."""
        if group_key in self._autoload_history:
            del self._autoload_history[group_key]

    def may_autoload(self, group_key, preset):
        """Check if this autoload would be redundant.

        This is needed because udev triggers multiple times per hardware
        device, and because it should be possible to stop the injection
        by unplugging the device if the preset goes wrong or if input-remapper
        has some bug that prevents the computer from being controlled.

        For that unplug and reconnect the device twice within a 15 seconds
        timeframe which will then not ask for autoloading again. Wait 3
        seconds between replugging.
        """
        if group_key not in self._autoload_history:
            return True

        if self._autoload_history[group_key][1] != preset:
            return True

        # bluetooth devices go to standby mode after some time. After a
        # certain time of being disconnected it should be legit to autoload
        # again. It takes 2.5 seconds for me when quickly replugging my usb
        # mouse until the daemon is asked to autoload again. Redundant calls
        # by udev to autoload for the device seem to happen within 0.2
        # seconds in my case.
        now = time.time()
        threshold = 15  # seconds
        if self._autoload_history[group_key][0] < now - threshold:
            return True

        return False


def remove_timeout(func):
    """Remove timeout to ensure the call works if the daemon is not a proxy."""
    # the timeout kwarg is a feature of pydbus. This is needed to make tests work
    # that create a Daemon by calling its constructor instead of using pydbus.
    def wrapped(*args, **kwargs):
        if "timeout" in kwargs:
            del kwargs["timeout"]

        return func(*args, **kwargs)

    return wrapped


class Daemon:
    """Starts injecting keycodes based on the configuration.

    Can be talked to either over dbus or by instantiating it.

    The Daemon may not have any knowledge about the logged in user, so it
    can't read any config files. It has to be told what to do and will
    continue to do so afterwards, but it can't decide to start injecting
    on its own.
    """

    # https://dbus.freedesktop.org/doc/dbus-specification.html#type-system
    dbus = f"""
        <node>
            <interface name='{BUS_NAME}'>
                <method name='stop_injecting'>
                    <arg type='s' name='group_key' direction='in'/>
                </method>
                <method name='get_state'>
                    <arg type='s' name='group_key' direction='in'/>
                    <arg type='i' name='response' direction='out'/>
                </method>
                <method name='start_injecting'>
                    <arg type='s' name='group_key' direction='in'/>
                    <arg type='s' name='preset' direction='in'/>
                    <arg type='b' name='response' direction='out'/>
                </method>
                <method name='stop_all'>
                </method>
                <method name='set_config_dir'>
                    <arg type='s' name='config_dir' direction='in'/>
                </method>
                <method name='autoload'>
                </method>
                <method name='autoload_single'>
                    <arg type='s' name='group_key' direction='in'/>
                </method>
                <method name='hello'>
                    <arg type='s' name='out' direction='in'/>
                    <arg type='s' name='response' direction='out'/>
                </method>
            </interface>
        </node>
    """

    def __init__(self):
        """Constructs the daemon."""
        logger.debug("Creating daemon")
        self.injectors = {}

        self.config_dir = None

        if USER != "root":
            self.set_config_dir(get_config_path())

        # check privileges
        if os.getuid() != 0:
            logger.warning("The service usually needs elevated privileges")

        self.autoload_history = AutoloadHistory()
        self.refreshed_devices_at = 0

        atexit.register(self.stop_all)

        # initialize stuff that is needed alongside the daemon process
        macro_variables.start()

        global_uinputs.prepare()

    @classmethod
    def connect(cls, fallback=True):
        """Get an interface to start and stop injecting keystrokes.

        Parameters
        ----------
        fallback : bool
            If true, returns an instance of the daemon instead if it cannot
            connect
        """
        try:
            bus = SystemBus()
            interface = bus.get(BUS_NAME, timeout=BUS_TIMEOUT)
            logger.info("Connected to the service")
        except GLib.GError as error:
            if not fallback:
                logger.error("Service not running? %s", error)
                return None

            logger.info("Starting the service")
            # Blocks until pkexec is done asking for the password.
            # Runs via input-remapper-control so that auth_admin_keep works
            # for all pkexec calls of the gui
            debug = " -d" if is_debug() else ""
            cmd = f"pkexec input-remapper-control --command start-daemon {debug}"

            # using pkexec will also cause the service to continue running in
            # the background after the gui has been closed, which will keep
            # the injections ongoing

            logger.debug("Running `%s`", cmd)
            os.system(cmd)
            time.sleep(0.2)

            # try a few times if the service was just started
            for attempt in range(3):
                try:
                    interface = bus.get(BUS_NAME, timeout=BUS_TIMEOUT)
                    break
                except GLib.GError as error:
                    logger.debug("Attempt %d to reach the service failed:", attempt + 1)
                    logger.debug('"%s"', error)
                time.sleep(0.2)
            else:
                logger.error("Failed to connect to the service")
                sys.exit(1)

        if USER != "root":
            config_path = get_config_path()
            logger.debug('Telling service about "%s"', config_path)
            interface.set_config_dir(get_config_path(), timeout=2)

        return interface

    def publish(self):
        """Make the dbus interface available."""
        bus = SystemBus()
        try:
            bus.publish(BUS_NAME, self)
        except RuntimeError as error:
            logger.error("Is the service already running? (%s)", str(error))
            sys.exit(1)

    def run(self):
        """Start the daemons loop. Blocks until the daemon stops."""
        loop = GLib.MainLoop()
        logger.debug("Running daemon")
        loop.run()

    def refresh(self, group_key=None):
        """Refresh groups if the specified group is unknown.

        Parameters
        ----------
        group_key : str
            unique identifier used by the groups object
        """
        now = time.time()
        if now - 10 > self.refreshed_devices_at:
            logger.debug("Refreshing because last info is too old")
            # it may take a little bit of time until devices are visible after
            # changes
            time.sleep(0.1)
            groups.refresh()
            self.refreshed_devices_at = now
            return

        if not groups.find(key=group_key):
            logger.debug('Refreshing because "%s" is unknown', group_key)
            time.sleep(0.1)
            groups.refresh()
            self.refreshed_devices_at = now

    def stop_injecting(self, group_key):
        """Stop injecting the mapping for a single device."""
        if self.injectors.get(group_key) is None:
            logger.debug(
                'Tried to stop injector, but none is running for group "%s"', group_key
            )
            return

        self.injectors[group_key].stop_injecting()
        self.autoload_history.forget(group_key)

    def get_state(self, group_key):
        """Get the injectors state."""
        injector = self.injectors.get(group_key)
        return injector.get_state() if injector else UNKNOWN

    @remove_timeout
    def set_config_dir(self, config_dir):
        """All future operations will use this config dir.

        Existing injections (possibly of the previous user) will be kept
        alive, call stop_all to stop them.

        Parameters
        ----------
        config_dir : string
            This path contains config.json, xmodmap.json and the
            presets directory
        """
        config_path = os.path.join(config_dir, "config.json")
        if not os.path.exists(config_path):
            logger.error('"%s" does not exist', config_path)
            return

        self.config_dir = config_dir
        config.load_config(config_path)

    def _autoload(self, group_key):
        """Check if autoloading is a good idea, and if so do it.

        Parameters
        ----------
        group_key : str
            unique identifier used by the groups object
        """
        self.refresh(group_key)

        group = groups.find(key=group_key)
        if group is None:
            # even after groups.refresh, the device is unknown, so it's
            # either not relevant for input-remapper, or not connected yet
            return

        preset = config.get(["autoload", group.key], log_unknown=False)

        if preset is None:
            # no autoloading is configured for this device
            return

        if not isinstance(preset, str):
            # maybe another dict or something, who knows. Broken config
            logger.error("Expected a string for autoload, but got %s", preset)
            return

        logger.info('Autoloading for "%s"', group.key)

        if not self.autoload_history.may_autoload(group.key, preset):
            logger.info(
                'Not autoloading the same preset "%s" again for group "%s"',
                preset,
                group.key,
            )
            return

        self.start_injecting(group.key, preset)
        self.autoload_history.remember(group.key, preset)

    @remove_timeout
    def autoload_single(self, group_key):
        """Inject the configured autoload preset for the device.

        If the preset is already being injected, it won't autoload it again.

        Parameters
        ----------
        group_key : str
            unique identifier used by the groups object
        """
        # avoid some confusing logs and filter obviously invalid requests
        if group_key.startswith("input-remapper"):
            return

        logger.info('Request to autoload for "%s"', group_key)

        if self.config_dir is None:
            logger.error(
                'Request to autoload "%s" before a user told the service about their '
                "session using set_config_dir",
                group_key,
            )
            return

        self._autoload(group_key)

    @remove_timeout
    def autoload(self):
        """Load all autoloaded presets for the current config_dir.

        If the preset is already being injected, it won't autoload it again.
        """
        if self.config_dir is None:
            logger.error(
                "Request to autoload all before a user told the service about their "
                "session using set_config_dir",
            )
            return

        autoload_presets = list(config.iterate_autoload_presets())

        logger.info("Autoloading for all devices")

        if len(autoload_presets) == 0:
            logger.error("No presets configured to autoload")
            return

        for group_key, _ in autoload_presets:
            self._autoload(group_key)

    def start_injecting(self, group_key, preset):
        """Start injecting the preset for the device.

        Returns True on success. If an injection is already ongoing for
        the specified device it will stop it automatically first.

        Parameters
        ----------
        group_key : string
            The unique key of the group
        preset : string
            The name of the preset
        """
        self.refresh(group_key)

        if self.config_dir is None:
            logger.error(
                "Request to start an injectoin before a user told the service about "
                "their session using set_config_dir",
            )
            return False

        group = groups.find(key=group_key)

        if group is None:
            logger.error('Could not find group "%s"', group_key)
            return False

        preset_path = os.path.join(
            self.config_dir, "presets", group.name, f"{preset}.json"
        )

        preset = Preset()
        try:
            preset.load(preset_path)
        except FileNotFoundError as error:
            logger.error(str(error))
            return False

        if self.injectors.get(group_key) is not None:
            self.stop_injecting(group_key)

        # Path to a dump of the xkb mappings, to provide more human
        # readable keys in the correct keyboard layout to the service.
        # The service cannot use `xmodmap -pke` because it's running via
        # systemd.
        xmodmap_path = os.path.join(self.config_dir, "xmodmap.json")
        try:
            with open(xmodmap_path, "r") as file:
                # do this for each injection to make sure it is up to
                # date when the system layout changes.
                xmodmap = json.load(file)
                logger.debug('Using keycodes from "%s"', xmodmap_path)
                system_mapping.update(xmodmap)
                # the service now has process wide knowledge of xmodmap
                # keys of the users session
        except FileNotFoundError:
            logger.error('Could not find "%s"', xmodmap_path)

        try:
            injector = Injector(group, preset)
            injector.start()
            self.injectors[group.key] = injector
        except OSError:
            # I think this will never happen, probably leftover from
            # some earlier version
            return False

        return True

    def stop_all(self):
        """Stop all injections."""
        logger.info("Stopping all injections")
        for group_key in list(self.injectors.keys()):
            self.stop_injecting(group_key)

    def hello(self, out):
        """Used for tests."""
        logger.info('Received "%s" from client', out)
        return out
