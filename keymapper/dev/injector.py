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
from evdev.ecodes import EV_KEY, EV_ABS

from keymapper.logger import logger
from keymapper.getdevices import get_devices
from keymapper.state import system_mapping, KEYCODE_OFFSET
from keymapper.dev.keycode_mapper import handle_keycode
from keymapper.dev.ev_abs_mapper import ev_abs_mapper
from keymapper.dev.macros import parse


DEV_NAME = 'key-mapper'
CLOSE = 0


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
            name=f'{DEV_NAME} numlock-control',
            phys=DEV_NAME,
        )
        device.write(EV_KEY, evdev.ecodes.KEY_NUMLOCK, 1)
        device.syn()
        device.write(EV_KEY, evdev.ecodes.KEY_NUMLOCK, 0)
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
        self._msg_pipe = multiprocessing.Pipe()

        # some EV_ABS mapping stuff
        self.abs_state = [0, 0]

    def start_injecting(self):
        """Start injecting keycodes."""
        self._process = multiprocessing.Process(target=self._start_injecting)
        self._process.start()

    def map_ev_to_abs(self, capabilities):
        """Check if joystick movements can and should be mapped."""
        # mapping buttons only works without ABS events in the capabilities,
        # possibly due to some intentional constraints in the os. So always
        # do this without the option to configure, if it is possible.
        return evdev.ecodes.ABS_X in capabilities.get(EV_ABS, [])

    def _prepare_device(self, path):
        """Try to grab the device, return if not needed/possible.

        Also return if ABS events are changed to REL mouse movements,
        because the capabilities of the returned device are changed
        so this cannot be checked later anymore.
        """
        device = evdev.InputDevice(path)

        if device is None:
            return None, False

        capabilities = device.capabilities(absinfo=False)

        needed = False
        if capabilities.get(EV_KEY) is not None:
            for (ev_type, keycode), _ in self.mapping:
                # TEST ev_type
                if keycode - KEYCODE_OFFSET in capabilities.get(ev_type, []):
                    needed = True
                    break

        map_ev_abs = self.map_ev_to_abs(capabilities)

        if map_ev_abs:
            needed = True

        if not needed:
            # skipping reading and checking on events from those devices
            # may be beneficial for performance.
            logger.debug('No need to grab %s', path)
            return None, False

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
                # it might take a little time until the device is free if
                # it was previously grabbed.
                logger.debug('Failed attemts to grab %s: %d', path, attempts)

            if attempts >= 4:
                logger.error('Cannot grab %s, it is possibly in use', path)
                return None, False

            time.sleep(0.15)

        return device, map_ev_abs

    def _modify_capabilities(self, input_device, map_ev_abs):
        """Adds all keycode into a copy of a devices capabilities.

        Prameters
        ---------
        input_device : evdev.InputDevice
        map_ev_abs : bool
            if ABS capabilities should be removed in favor of REL
        """
        ecodes = evdev.ecodes

        # copy the capabilities because the uinput is going
        # to act like the device.
        capabilities = input_device.capabilities(absinfo=False)

        # Furthermore, support all injected keycodes
        if len(self.mapping) > 0 and capabilities.get(ecodes.EV_KEY) is None:
            capabilities[ecodes.EV_KEY] = []

        for (ev_type, _), character in self.mapping:
            keycode = system_mapping.get(character)
            if keycode is not None:
                capabilities[ev_type].append(keycode - KEYCODE_OFFSET)

        if map_ev_abs:
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

    async def _msg_listener(self, loop):
        """Wait for messages from the main process to do special stuff."""
        while True:
            frame_available = asyncio.Event()
            loop.add_reader(self._msg_pipe[0].fileno(), frame_available.set)
            await frame_available.wait()
            frame_available.clear()
            msg = self._msg_pipe[0].recv()
            if msg == CLOSE:
                logger.debug('Received close signal')
                # stop the event loop and cause the process to reach its end
                # cleanly. Using .terminate prevents coverage from working.
                loop.stop()
                return

    def _start_injecting(self):
        """The injection worker that keeps injecting until terminated.

        Stuff is non-blocking by using asyncio in order to do multiple things
        somewhat concurrently.
        """
        loop = asyncio.get_event_loop()
        coroutines = []

        logger.info('Starting injecting the mapping for %s', self.device)

        paths = get_devices()[self.device]['paths']

        # Watch over each one of the potentially multiple devices per hardware
        for path in paths:
            input_device, map_ev_abs = self._prepare_device(path)
            if input_device is None:
                continue

            # certain capabilities can have side effects apparently. with an
            # EV_ABS capability, EV_REL won't move the mouse pointer anymore.
            # so don't merge all InputDevices into one UInput device.
            uinput = evdev.UInput(
                name=f'{DEV_NAME} {self.device}',
                phys=DEV_NAME,
                events=self._modify_capabilities(input_device, map_ev_abs)
            )

            # keycode injection
            coroutine = self._keycode_loop(input_device, uinput, map_ev_abs)
            coroutines.append(coroutine)

            # mouse movement injection
            if map_ev_abs:
                self.abs_state[0] = 0
                self.abs_state[1] = 0
                coroutine = ev_abs_mapper(
                    self.abs_state,
                    input_device,
                    uinput
                )
                coroutines.append(coroutine)

        if len(coroutines) == 0:
            logger.error('Did not grab any device')
            return

        coroutines.append(self._msg_listener(loop))

        try:
            loop.run_until_complete(asyncio.gather(*coroutines))
        except RuntimeError:
            # stopped event loop most likely
            pass

        if len(coroutines) > 0:
            logger.debug('asyncio coroutines ended')

    def _macro_write(self, character, value, uinput):
        """Handler for macros."""
        keycode = system_mapping[character]
        logger.spam(
            'macro writes code:%s value:%d char:%s',
            keycode, value, character
        )
        uinput.write(EV_KEY, keycode - KEYCODE_OFFSET, value)
        uinput.syn()

    async def _keycode_loop(self, device, uinput, map_ev_abs):
        """Inject keycodes for one of the virtual devices.

        Can be stopped by stopping the asyncio loop.

        Parameters
        ----------
        device : evdev.InputDevice
            where to read keycodes from
        uinput : evdev.UInput
            where to write keycodes to
        map_ev_abs : bool
            if joystick events should be mapped to mouse movements
        """
        # efficiently figure out the target keycode without taking
        # extra steps.
        code_code_mapping = {}

        # Parse all macros beforehand
        logger.debug('Parsing macros')
        macros = {}
        for (ev_type, keycode), output in self.mapping:
            keycode -= KEYCODE_OFFSET

            if '(' in output and ')' in output and len(output) >= 4:
                # probably a macro
                macros[keycode] = parse(
                    output,
                    lambda *args: self._macro_write(*args, uinput)
                )
                continue

            target_keycode = system_mapping.get(output)
            if target_keycode is None:
                logger.error('Don\'t know what %s is', output)
                continue

            code_code_mapping[keycode] = target_keycode - KEYCODE_OFFSET

        logger.debug(
            'Started injecting into %s, fd %s',
            uinput.device.path, uinput.fd
        )

        async for event in device.async_read_loop():
            if map_ev_abs and event.type == EV_ABS:
                if event.code not in [evdev.ecodes.ABS_X, evdev.ecodes.ABS_Y]:
                    continue
                if event.code == evdev.ecodes.ABS_X:
                    self.abs_state[0] = event.value
                if event.code == evdev.ecodes.ABS_Y:
                    self.abs_state[1] = event.value
                continue

            if event.type != EV_KEY:
                uinput.write(event.type, event.code, event.value)
                # this already includes SYN events, so need to syn here again
                continue

            if event.value == 2:
                # linux does them itself, no need to trigger them
                continue

            handle_keycode(code_code_mapping, macros, event, uinput)

        # this should only ever happen in tests to avoid blocking them
        # forever, as soon as all events are consumed. In normal operation
        # there is no end to the events.
        logger.error(
            'The injector for "%s" stopped early',
            uinput.device.path
        )

    @ensure_numlock
    def stop_injecting(self):
        """Stop injecting keycodes."""
        logger.info('Stopping injecting keycodes for device "%s"', self.device)
        self._msg_pipe[1].send(CLOSE)
