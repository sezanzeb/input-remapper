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
import multiprocessing
import asyncio

import evdev

from keymapper.logger import logger
from keymapper.getdevices import get_devices
from keymapper.state import custom_mapping, system_mapping


DEV_NAME = 'key-mapper'
DEVICE_CREATED = 1


def can_grab(path):
    """Can input events from the device be read?

    Parameters
    ----------
    path : string
        Path in dev, for example '/dev/input/event7'
    """
    p = subprocess.run(['fuser', '-v', path])
    return p.returncode == 1


class KeycodeInjector:
    """Keeps injecting keycodes in the background based on the mapping."""
    def __init__(self, device):
        self.device = device
        self.virtual_devices = []
        self.processes = []
        self.start_injecting()

    def start_injecting(self):
        """Read keycodes and inject the mapped character forever."""
        self.stop_injecting()

        paths = get_devices()[self.device]['paths']

        logger.info(
            'Starting injecting the mapping for %s on %s',
            self.device,
            ', '.join(paths)
        )

        # Watch over each one of the potentially multiple devices per hardware
        for path in paths:
            pipe = multiprocessing.Pipe()
            worker = multiprocessing.Process(
                target=self._start_injecting_worker,
                args=(path, custom_mapping, pipe[1])
            )
            worker.start()
            # wait for the process to notify creation of the new injection
            # device, to keep the logs in order.
            pipe[0].recv()
            self.processes.append(worker)

    def stop_injecting(self):
        """Stop injecting keycodes."""
        # TODO test
        logger.info('Stopping injecting keycodes')
        for i, process in enumerate(self.processes):
            if process is None:
                continue

            if process.is_alive():
                process.terminate()
                self.processes[i] = None

    def _start_injecting_worker(self, path, mapping, pipe):
        """Inject keycodes for one of the virtual devices."""
        # TODO test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        device = evdev.InputDevice(path)
        try:
            # grab to avoid e.g. the disabled keycode of 10 to confuse X,
            # especially when one of the buttons of your mouse also uses 10
            device.grab()
        except IOError:
            logger.error('Cannot grab %s', path)

        # copy the capabilities because the keymapper_device is going
        # to act like the mouse
        keymapper_device = evdev.UInput.from_device(device)

        pipe.send(DEVICE_CREATED)

        logger.debug(
            'Started injecting into %s, fd %s',
            device.path, keymapper_device.fd
        )

        for event in device.read_loop():
            if event.type != evdev.ecodes.EV_KEY:
                logger.spam(
                    'got type:%s code:%s value:%s, forward',
                    event.type, event.code, event.value
                )
                keymapper_device.write(event.type, event.code, event.value)
                keymapper_device.syn()
                continue

            if event.value == 2:
                # linux does them itself, no need to trigger them
                continue

            # this happens to report key codes that are 8 lower
            # than the ones reported by xev and that X expects
            input_keycode = event.code + 8

            character = mapping.get_character(input_keycode)

            if character is None:
                # unknown keycode, forward it
                continue
            else:
                target_keycode = system_mapping.get_keycode(character)
                if target_keycode is None:
                    logger.error(
                        'Cannot find character %s in the internal mapping',
                        character
                    )
                    continue

            logger.spam(
                'got code:%s value:%s, maps to code:%s char:%s',
                event.code + 8, event.value, target_keycode, character
            )

            # TODO test for the stuff put into write
            keymapper_device.write(
                evdev.ecodes.EV_KEY,
                target_keycode - 8,
                event.value
            )

            keymapper_device.syn()
