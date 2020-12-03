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


"""Keeps reading keycodes in the background for the UI to use."""


import sys
import select
import multiprocessing

import evdev

from keymapper.logger import logger
from keymapper.getdevices import get_devices, refresh_devices
from keymapper.dev.keycode_mapper import should_map_event_as_btn


CLOSE = 1


class _KeycodeReader:
    """Keeps reading keycodes in the background for the UI to use.

    When a button was pressed, the newest keycode can be obtained from this
    object. GTK has get_keycode for keyboard keys, but KeycodeReader also
    has knowledge of buttons like the middle-mouse button.
    """
    def __init__(self):
        self.virtual_devices = []
        self._pipe = None
        self._process = None

    def __del__(self):
        self.stop_reading()

    def stop_reading(self):
        if self._pipe is not None:
            logger.debug('Sending close msg to reader')
            self._pipe[0].send(CLOSE)
            self._pipe = None

    def clear(self):
        """Next time when reading don't return the previous keycode."""
        # just call read to clear the pipe
        self.read()

    def start_reading(self, device_name):
        """Tell the evdev lib to start looking for keycodes.

        If read is called without prior start_reading, no keycodes
        will be available.
        """
        self.stop_reading()

        # make sure this sees up to date devices, including those created
        # by key-mapper
        refresh_devices()

        self.virtual_devices = []

        for name, group in get_devices().items():
            if device_name not in name:
                continue

            # Watch over each one of the potentially multiple devices per
            # hardware
            for path in group['paths']:
                try:
                    device = evdev.InputDevice(path)
                except FileNotFoundError:
                    continue

                if evdev.ecodes.EV_KEY in device.capabilities():
                    self.virtual_devices.append(device)

            logger.debug(
                'Starting reading keycodes from "%s"',
                '", "'.join([device.name for device in self.virtual_devices])
            )

        pipe = multiprocessing.Pipe()
        self._pipe = pipe
        self._process = multiprocessing.Process(target=self._read_worker)
        self._process.start()

    def _consume_event(self, event):
        """Write the event code into the pipe if it is a key-down press."""
        # value: 1 for down, 0 for up, 2 for hold.
        if self._pipe[1].closed:
            logger.debug('Pipe closed, reader stops.')
            sys.exit(0)

        if should_map_event_as_btn(event.type, event.code):
            logger.spam(
                'got code:%s value:%s type:%s',
                event.code,
                event.value,
                evdev.ecodes.EV[event.type]
            )
            self._pipe[1].send((event.type, event.code))

    def _read_worker(self):
        """Process that reads keycodes and buffers them into a pipe."""
        # using a process that blocks instead of read_one made it easier
        # to debug via the logs, because the UI was not polling properly
        # at some point which caused logs for events not to be written.
        rlist = {device.fd: device for device in self.virtual_devices}
        rlist[self._pipe[1]] = self._pipe[1]

        while True:
            ready = select.select(rlist, [], [])[0]
            for fd in ready:
                readable = rlist[fd]
                if isinstance(readable, multiprocessing.connection.Connection):
                    msg = readable.recv()
                    if msg == CLOSE:
                        logger.debug('Reader stopped')
                        return
                    continue

                try:
                    for event in rlist[fd].read():
                        self._consume_event(event)
                except OSError:
                    logger.debug(
                        'Device "%s" disappeared from the reader',
                        rlist[fd].path
                    )
                    del rlist[fd]

    def read(self):
        """Get the newest tuple of event type, keycode or None."""
        if self._pipe is None:
            logger.debug('No pipe available to read from')
            return None, None

        newest_event = (None, None)
        while self._pipe[0].poll():
            newest_event = self._pipe[0].recv()

        return newest_event


keycode_reader = _KeycodeReader()
