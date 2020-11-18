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
from keymapper.cli import apply_symbols
from keymapper.getdevices import get_devices, refresh_devices
from keymapper.state import custom_mapping, internal_mapping, \
    system_mapping, capabilities


DEV_NAME = 'key-mapper'


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

        apply_symbols(self.device, name='key-mapper-empty')

        # Watch over each one of the potentially multiple devices per hardware
        for path in paths:
            worker = multiprocessing.Process(
                target=self._start_injecting_worker,
                args=(path, custom_mapping)
            )
            worker.start()
            self.processes.append(worker)

        # it takes a little time for the key-mapper devices to appear
        time.sleep(0.1)

        refresh_devices()
        apply_symbols(DEV_NAME, name='key-mapper-dev', keycodes='key-mapper')

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

        # apply the default layout back
        apply_symbols(self.device)

    def _start_injecting_worker(self, path, mapping):
        """Inject keycodes for one of the virtual devices."""
        # TODO test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        device = evdev.InputDevice(path)
        """try:
            # grab to avoid e.g. the disabled keycode of 10 to confuse X,
            # especially when one of the buttons of your mouse also uses 10
            device.grab()
        except IOError:
            logger.error('Cannot grab %s', path)"""

        # foo = evdev.InputDevice('/dev/input/event2')
        keymapper_device = evdev.UInput(
            name=DEV_NAME,
            phys='key-mapper-uinput',
            events={
                evdev.ecodes.EV_KEY: [c - 8 for c in capabilities]
            }
        )

        logger.debug(
            'Started injecting into %s, fd %s',
            device.path, keymapper_device.fd
        )

        for event in device.read_loop():
            if event.type != evdev.ecodes.EV_KEY:
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
                # turns out, if I don't sleep here X/Linux gets confused. Lets
                # assume a mapping of 10 to z. Without sleep it would always
                # result in 1z 1z 1z. Even though the empty xkb symbols file
                # was applied on the mouse! And I really made sure `write` was
                # not called twice. '1' just somewhow sneaks past the symbols.
                # 0.0005 has many errors. 0.001 has them super rare.
                # 5ms is still faster than anything on the planet so that's.
                # fine. I came up with that after randomly poking around in,
                # frustration. I don't know of any helpful resource that
                # explains this
                # TODO still needed? if yes, add to HELP.md
                time.sleep(0.005)

            logger.debug2(
                'got code:%s value:%s, maps to code:%s char:%s',
                event.code + 8, event.value, target_keycode, character
            )

            # TODO test for the stuff put into write
            keymapper_device.write(
                evdev.ecodes.EV_KEY,
                target_keycode - 8,
                event.value
            )

            # the second device that starts writing an event.value of 2 will
            # take ownership of what is happening. Following example:
            # (KB = keyboard, example devices)
            # hold a on KB1:
            #   a-1, a-2, a-2, a-2, ...
            # hold shift on KB2:
            #   shift-2, shift-2, shift-2, ...
            # No a-2 on KB1 happening anymore. The xkb symbols of KB2 will
            # be used! So if KB2 maps shift+a to b, it will write b, even
            # though KB1 maps shift+a to c! And if you reverse this, hold
            # shift on KB2 first and then a on KB1, the xkb mapping of KB1
            # will take effect and write c!

            # foo.write(evdev.ecodes.EV_SYN, evdev.ecodes.SYN_REPORT, 0)
            keymapper_device.syn()
