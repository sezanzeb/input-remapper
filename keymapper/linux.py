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


"""Device and evdev stuff that is independent from the display server."""


import subprocess
import time
import threading
import asyncio

import evdev

from keymapper.logger import logger
from keymapper.cli import apply_empty_symbols
from keymapper.getdevices import get_devices
from keymapper.mapping import custom_mapping, system_mapping


def can_grab(path):
    """Can input events from the device be read?

    Parameters
    ----------
    path : string
        Path in dev, for example '/dev/input/event7'
    """
    p = subprocess.run(['fuser', '-v', path])
    return p.returncode == 1


class KeycodeReader:
    """Keeps reading keycodes in the background for the UI to use.

    When a button was pressed, the newest keycode can be obtained from this
    object.
    """
    def __init__(self, device):
        self.device = device
        self.virtual_devices = []
        self.start_injecting()

    def clear(self):
        """Next time when reading don't return the previous keycode."""
        # read all of them to clear the buffer or whatever
        for virtual_device in self.virtual_devices:
            while virtual_device.read_one():
                pass

    def start_injecting_worker(self, path):
        """Inject keycodes for one of the virtual devices."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        device = evdev.InputDevice(path)
        keymapper_device = evdev.UInput(
            name='key-mapper',
            phys='key-mapper-uinput'
        )

        for event in device.read_loop():
            if event.type != evdev.ecodes.EV_KEY:
                continue

            # this happens to report key codes that are 8 lower
            # than the ones reported by xev and that X expects
            input_keycode = event.code + 8

            character = custom_mapping.get_character(input_keycode)

            if character is None:
                # unknown keycode, forward it
                target_keycode = input_keycode
            else:
                target_keycode = system_mapping.get_keycode(character)
                if target_keycode is None:
                    logger.error(
                        'Cannot find character %s in xmodmap',
                        character
                    )
                    continue
                # turns out, if I don't sleep here X/Linux gets confused. Lets
                # assume a mapping of 10 to z. Without sleep it would always
                # result in 1z 1z 1z. Even though the empty xkb symbols file
                # was applied on the mouse! And I really made sure .write was
                # not called twice. 1 just somewhow sneaks past the symbols.
                # 0.0005 has many errors. 0.001 has them super rare.
                # 5ms is still faster than anything on the planet so that's.
                # fine. I came up with that after randomly poking around in,
                # frustration. I don't know of any helpful resource that
                # explains this
                time.sleep(0.005)

            # TODO test for the stuff put into write
            keymapper_device.write(evdev.ecodes.EV_KEY, target_keycode - 8, event.value)
            keymapper_device.syn()

    def start_injecting(self):
        """Read keycodes and inject the mapped character forever."""
        paths = get_devices()[self.device]['paths']

        logger.debug(
            'Starting injecting the mapping for %s on %s',
            self.device,
            ', '.join(paths)
        )

        apply_empty_symbols(self.device)

        # Watch over each one of the potentially multiple devices per hardware
        for path in paths:
            threading.Thread(
                target=self.start_injecting_worker,
                args=(path,)
            ).start()

    def read(self):
        """Get the newest key or None if none was pressed."""
        newest_keycode = None
        for virtual_device in self.virtual_devices:
            while True:
                event = virtual_device.read_one()
                if event is None:
                    break
                if event.type == evdev.ecodes.EV_KEY and event.value == 1:
                    # value: 1 for down, 0 for up, 2 for hold.
                    # this happens to report key codes that are 8 lower
                    # than the ones reported by xev
                    newest_keycode = event.code + 8
        return newest_keycode
