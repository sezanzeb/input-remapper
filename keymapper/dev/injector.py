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
from evdev.ecodes import EV_KEY, EV_ABS, EV_REL

from keymapper.logger import logger
from keymapper.getdevices import get_devices
from keymapper.state import system_mapping
from keymapper.dev.keycode_mapper import handle_keycode, \
    should_map_event_as_btn
from keymapper.dev.ev_abs_mapper import ev_abs_mapper, JOYSTICK
from keymapper.dev.macros import parse, is_this_a_macro


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


def set_numlock(state):
    """Set the numlock to a given state of True or False."""
    value = {
        True: 'on',
        False: 'off'
    }[state]

    try:
        subprocess.check_output(['numlockx', value])
    except FileNotFoundError:
        # doesn't seem to be installed everywhere
        logger.debug('numlockx not found')


def ensure_numlock(func):
    """Decorator to reset the numlock to its initial state afterwards."""
    def wrapped(*args, **kwargs):
        # for some reason, grabbing a device can modify the num lock state.
        # remember it and apply back later
        numlock_before = is_numlock_on()
        result = func(*args, **kwargs)
        set_numlock(numlock_before)
        return result
    return wrapped


class KeycodeInjector:
    """Keeps injecting keycodes in the background based on the mapping.

    Is a process to make it non-blocking for the rest of the code and to
    make running multiple injector easier. There is one procss per
    hardware-device that is being mapped.
    """
    regrab_timeout = 0.5

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
        self._code_to_code = self._map_codes_to_codes()
        self.stopped = False

        # when moving the joystick and then staying at a position, no
        # events will be written anymore. Remember the last value the
        # joystick reported, because it is still remaining at that
        # position.
        self.abs_state = [0, 0, 0, 0]

    def _map_codes_to_codes(self):
        """To quickly get target keycodes during operation."""
        _code_to_code = {}
        for (_, keycode), output in self.mapping:
            if is_this_a_macro(output):
                continue

            target_keycode = system_mapping.get(output)
            if target_keycode is None:
                logger.error('Don\'t know what %s is', output)
                continue

            _code_to_code[keycode] = target_keycode
        return _code_to_code

    def start_injecting(self):
        """Start injecting keycodes."""
        if self.stopped or self._process is not None:
            # So that there is less concern about integrity when putting
            # stuff into self. Each injector object can only be
            # started once.
            raise Exception('Please construct a new injector instead')

        if self.device not in get_devices():
            logger.error('Cannot inject for unknown device "%s"', self.device)
            return

        self._process = multiprocessing.Process(target=self._start_injecting)
        self._process.start()

    def map_abs_to_rel(self, capabilities):
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
        try:
            device = evdev.InputDevice(path)
        except FileNotFoundError:
            return None, False

        capabilities = device.capabilities(absinfo=False)

        needed = False
        for (ev_type, keycode), _ in self.mapping:
            if keycode in capabilities.get(ev_type, []):
                needed = True
                break

        abs_to_rel = self.map_abs_to_rel(capabilities)

        if abs_to_rel:
            needed = True

        if not needed:
            # skipping reading and checking on events from those devices
            # may be beneficial for performance.
            logger.debug('No need to grab %s', path)
            return None, False

        attempts = 0
        while True:
            try:
                # grab to avoid e.g. the disabled keycode of 10 to confuse
                # X, especially when one of the buttons of your mouse also
                # uses 10. This also avoids having to load an empty xkb
                # symbols file to prevent writing any unwanted keys.
                device.grab()
                logger.debug('Grab %s', path)
                break
            except IOError:
                attempts += 1
                # it might take a little time until the device is free if
                # it was previously grabbed.
                logger.debug('Failed attemts to grab %s: %d', path, attempts)

            if attempts >= 4:
                logger.error('Cannot grab %s, it is possibly in use', path)
                return None, False

            time.sleep(self.regrab_timeout)

        return device, abs_to_rel

    def _modify_capabilities(self, macros, input_device, abs_to_rel):
        """Adds all used keycodes into a copy of a devices capabilities.

        A device with those capabilities can do exactly the stuff it needs
        to perform all mappings and macros.

        Prameters
        ---------
        macros : dict
            maping of int to _Macro
        input_device : evdev.InputDevice
        abs_to_rel : bool
            if ABS capabilities should be removed in favor of REL
        """
        ecodes = evdev.ecodes

        # copy the capabilities because the uinput is going
        # to act like the device.
        capabilities = input_device.capabilities(absinfo=False)

        if len(self._code_to_code) > 0 or len(macros) > 0:
            if capabilities.get(EV_KEY) is None:
                capabilities[EV_KEY] = []

        # Furthermore, support all injected keycodes
        for keycode in self._code_to_code.values():
            if keycode not in capabilities[EV_KEY]:
                capabilities[EV_KEY].append(keycode)

        # and all keycodes that are injected by macros
        for macro in macros.values():
            capabilities[EV_KEY] += list(macro.get_capabilities())

        if abs_to_rel:
            del capabilities[EV_ABS]
            # those are the requirements to recognize it as mouse
            # on my system. REL_X and REL_Y are of course required to
            # accept the events that the mouse-movement-mapper writes.
            capabilities[EV_REL] = [
                evdev.ecodes.REL_X,
                evdev.ecodes.REL_Y,
                evdev.ecodes.REL_WHEEL,
            ]
            if capabilities.get(EV_KEY) is None:
                capabilities[EV_KEY] = []
            # for reasons I don't know, it is also required to have
            # any keyboard button in capabilities.
            capabilities[EV_KEY].append(ecodes.KEY_0)

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
        numlock_state = is_numlock_on()

        loop = asyncio.get_event_loop()
        coroutines = []

        logger.info('Starting injecting the mapping for "%s"', self.device)

        paths = get_devices()[self.device]['paths']

        # Watch over each one of the potentially multiple devices per hardware
        for path in paths:
            source, abs_to_rel = self._prepare_device(path)
            if source is None:
                continue

            # each device parses the macros with a different handler
            logger.debug('Parsing macros for %s', path)
            macros = {}
            for (_, keycode), output in self.mapping:
                if is_this_a_macro(output):
                    macro = parse(output)
                    if macro is None:
                        continue

                    macros[keycode] = macro

            # certain capabilities can have side effects apparently. with an
            # EV_ABS capability, EV_REL won't move the mouse pointer anymore.
            # so don't merge all InputDevices into one UInput device.
            uinput = evdev.UInput(
                name=f'{DEV_NAME} {self.device}',
                phys=DEV_NAME,
                events=self._modify_capabilities(macros, source, abs_to_rel)
            )

            logger.spam(
                'Injected capabilities for "%s": %s',
                path, uinput.capabilities(verbose=True)
            )

            def handler(*args, uinput=uinput):
                # this ensures that the right uinput is used for macro_write,
                # because this is within a loop
                self._macro_write(*args, uinput)

            for macro in macros.values():
                macro.set_handler(handler)

            # keycode injection
            coroutine = self._keycode_loop(macros, source, uinput, abs_to_rel)
            coroutines.append(coroutine)

            # mouse movement injection
            if abs_to_rel:
                self.abs_state[0] = 0
                self.abs_state[1] = 0
                coroutine = ev_abs_mapper(self.abs_state, source, uinput)
                coroutines.append(coroutine)

        if len(coroutines) == 0:
            logger.error('Did not grab any device')
            return

        coroutines.append(self._msg_listener(loop))

        # set the numlock state to what it was before injecting, because
        # grabbing devices screws this up
        set_numlock(numlock_state)

        try:
            loop.run_until_complete(asyncio.gather(*coroutines))
        except RuntimeError:
            # stopped event loop most likely
            pass

        if len(coroutines) > 0:
            logger.debug('asyncio coroutines ended')

    def _macro_write(self, code, value, uinput):
        """Handler for macros."""
        logger.spam('macro writes code:%s value:%d', code, value)
        uinput.write(EV_KEY, code, value)
        uinput.syn()

    async def _keycode_loop(self, macros, source, uinput, abs_to_rel):
        """Inject keycodes for one of the virtual devices.

        Can be stopped by stopping the asyncio loop.

        Parameters
        ----------
        macros : int -> _Macro
            macro with a handler that writes to the provided uinput
        source : evdev.InputDevice
            where to read keycodes from
        uinput : evdev.UInput
            where to write keycodes to
        abs_to_rel : bool
            if joystick events should be mapped to mouse movements
        """
        logger.debug(
            'Started injecting into %s, fd %s',
            uinput.device.path, uinput.fd
        )

        async for event in source.async_read_loop():
            if abs_to_rel and event.type == EV_ABS and event.code in JOYSTICK:
                if event.code == evdev.ecodes.ABS_X:
                    self.abs_state[0] = event.value
                elif event.code == evdev.ecodes.ABS_Y:
                    self.abs_state[1] = event.value
                elif event.code == evdev.ecodes.ABS_RX:
                    self.abs_state[2] = event.value
                elif event.code == evdev.ecodes.ABS_RY:
                    self.abs_state[3] = event.value
                continue

            if should_map_event_as_btn(event.type, event.code):
                handle_keycode(self._code_to_code, macros, event, uinput)
                continue

            # forward the rest
            uinput.write(event.type, event.code, event.value)
            # this already includes SYN events, so need to syn here again
            continue

        logger.error(
            'The injector for "%s" stopped early',
            uinput.device.path
        )

    @ensure_numlock
    def stop_injecting(self):
        """Stop injecting keycodes."""
        logger.info('Stopping injecting keycodes for device "%s"', self.device)
        self._msg_pipe[1].send(CLOSE)
        self.stopped = True
