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


"""Starts injecting keycodes based on the configuration.

https://github.com/LEW21/pydbus/tree/cc407c8b1d25b7e28a6d661a29f9e661b1c9b964/examples/clientserver  # noqa pylint: disable=line-too-long
"""


import subprocess

from pydbus import SessionBus

from keymapper.logger import logger
from keymapper.dev.injector import KeycodeInjector
from keymapper.mapping import Mapping
from keymapper.config import config


BUS_NAME = 'keymapper.Control'


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

    bus = SessionBus()
    interface = bus.get(BUS_NAME)

    return interface


class Daemon:
    """Starts injecting keycodes based on the configuration.

    Can be talked to either over dbus or by instantiating it.

    The Daemon may not have any knowledge about the logged in user, so it
    can't read any config files. It has to be told what to do and will
    continue to do so afterwards, but it can't decide to start injecting
    on its own.
    """

    dbus = f"""
        <node>
            <interface name='{BUS_NAME}'>
                <method name='stop_injecting'>
                    <arg type='s' name='device' direction='in'/>
                </method>
                <method name='is_injecting'>
                    <arg type='s' name='device' direction='in'/>
                    <arg type='b' name='response' direction='out'/>
                </method>
                <method name='start_injecting'>
                    <arg type='s' name='device' direction='in'/>
                    <arg type='s' name='preset' direction='in'/>
                    <arg type='b' name='response' direction='out'/>
                </method>
                <method name='stop'>
                    <arg type='b' name='terminate' direction='in'/>
                </method>
                <method name='hello'>
                    <arg type='s' name='out' direction='in'/>
                    <arg type='s' name='response' direction='out'/>
                </method>
            </interface>
        </node>
    """

    def __init__(self, autoload=True, loop=None):
        """Constructs the daemon. You still need to run the GLib mainloop."""
        logger.debug('Creating daemon')
        self.injectors = {}
        self.loop = loop
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

    def stop_injecting(self, device):
        """Stop injecting the mapping for a single device."""
        if self.injectors.get(device) is None:
            logger.error(
                'Tried to stop injector, but none is running for device "%s"',
                device
            )
            return

        self.injectors[device].stop_injecting()
        del self.injectors[device]

    def is_injecting(self, device):
        """Is this device being mapped?"""
        return device in self.injectors

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

    def stop(self, terminate=False):
        """Stop all injections and end the service.

        Raises dbus.exceptions.DBusException in your main process.
        """
        for injector in self.injectors.values():
            injector.stop_injecting()

        if terminate and self.loop:
            logger.debug('Daemon stops')
            self.loop.quit()

    def hello(self, out):
        """Used for tests."""
        return out
