#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2020 sezanzeb <proxima@hip70890b.de>
#
# This file is part of key-mapper.
#
# key-mapper is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# key-mapper is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with key-mapper.  If not, see <https://www.gnu.org/licenses/>.


"""Starts injecting keycodes based on the configuration."""


import subprocess

# TODO https://www.freedesktop.org/wiki/Software/DBusBindings/#python
#  says "New applications should use pydbus"
import dbus
from dbus import service
import dbus.mainloop.glib

from keymapper.logger import logger
from keymapper.dev.injector import KeycodeInjector
from keymapper.mapping import Mapping
from keymapper.config import config


def is_service_running():
    """Check if the daemon is running."""
    try:
        subprocess.check_output(['pgrep', '-f', 'key-mapper-service'])
    except subprocess.CalledProcessError:
        return False
    return True


def get_dbus_interface():
    """Get an interface to start and stop injecting keystrokes."""
    if not is_service_running():
        logger.warning(
            'The daemon "key-mapper-service" is not running, mapping keys '
            'only works as long as the window is open.'
        )
        return Daemon(autoload=False)

    try:
        bus = dbus.SessionBus()
        remote_object = bus.get_object('keymapper.Control', '/')
        interface = dbus.Interface(remote_object, 'keymapper.Interface')
        logger.debug('Connected to dbus')
    except dbus.exceptions.DBusException as error:
        logger.warning(
            'Could not connect to the dbus of "key-mapper-service", mapping '
            'keys only works as long as the window is open.'
        )
        logger.debug(error)
        return Daemon(autoload=False)

    return interface


class Daemon(service.Object):
    """Starts injecting keycodes based on the configuration.

    Can be talked to either over dbus or by instantiating it.

    The Daemon may not have any knowledge about the logged in user, so it
    can't read any config files. It has to be told what to do and will
    continue to do so afterwards, but it can't decide to start injecting
    on its own.
    """
    def __init__(self, *args, autoload=True, **kwargs):
        """Constructs the daemon. You still need to run the GLib mainloop."""
        self.injectors = {}
        if autoload:
            for device, preset in config.iterate_autoload_presets():
                mapping = Mapping()
                mapping.load(device, preset)
                try:
                    injector = KeycodeInjector(device, mapping)
                    injector.start_injecting()
                    self.injectors[device] = injector
                except OSError as error:
                    logger.error(error)
        super().__init__(*args, **kwargs)

    @dbus.service.method('keymapper.Interface', in_signature='s')
    def stop_injecting(self, device):
        """Stop injecting the mapping for a single device."""
        if self.injectors.get(device) is None:
            logger.error(
                'Tried to stop injector, but none is running for device "%s"',
                device
            )
            return

        self.injectors[device].stop_injecting()

    # TODO if ss is the correct signature for multiple parameters, add an
    #  example to https://gitlab.freedesktop.org/dbus/dbus-python/-/blob/master/doc/tutorial.txt # noqa pylint: disable=line-too-long
    @dbus.service.method('keymapper.Interface', in_signature='ss')
    def start_injecting(self, device, preset):
        """Start injecting the preset for the device.

        Returns True on success.

        Parameters
        ----------
        device : string
            The name of the device
        preset : string
            The name of the preset
        """
        # reload the config, since it may have been changed
        config.load_config()
        if self.injectors.get(device) is not None:
            self.injectors[device].stop_injecting()

        mapping = Mapping()
        mapping.load(device, preset)
        try:
            injector = KeycodeInjector(device, mapping)
            injector.start_injecting()
            self.injectors[device] = injector
        except OSError:
            return False

        return True

    @dbus.service.method('keymapper.Interface')
    def stop(self):
        """Stop all mapping injections."""
        for injector in self.injectors.values():
            injector.stop_injecting()
