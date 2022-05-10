#!/usr/bin/python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2022 sezanzeb <proxima@hip70890b.de>
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


"""Process that sends stuff to the GUI.

It should be started via input-remapper-control and pkexec.

GUIs should not run as root
https://wiki.archlinux.org/index.php/Running_GUI_applications_as_root

The service shouldn't do that even though it has root rights, because that
would provide a key-logger that can be accessed by any user at all times,
whereas for the helper to start a password is needed and it stops when the ui
closes.
"""


import sys
import select
import multiprocessing
import subprocess
import time

import evdev
from evdev.ecodes import EV_KEY, EV_ABS

from inputremapper.ipc.pipe import Pipe
from inputremapper.logger import logger
from inputremapper.groups import groups
from inputremapper import utils
from inputremapper.user import USER


# received by the helper
CMD_TERMINATE = "terminate"
CMD_REFRESH_GROUPS = "refresh_groups"

# sent by the helper to the reader
MSG_GROUPS = "groups"
MSG_EVENT = "event"


def is_helper_running():
    """Check if the helper is running."""
    try:
        subprocess.check_output(["pgrep", "-f", "input-remapper-helper"])
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
        self._results = Pipe(f"/tmp/input-remapper-{USER}/results")
        self._commands = Pipe(f"/tmp/input-remapper-{USER}/commands")

        self._send_groups()

        self.group = None
        self._pipe = multiprocessing.Pipe()

    def run(self):
        """Start doing stuff. Blocks."""
        logger.debug("Waiting for the first command")
        # the reader will check for new commands later, once it is running
        # it keeps running for one device or another.
        select.select([self._commands], [], [])

        # possibly an alternative to select:
        """while True:
            if self._commands.poll():
                break

            time.sleep(0.1)"""

        logger.debug("Starting mainloop")
        while True:
            self._read_commands()
            self._start_reading()

    def _send_groups(self):
        """Send the groups to the gui."""
        logger.debug("Sending groups")
        self._results.send({"type": MSG_GROUPS, "message": groups.dumps()})

    def _read_commands(self):
        """Handle all unread commands."""
        while self._commands.poll():
            cmd = self._commands.recv()
            logger.debug('Received command "%s"', cmd)

            if cmd == CMD_TERMINATE:
                logger.debug("Helper terminates")
                sys.exit(0)

            if cmd == CMD_REFRESH_GROUPS:
                groups.refresh()
                self._send_groups()
                continue

            group = groups.find(key=cmd)
            if group is None:
                groups.refresh()
                group = groups.find(key=cmd)

            if group is not None:
                self.group = group
                continue

            logger.error('Received unknown command "%s"', cmd)

        logger.debug("No more commands in pipe")

    def _start_reading(self):
        """Tell the evdev lib to start looking for keycodes.

        If read is called without prior start_reading, no keycodes
        will be available.

        This blocks forever until it discovers a new command on the socket.
        """
        rlist = {}

        if self.group is None:
            logger.error("group is None")
            return

        virtual_devices = []
        # Watch over each one of the potentially multiple devices per
        # hardware
        for path in self.group.paths:
            try:
                device = evdev.InputDevice(path)
            except FileNotFoundError:
                continue

            if evdev.ecodes.EV_KEY in device.capabilities():
                virtual_devices.append(device)

        if len(virtual_devices) == 0:
            logger.debug('No interesting device for "%s"', self.group.key)
            return

        for device in virtual_devices:
            rlist[device.fd] = device

        logger.debug(
            'Starting reading keycodes from "%s"',
            '", "'.join([device.name for device in virtual_devices]),
        )

        rlist[self._commands] = self._commands

        while True:
            ready_fds = select.select(rlist, [], [])
            if len(ready_fds[0]) == 0:
                # happens with sockets sometimes. Sockets are not stable and
                # not used, so nothing to worry about now.
                continue

            for fd in ready_fds[0]:
                if rlist[fd] == self._commands:
                    # all commands will cause the reader to start over
                    # (possibly for a different device).
                    # _read_commands will check what is going on
                    logger.debug("Stops reading due to new command")
                    return

                device = rlist[fd]

                try:
                    event = device.read_one()
                    if event:
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

        blacklisted_keys = [evdev.ecodes.BTN_TOOL_DOUBLETAP]

        if event.type == EV_KEY and event.code in blacklisted_keys:
            return

        if event.type == EV_ABS:
            abs_range = utils.get_abs_range(device, event.code)
            event.value = utils.classify_action(event, abs_range)
        else:
            event.value = utils.classify_action(event)

        self._results.send(
            {
                "type": MSG_EVENT,
                "message": (event.sec, event.usec, event.type, event.code, event.value),
            }
        )
