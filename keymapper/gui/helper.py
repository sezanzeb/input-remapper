#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@hip70890b.de>
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


"""Process that sends stuff to the GUI.

It should be started via key-mapper-control and pkexec.

GUIs should not run as root
https://wiki.archlinux.org/index.php/Running_GUI_applications_as_root
"""


import sys
import select
import multiprocessing
import subprocess

import evdev
from evdev.ecodes import EV_KEY

from keymapper.ipc.pipe import Pipe
from keymapper.logger import logger
from keymapper.getdevices import get_devices
from keymapper import utils


TERMINATE = 'terminate'


def is_helper_running():
    """Check if the helper is running."""
    try:
        subprocess.check_output(['pgrep', '-f', 'key-mapper-helper'])
    except subprocess.CalledProcessError:
        return False
    return True


class RootHelper:
    """Client that runs as root and works for the GUI.

    Sends device information and keycodes to the GUIs socket.

    Commands are either numbers for generic commands,
    or strings to start listening on a specific device.
    """
    def __init__(self):
        """Construct the helper and initialize its sockets."""
        self._results = Pipe('/tmp/key-mapper/results')
        self._commands = Pipe('/tmp/key-mapper/commands')

        # the ui needs the devices first
        self._results.send({
            'type': 'devices',
            'message': get_devices()
        })

        self.device_name = None
        self._pipe = multiprocessing.Pipe()

    def run(self):
        """Start doing stuff. Blocks."""
        while True:
            self._handle_commands()
            self._start_reading()

    def _handle_commands(self):
        """Handle all unread commands."""
        # wait for something to do
        select.select([self._commands], [], [])

        while self._commands.poll():
            cmd = self._commands.recv()
            logger.debug('Received command "%s"', cmd)
            if cmd == TERMINATE:
                logger.debug('Helper terminates')
                sys.exit(0)
            elif cmd in get_devices():
                self.device_name = cmd
            else:
                logger.error('Received unknown command "%s"', cmd)

    def _start_reading(self):
        """Tell the evdev lib to start looking for keycodes.

        If read is called without prior start_reading, no keycodes
        will be available.

        This blocks forever until it discovers a new command on the socket.
        """
        device_name = self.device_name

        rlist = {}

        if device_name is None:
            logger.error('device_name is None')
            return

        group = get_devices()[device_name]
        virtual_devices = []
        # Watch over each one of the potentially multiple devices per
        # hardware
        for path in group['paths']:
            try:
                device = evdev.InputDevice(path)
            except FileNotFoundError:
                continue

            if evdev.ecodes.EV_KEY in device.capabilities():
                virtual_devices.append(device)

        if len(virtual_devices) == 0:
            logger.debug('No interesting device for "%s"', device_name)
            return

        for device in virtual_devices:
            rlist[device.fd] = device

        logger.debug(
            'Starting reading keycodes from "%s"',
            '", "'.join([device.name for device in virtual_devices])
        )

        rlist[self._commands] = self._commands

        while True:
            ready_fds = select.select(rlist, [], [])
            if len(ready_fds[0]) == 0:
                # whatever, happens for sockets sometimes. Maybe the socket
                # is closed and select has nothing to select from?
                continue

            for fd in ready_fds[0]:
                if rlist[fd] == self._commands:
                    # all commands will cause the reader to start over
                    # (possibly for a different device).
                    # _handle_commands will check what is going on
                    return

                device = rlist[fd]

                try:
                    event = device.read_one()
                    self._send_event(event, device)
                except OSError:
                    logger.debug('Device "%s" disappeared', device.path)
                    return

    def _send_event(self, event, device):
        """Write the event into the pipe to the main process.

        Parameters
        ----------
        event : evdev.InputEvent
        device : evdev.InputDevice
        """
        # value: 1 for down, 0 for up, 2 for hold.
        if event.type == EV_KEY and event.value == 2:
            # ignore hold-down events
            return

        click_events = [
            evdev.ecodes.BTN_LEFT,
            evdev.ecodes.BTN_TOOL_DOUBLETAP
        ]

        if event.type == EV_KEY and event.code in click_events:
            # disable mapping the left mouse button because it would break
            # the mouse. Also it is emitted right when focusing the row
            # which breaks the current workflow.
            return

        max_abs = utils.get_max_abs(device)
        event.value = utils.normalize_value(event, max_abs)

        self._results.send({
            'type': 'event',
            'message': (
                event.sec, event.usec,
                event.type, event.code, event.value
            )
        })
