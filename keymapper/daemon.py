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

from dbus import service
import dbus.mainloop.glib

from keymapper.logger import logger
from keymapper.config import config
from keymapper.injector import KeycodeInjector
from keymapper.mapping import Mapping


# TODO service file in data for a root daemon


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

    logger.debug('Found the daemon process')
    bus = dbus.SessionBus()
    remote_object = bus.get_object('com.keymapper.Control', '/')
    interface = dbus.Interface(remote_object, 'com.keymapper.Interface')
    logger.debug('Connected to dbus')
    return interface


class Daemon(service.Object):
    """Starts injecting keycodes based on the configuration.

    Can be talked to either over dbus or by instantiating it.
    """
    def __init__(self, *args, autoload=True, **kwargs):
        """Constructs the daemon. You still need to run the GLib mainloop."""
        self.injectors = {}
        if autoload:
            for device, preset in config.iterate_autoload_presets():
                mapping = Mapping()
                mapping.load(device, preset)
                self.injectors[device] = KeycodeInjector(device, mapping)

        super().__init__(*args, **kwargs)

    @dbus.service.method(
        'com.keymapper.Interface',
        in_signature='s'
    )
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
    @dbus.service.method(
        'com.keymapper.Interface',
        in_signature='ss'
    )
    def start_injecting(self, device, preset):
        """Start injecting the preset for the device.

        Returns True on success.
        """
        if self.injectors.get(device) is not None:
            self.injectors[device].stop_injecting()

        mapping = Mapping()
        mapping.load(device, preset)
        try:
            self.injectors[device] = KeycodeInjector(device, mapping)
        except OSError:
            return False

        return True

    @dbus.service.method(
        'com.keymapper.Interface'
    )
    def stop(self):
        """Properly stop the daemon."""
        for injector in self.injectors.values():
            injector.stop_injecting()
