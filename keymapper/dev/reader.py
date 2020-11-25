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


import evdev

from keymapper.logger import logger
from keymapper.getdevices import get_devices, refresh_devices


# offset between xkb and linux keycodes. linux keycodes are lower
KEYCODE_OFFSET = 8


class _KeycodeReader:
    """Keeps reading keycodes in the background for the UI to use.

    When a button was pressed, the newest keycode can be obtained from this
    object. GTK has get_keycode for keyboard keys, but KeycodeReader also
    has knowledge of buttons like the middle-mouse button.
    """
    def __init__(self):
        self.virtual_devices = []

    def clear(self):
        """Next time when reading don't return the previous keycode."""
        # read all of them to clear the buffer or whatever
        for virtual_device in self.virtual_devices:
            while virtual_device.read_one():
                pass

    def start_reading(self, device):
        """Tell the evdev lib to start looking for keycodes.

        If read is called without prior start_reading, no keycodes
        will be available.
        """
        # make sure this sees up to date devices, including those created
        # by key-mapper
        refresh_devices()

        self.virtual_devices = []

        for name, group in get_devices(include_keymapper=True).items():
            # also find stuff like "key-mapper {device}"
            if device not in name:
                continue

            # Watch over each one of the potentially multiple devices per
            # hardware
            for path in group['paths']:
                try:
                    self.virtual_devices.append(evdev.InputDevice(path))
                except FileNotFoundError:
                    continue

            logger.debug(
                'Starting reading keycodes from "%s"',
                '", "'.join([device.name for device in self.virtual_devices])
            )

    def read(self):
        """Get the newest keycode or None if none was pressed."""
        newest_keycode = None
        for virtual_device in self.virtual_devices:
            while True:
                try:
                    event = virtual_device.read_one()
                except OSError:
                    # can happen if a device disappears
                    logger.debug(
                        '%s cannot be read anymore',
                        virtual_device.name
                    )
                    self.virtual_devices.remove(virtual_device)
                    break

                if event is None:
                    break

                if event.type == evdev.ecodes.EV_KEY and event.value == 1:
                    logger.spam(
                        'got code:%s value:%s',
                        event.code + KEYCODE_OFFSET, event.value
                    )
                    # value: 1 for down, 0 for up, 2 for hold.
                    newest_keycode = event.code + KEYCODE_OFFSET
        return newest_keycode


keycode_reader = _KeycodeReader()
