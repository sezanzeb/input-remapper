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
import asyncio
import signal
import json
import os
import sys
import time
import tracemalloc
import typing
from pathlib import PurePath
from typing import Protocol, Dict, Optional

from dbus_next.aio import MessageBus
from dbus_next import BusType, service, RequestNameReply
from pydbus import SystemBus

import gi

gi.require_version("GLib", "2.0")
from gi.repository import GLib

from inputremapper.logger import logger, is_debug
from inputremapper.injection.injector import Injector, InjectorState
from inputremapper.configs.preset import Preset
from inputremapper.configs.global_config import global_config
from inputremapper.configs.system_mapping import system_mapping
from inputremapper.groups import groups
from inputremapper.configs.paths import get_config_path, sanitize_path_component, USER
from inputremapper.injection.global_uinputs import global_uinputs

tracemalloc.start()

BUS_NAME = "inputremapper.Control"
PATH_NAME = "/inputremapper/Control"
INTERFACE_NAME = "inputremapper.Control"

# timeout in seconds, see
# https://github.com/LEW21/pydbus/blob/cc407c8b1d25b7e28a6d661a29f9e661b1c9b964/pydbus/proxy.py
BUS_TIMEOUT = 10


class AutoloadHistory:
    """Contains the autoloading history and constraints."""

    def __init__(self):
        """Construct this with an empty history."""
        # preset of device -> (timestamp, preset)
        self._autoload_history = {}

    def remember(self, group_key: str, preset: str):
        """Remember when this preset was autoloaded for the device."""
        self._autoload_history[group_key] = (time.time(), preset)

    def forget(self, group_key: str):
        """The injection was stopped or started by hand."""
        if group_key in self._autoload_history:
            del self._autoload_history[group_key]

    def may_autoload(self, group_key: str, preset: str):
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


class DaemonProxy(Protocol):  # pragma: no cover
    """The interface provided over the dbus."""

    def stop_injecting(self, group_key: str) -> None:
        ...

    def get_state(self, group_key: str) -> InjectorState:
        ...

    def start_injecting(self, group_key: str, preset: str) -> bool:
        ...

    def stop_all(self) -> None:
        ...

    def set_config_dir(self, config_dir: str) -> None:
        ...

    def autoload(self) -> None:
        ...

    def autoload_single(self, group_key: str) -> None:
        ...

    def hello(self, out: str) -> str:
        ...


def method(name: str = None, disabled: bool = False):
    # this is a workaround for https://github.com/altdesktop/python-dbus-next/issues/119
    @typing.no_type_check_decorator
    def fixed_decorator(fn):
        # we don't actually decorate the function
        # dbus-next only cares about the __dict__
        fn.__dict__ = service.method(name, disabled)(fn).__dict__
        return fn

    return fixed_decorator


class Daemon(service.ServiceInterface):
    """Starts injecting keycodes based on the configuration.

    Can be talked to either over dbus or by instantiating it.

    The Daemon may not have any knowledge about the logged in user, so it
    can't read any config files. It has to be told what to do and will
    continue to do so afterwards, but it can't decide to start injecting
    on its own.
    """

    def __init__(self):
        """Constructs the daemon."""
        logger.debug("Creating daemon")
        super().__init__(INTERFACE_NAME)
        self.injectors: Dict[str, Injector] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._bus: Optional[MessageBus] = None

        self.config_dir = None

        if USER != "root":
            self.set_config_dir(get_config_path())

        # check privileges
        if os.getuid() != 0:
            logger.warning("The service usually needs elevated privileges")

        self.autoload_history = AutoloadHistory()
        self.refreshed_devices_at = 0

        signal.signal(signal.SIGINT, self.quit)

    @classmethod
    def connect(cls, fallback: bool = True) -> DaemonProxy:
        """Get an interface to start and stop injecting keystrokes.

        Parameters
        ----------
        fallback
            If true, starts the daemon via pkexec if it cannot connect.
        """
        bus = SystemBus()
        try:
            interface = bus.get(BUS_NAME, timeout=BUS_TIMEOUT)
            logger.info("Connected to the service")
        except GLib.Error as error:
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
                except GLib.Error as error:
                    logger.debug("Attempt %d to reach the service failed:", attempt + 1)
                    logger.debug('"%s"', error)
                time.sleep(0.2)
            else:
                logger.error("Failed to connect to the service")
                sys.exit(8)

        if USER != "root":
            config_path = get_config_path()
            logger.debug('Telling service about "%s"', config_path)
            interface.set_config_dir(get_config_path())

        return interface

    def run(self):
        """Start the event loop and publish the daemon.
        Blocks until the daemon stops."""
        self._loop = loop = asyncio.get_event_loop()

        async def task():
            self._bus = bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
            bus.export(path=PATH_NAME, interface=self)
            if RequestNameReply.PRIMARY_OWNER != await bus.request_name(BUS_NAME):
                logger.error("Is the service already running?")
                sys.exit(9)

        loop.run_until_complete(task())
        logger.debug("Running daemon")
        loop.run_forever()

    def quit(self, *_):
        self.stop_all()
        self._bus.unexport(path=PATH_NAME, interface=self)

        async def stop_later():
            # give all injections time to reset uinputs
            await asyncio.sleep(0.2)

            # loop.run_forever will return
            self._loop.stop()

        asyncio.ensure_future(stop_later())

    async def refresh(self, group_key: Optional[str] = None):
        """Refresh groups if the specified group is unknown.

        Parameters
        ----------
        group_key
            unique identifier used by the groups object
        """
        now = time.time()
        if now - 10 > self.refreshed_devices_at:
            logger.debug("Refreshing because last info is too old")
            # it may take a little bit of time until devices are visible after
            # changes
            await asyncio.sleep(0.1)
            groups.refresh()
            self.refreshed_devices_at = now
            return

        if not groups.find(key=group_key):
            logger.debug('Refreshing because "%s" is unknown', group_key)
            await asyncio.sleep(0.1)
            groups.refresh()
            self.refreshed_devices_at = now

    @method()
    def stop_injecting(self, group_key: "s"):
        """Stop injecting the preset mappings for a single device."""
        if self.injectors.get(group_key) is None:
            logger.debug(
                'Tried to stop injector, but none is running for group "%s"',
                group_key,
            )
            return

        self.injectors[group_key].stop_injecting()
        self.autoload_history.forget(group_key)

    @method()
    def get_state(self, group_key: "s") -> "s":
        """Get the injectors state."""
        injector = self.injectors.get(group_key)
        return injector.get_state() if injector else InjectorState.UNKNOWN

    @method()
    def set_config_dir(self, config_dir: "s"):
        """All future operations will use this config dir.

        Existing injections (possibly of the previous user) will be kept
        alive, call stop_all to stop them.

        Parameters
        ----------
        config_dir
            This path contains config.json, xmodmap.json and the
            presets directory
        """
        config_path = PurePath(config_dir, "config.json")
        if not os.path.exists(config_path):
            logger.error('"%s" does not exist', config_path)
            return

        self.config_dir = config_dir
        global_config.load_config(config_path)

    async def _autoload(self, group_key: str):
        """Check if autoloading is a good idea, and if so do it.

        Parameters
        ----------
        group_key
            unique identifier used by the groups object
        """
        await self.refresh(group_key)

        group = groups.find(key=group_key)
        if group is None:
            # even after groups.refresh, the device is unknown, so it's
            # either not relevant for input-remapper, or not connected yet
            return

        preset = global_config.get(["autoload", group.key], log_unknown=False)

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

        await self.start_injecting(group.key, preset)
        self.autoload_history.remember(group.key, preset)

    @method()
    async def autoload_single(self, group_key: "s"):
        """Inject the configured autoload preset for the device.

        If the preset is already being injected, it won't autoload it again.

        Parameters
        ----------
        group_key
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

        await self._autoload(group_key)

    @method()
    async def autoload(self):
        """Load all autoloaded presets for the current config_dir.

        If the preset is already being injected, it won't autoload it again.
        """
        if self.config_dir is None:
            logger.error(
                "Request to autoload all before a user told the service about their "
                "session using set_config_dir",
            )
            return

        autoload_presets = list(global_config.iterate_autoload_presets())

        logger.info("Autoloading for all devices")

        if len(autoload_presets) == 0:
            logger.error("No presets configured to autoload")
            return

        for group_key, _ in autoload_presets:
            await self._autoload(group_key)

    @method()
    async def start_injecting(self, group_key: "s", preset: "s") -> "b":
        """Start injecting the preset for the device.

        Returns True on success. If an injection is already ongoing for
        the specified device it will stop it automatically first.

        Parameters
        ----------
        group_key
            The unique key of the group
        preset
            The name of the preset
        """
        logger.info('Request to start injecting for "%s"', group_key)

        await self.refresh(group_key)

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

        preset_path = PurePath(
            self.config_dir,
            "presets",
            sanitize_path_component(group.name),
            f"{preset}.json",
        )

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

                # this creates the system_mapping._xmodmap, which we need to do now
                # otherwise it might be created later which will override the changes
                # we do here.
                # Do we really need to lazyload in the system_mapping?
                # this kind of bug is stupid to track down
                system_mapping.get_name(0)
                system_mapping.update(xmodmap)
                # the service now has process wide knowledge of xmodmap
                # keys of the users session
        except FileNotFoundError:
            logger.error('Could not find "%s"', xmodmap_path)

        preset = Preset(preset_path)

        try:
            preset.load()
        except FileNotFoundError as error:
            logger.error(str(error))
            return False

        for mapping in preset:
            # only create those uinputs that are required to avoid
            # confusing the system. Seems to be especially important with
            # gamepads, because some apps treat the first gamepad they found
            # as the only gamepad they'll ever care about.
            global_uinputs.prepare_single(mapping.target_uinput)

        if self.injectors.get(group_key) is not None:
            self.stop_injecting(group_key)

        try:
            injector = Injector(group, preset)
            asyncio.create_task(injector.run())
            self.injectors[group.key] = injector
        except OSError:
            # I think this will never happen, probably leftover from
            # some earlier version
            return False

        return True

    @method()
    def stop_all(self):
        """Stop all injections."""
        logger.info("Stopping all injections")
        for group_key in list(self.injectors.keys()):
            self.stop_injecting(group_key)

    @method()
    def hello(self, out: "s") -> "s":
        """Used for tests."""
        logger.info('Received "%s" from client', out)
        return out
