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


"""Keeps injecting keycodes in the background based on the mapping."""


import re
import asyncio
import time
import subprocess
import multiprocessing

import evdev

from keymapper.logger import logger
from keymapper.config import config
from keymapper.getdevices import get_devices
from keymapper.state import system_mapping, KEYCODE_OFFSET
from keymapper.dev.macros import parse


DEV_NAME = 'key-mapper'
DEVICE_CREATED = 1
FAILED = 2
DEVICE_SKIPPED = 3


def is_numlock_on():
    """Get the current state of the numlock."""
    xset_q = subprocess.check_output(['xset', 'q']).decode()
    num_lock_status = re.search(
        r'Num Lock:\s+(.+?)\s',
        xset_q
    )

    if num_lock_status is not None:
        return num_lock_status[1] == 'on'

    return False


def toggle_numlock():
    """Turn the numlock on or off."""
    try:
        subprocess.check_output(['numlockx', 'toggle'])
    except FileNotFoundError:
        # doesn't seem to be installed everywhere
        logger.debug('numlockx not found, trying to inject a keycode')
        # and this doesn't always work.
        device = evdev.UInput(
            name=f'key-mapper numlock-control',
            phys='key-mapper',
        )
        device.write(evdev.ecodes.EV_KEY, evdev.ecodes.KEY_NUMLOCK, 1)
        device.syn()
        device.write(evdev.ecodes.EV_KEY, evdev.ecodes.KEY_NUMLOCK, 0)
        device.syn()


def ensure_numlock(func):
    """Decorator to reset the numlock to its initial state afterwards."""
    def wrapped(*args, **kwargs):
        # for some reason, grabbing a device can modify the num lock state.
        # remember it and apply back later
        numlock_before = is_numlock_on()
        result = func(*args, **kwargs)
        numlock_after = is_numlock_on()
        if numlock_after != numlock_before:
            logger.debug('Reverting numlock status to %s', numlock_before)
            toggle_numlock()
        return result
    return wrapped


class KeycodeInjector:
    """Keeps injecting keycodes in the background based on the mapping.

    Is a process to make it non-blocking for the rest of the code and to
    make running multiple injector easier. There is one procss per
    hardware-device that is being mapped.
    """
    @ensure_numlock
    def __init__(self, device, mapping):
        """Start injecting keycodes based on custom_mapping.

        Parameters
        ----------
        device : string
            the name of the device as available in get_device
        """
        self.device = device
        self.mapping = mapping
        self._process = None

    def __del__(self):
        if self._process is not None:
            self._process.terminate()

    def start_injecting(self):
        """Start injecting keycodes."""
        self._process = multiprocessing.Process(target=self._start_injecting)
        self._process.start()

    def _prepare_device(self, path):
        """Try to grab the device, return if not needed/possible."""
        device = evdev.InputDevice(path)

        if device is None:
            return None

        capabilities = device.capabilities(absinfo=False)

        needed = False
        for keycode, _ in self.mapping:
            if keycode - KEYCODE_OFFSET in capabilities[evdev.ecodes.EV_KEY]:
                needed = True
                break
        # TODO only if map ABS to REL keep ABS devics
        if capabilities.get(evdev.ecodes.EV_REL) is not None:
            needed = True

        if not needed:
            # skipping reading and checking on events from those devices
            # may be beneficial for performance.
            logger.debug('No need to grab %s', path)
            return None

        attempts = 0
        while True:
            device = evdev.InputDevice(path)
            try:
                # grab to avoid e.g. the disabled keycode of 10 to confuse
                # X, especially when one of the buttons of your mouse also
                # uses 10. This also avoids having to load an empty xkb
                # symbols file to prevent writing any unwanted keys.
                device.grab()
                break
            except IOError:
                attempts += 1
                logger.debug('Failed attemts to grab %s: %d', path, attempts)

            if attempts >= 4:
                logger.error('Cannot grab %s, it is possibly in use', path)
                return None

            # it might take a little time until the device is free if
            # it was previously grabbed.
            time.sleep(0.15)

        return device

    def map_abs_to_rel(self):
        # TODO offer configuration via the UI if a gamepad is elected
        return True

    def _modify_capabilities(self, input_device):
        """Adds all keycode into a copy of a devices capabilities.

        Prameters
        ---------
        input_device : evdev.InputDevice
        """
        ecodes = evdev.ecodes

        # copy the capabilities because the keymapper_device is going
        # to act like the device.
        capabilities = input_device.capabilities(absinfo=False)

        # Furthermore, support all injected keycodes
        if len(self.mapping) > 0 and capabilities.get(ecodes.EV_KEY) is None:
            capabilities[ecodes.EV_KEY] = []

        for _, character in self.mapping:
            keycode = system_mapping.get(character)
            if keycode is not None:
                capabilities[ecodes.EV_KEY].append(keycode - KEYCODE_OFFSET)

        if self.map_abs_to_rel():
            if capabilities.get(ecodes.EV_ABS):
                del capabilities[ecodes.EV_ABS]
            capabilities[ecodes.EV_REL] = [
                evdev.ecodes.REL_X,
                evdev.ecodes.REL_Y,
                # for my system to recognize it as mouse, WHEEL is also needed:
                evdev.ecodes.REL_WHEEL,
            ]

        # just like what python-evdev does in from_device
        if ecodes.EV_SYN in capabilities:
            del capabilities[ecodes.EV_SYN]
        if ecodes.EV_FF in capabilities:
            del capabilities[ecodes.EV_FF]

        return capabilities

    def _start_injecting(self):
        """The injection worker that keeps injecting until terminated.

        Stuff is non-blocking by using asyncio in order to do multiple things
        somewhat concurrently.
        """
        # TODO do select.select insted of async_read_loop
        loop = asyncio.get_event_loop()
        coroutines = []

        logger.info('Starting injecting the mapping for %s', self.device)

        paths = get_devices()[self.device]['paths']
        devices = [self._prepare_device(path) for path in paths]

        # Watch over each one of the potentially multiple devices per hardware
        for input_device in devices:
            if input_device is None:
                continue

            # certain capabilities can have side effects apparently. with an
            # EV_ABS capability, EV_REL won't move the mouse pointer anymore.
            # so don't merge all InputDevices into one UInput device.
            uinput = evdev.UInput(
                name=f'key-mapper {self.device}',
                phys='key-mapper',
                events=self._modify_capabilities(input_device)
            )

            coroutine = self._injection_loop(input_device, uinput)
            coroutines.append(coroutine)

        if len(coroutines) == 0:
            raise OSError('Could not grab any device')

        loop.run_until_complete(asyncio.gather(*coroutines))

    def _write(self, device, type, keycode, value):
        """Actually inject."""
        device.write(type, keycode, value)
        device.syn()

    def _macro_write(self, character, value, keymapper_device):
        """Handler for macros."""
        keycode = system_mapping[character]
        logger.spam(
            'macro writes code:%s value:%d char:%s',
            keycode, value, character
        )
        self._write(
            keymapper_device,
            evdev.ecodes.EV_KEY,
            keycode - KEYCODE_OFFSET,
            value
        )

    async def spam_mouse_movements(self, keymapper_device):
        """Keep writing mouse movements based on the gamepad stick position."""
        # TODO get absinfo beforehand
        max_value = 32767
        max_speed = ((max_value ** 2) * 2) ** 0.5
        while True:
            await asyncio.sleep(1 / 60)

            abs_y = self.abs_y
            abs_x = self.abs_x

            non_linearity = config.get('gamepad.non_linearity', 4)
            if non_linearity != 1:
                # to make small movements smaller for more precision
                speed = (abs_x ** 2 + abs_y ** 2) ** 0.5
                factor = (speed / max_speed) ** non_linearity
            else:
                factor = 1

            rel_x = abs_x * factor * 80 / max_value
            rel_y = abs_y * factor * 80 / max_value

            self.pending_x_rel += rel_x
            self.pending_y_rel += rel_y
            rel_x = int(self.pending_x_rel)
            rel_y = int(self.pending_y_rel)
            self.pending_x_rel -= rel_x
            self.pending_y_rel -= rel_y

            if rel_y != 0:
                self._write(
                    keymapper_device,
                    evdev.ecodes.EV_REL,
                    evdev.ecodes.ABS_Y,
                    rel_y
                )

            if rel_x != 0:
                self._write(
                    keymapper_device,
                    evdev.ecodes.EV_REL,
                    evdev.ecodes.ABS_X,
                    rel_x
                )

    async def _injection_loop(self, device, keymapper_device):
        """Inject keycodes for one of the virtual devices.

        Parameters
        ----------
        device : evdev.InputDevice
            where to read keycodes from
        keymapper_device : evdev.UInput
            where to write keycodes to
        """
        # TODO this function is too long
        # Parse all macros beforehand
        logger.debug('Parsing macros')
        macros = {}
        for keycode, output in self.mapping:
            if '(' in output and ')' in output and len(output) >= 4:
                # probably a macro
                macros[keycode] = parse(
                    output,
                    lambda *args: self._macro_write(*args, keymapper_device)
                )

        logger.debug(
            'Started injecting into %s, fd %s',
            keymapper_device.device.path, keymapper_device.fd
        )

        self.abs_x = 0
        self.abs_y = 0

        # events only take ints, so a movement of 0.3 needs to add up to
        # 1.2 to affect the cursor.
        self.pending_x_rel = 0
        self.pending_y_rel = 0

        asyncio.ensure_future(self.spam_mouse_movements(keymapper_device))

        async for event in device.async_read_loop():
            if self.map_abs_to_rel() and event.type == evdev.ecodes.EV_ABS:
                if event.code not in [evdev.ecodes.ABS_X, evdev.ecodes.ABS_Y]:
                    continue

                if event.code == evdev.ecodes.ABS_X:
                    self.abs_x = event.value

                if event.code == evdev.ecodes.ABS_Y:
                    self.abs_y = event.value

                continue

            if event.type != evdev.ecodes.EV_KEY:
                keymapper_device.write(event.type, event.code, event.value)
                # this already includes SYN events, so need to syn here again
                continue

            if event.value == 2:
                # linux does them itself, no need to trigger them
                continue

            input_keycode = event.code + KEYCODE_OFFSET

            character = self.mapping.get_character(input_keycode)

            if character is None:
                # unknown keycode, forward it
                target_keycode = input_keycode
            elif macros.get(input_keycode) is not None:
                if event.value == 0:
                    continue

                logger.spam(
                    'got code:%s value:%s, maps to macro %s',
                    event.code + KEYCODE_OFFSET,
                    event.value,
                    character
                )
                macro = macros.get(input_keycode)
                if macro is not None:
                    asyncio.ensure_future(macro.run())
                continue
            else:
                # TODO compile int-int mapping instead of going this route.
                #  I think that makes the reverse mapping obsolete.
                target_keycode = system_mapping.get(character)
                if target_keycode is None:
                    logger.error(
                        'Don\'t know what %s maps to',
                        character
                    )
                    continue

                logger.spam(
                    'got code:%s value:%s, maps to code:%s char:%s',
                    event.code + KEYCODE_OFFSET,
                    event.value,
                    target_keycode,
                    character
                )

            self._write(
                keymapper_device,
                event.type,
                target_keycode - KEYCODE_OFFSET,
                event.value
            )

        # this should only ever happen in tests to avoid blocking them
        # forever, as soon as all events are consumed. In normal operation
        # there is no end to the events.
        logger.error(
            'The injector for "%s" stopped early',
            keymapper_device.device.path
        )

    @ensure_numlock
    def stop_injecting(self):
        """Stop injecting keycodes."""
        logger.info('Stopping injecting keycodes for device %s', self.device)
        if self._process is not None and self._process.is_alive():
            self._process.terminate()
