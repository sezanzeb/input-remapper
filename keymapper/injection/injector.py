#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@sezanzeb.de>
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


import asyncio
import time
import multiprocessing

import evdev
from evdev.ecodes import EV_KEY, EV_REL

from keymapper.logger import logger
from keymapper.groups import classify, GAMEPAD, groups
from keymapper import utils
from keymapper.mapping import DISABLE_CODE
from keymapper.injection.keycode_mapper import KeycodeMapper
from keymapper.injection.context import Context
from keymapper.injection.event_producer import EventProducer
from keymapper.injection.numlock import set_numlock, is_numlock_on, \
    ensure_numlock


DEV_NAME = 'key-mapper'

# messages
CLOSE = 0
OK = 1

# states
UNKNOWN = -1
STARTING = 2
FAILED = 3
RUNNING = 4
STOPPED = 5

# for both states and messages
NO_GRAB = 6


def is_in_capabilities(key, capabilities):
    """Are this key or one of its sub keys in the capabilities?

    Parameters
    ----------
    key : Key
    """
    for sub_key in key:
        if sub_key[1] in capabilities.get(sub_key[0], []):
            return True

    return False


class Injector(multiprocessing.Process):
    """Keeps injecting events in the background based on mapping and config.

    Is a process to make it non-blocking for the rest of the code and to
    make running multiple injector easier. There is one process per
    hardware-device that is being mapped.
    """
    regrab_timeout = 0.5

    def __init__(self, group, mapping):
        """Setup a process to start injecting keycodes based on custom_mapping.

        Parameters
        ----------
        group : _Group
            the device group
        mapping : Mapping
        """
        self.group = group
        self._event_producer = None
        self._state = UNKNOWN
        self._msg_pipe = multiprocessing.Pipe()
        self.mapping = mapping
        self.context = None  # only needed inside the injection process
        super().__init__()

    """Functions to interact with the running process"""

    def get_state(self):
        """Get the state of the injection.

        Can be safely called from the main process.
        """
        # slowly figure out what is going on
        alive = self.is_alive()

        if self._state == UNKNOWN and not alive:
            # didn't start yet
            return self._state

        # if it is alive, it is definitely at least starting up
        if self._state == UNKNOWN and alive:
            self._state = STARTING

        # if there is a message available, it might have finished starting up
        if self._state == STARTING and self._msg_pipe[1].poll():
            msg = self._msg_pipe[1].recv()
            if msg == OK:
                self._state = RUNNING

            if msg == NO_GRAB:
                self._state = NO_GRAB

        if self._state in [STARTING, RUNNING] and not alive:
            self._state = FAILED
            logger.error('Injector was unexpectedly found stopped')

        return self._state

    @ensure_numlock
    def stop_injecting(self):
        """Stop injecting keycodes.

        Can be safely called from the main procss.
        """
        logger.info(
            'Stopping injecting keycodes for group "%s"',
            self.group.key
        )
        self._msg_pipe[1].send(CLOSE)
        self._state = STOPPED

    """Process internal stuff"""

    def _grab_device(self, path):
        """Try to grab the device, return None if not needed/possible."""
        try:
            device = evdev.InputDevice(path)
        except (FileNotFoundError, OSError):
            logger.error('Could not find "%s"', path)
            return None

        capabilities = device.capabilities(absinfo=False)

        needed = False
        for key, _ in self.context.mapping:
            if is_in_capabilities(key, capabilities):
                logger.debug('Grabbing "%s" because of "%s"', path, key)
                needed = True
                break

        gamepad = classify(device) == GAMEPAD

        if gamepad and self.context.maps_joystick():
            logger.debug('Grabbing "%s" because of maps_joystick', path)
            needed = True

        if not needed:
            # skipping reading and checking on events from those devices
            # may be beneficial for performance.
            logger.debug('No need to grab %s', path)
            return None

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
            except IOError as error:
                attempts += 1

                # it might take a little time until the device is free if
                # it was previously grabbed.
                logger.debug('Failed attempts to grab %s: %d', path, attempts)

                if attempts >= 4:
                    logger.error('Cannot grab %s, it is possibly in use', path)
                    logger.error(str(error))
                    return None

            time.sleep(self.regrab_timeout)

        return device

    def _copy_capabilities(self, input_device):
        """Copy capabilities for a new device."""
        ecodes = evdev.ecodes

        # copy the capabilities because the uinput is going
        # to act like the device.
        capabilities = input_device.capabilities(absinfo=True)

        # just like what python-evdev does in from_device
        if ecodes.EV_SYN in capabilities:
            del capabilities[ecodes.EV_SYN]
        if ecodes.EV_FF in capabilities:
            del capabilities[ecodes.EV_FF]

        if ecodes.ABS_VOLUME in capabilities.get(ecodes.EV_ABS, []):
            # For some reason an ABS_VOLUME capability likes to appear
            # for some users. It prevents mice from moving around and
            # keyboards from writing symbols
            capabilities[ecodes.EV_ABS].remove(ecodes.ABS_VOLUME)

        return capabilities

    def _construct_capabilities(self, gamepad):
        """Adds all used keycodes into a copy of a devices capabilities.

        Sometimes capabilities are a bit tricky and change how the system
        interprets the device.

        Parameters
        ----------
        gamepad : bool
            If gamepad events can be translated to mouse events. (also
            depends on the configured purpose)

        Returns
        -------
        a mapping of int event type to an array of int event codes.
        """
        ecodes = evdev.ecodes

        capabilities = {
            EV_KEY: []
        }

        # support all injected keycodes
        for code in self.context.key_to_code.values():
            if code == DISABLE_CODE:
                continue

            if code not in capabilities[EV_KEY]:
                capabilities[EV_KEY].append(code)

        # and all keycodes that are injected by macros
        for macro in self.context.macros.values():
            macro_capabilities = macro.get_capabilities()
            for ev_type in macro_capabilities:
                if len(macro_capabilities[ev_type]) == 0:
                    continue
                if ev_type not in capabilities:
                    capabilities[ev_type] = []
                capabilities[ev_type] += list(macro_capabilities[ev_type])

        if gamepad and self.context.joystick_as_mouse():
            # REL_WHEEL was also required to recognize the gamepad
            # as mouse, even if no joystick is used as wheel.
            capabilities[EV_REL] = [
                evdev.ecodes.REL_X,
                evdev.ecodes.REL_Y,
                evdev.ecodes.REL_WHEEL,
                evdev.ecodes.REL_HWHEEL,
            ]

            if capabilities.get(EV_KEY) is None:
                capabilities[EV_KEY] = []

            if ecodes.BTN_MOUSE not in capabilities[EV_KEY]:
                # to be able to move the cursor, this key capability is
                # needed
                capabilities[EV_KEY].append(ecodes.BTN_MOUSE)

        return capabilities

    async def _msg_listener(self):
        """Wait for messages from the main process to do special stuff."""
        loop = asyncio.get_event_loop()
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

    def get_udev_name(self, name, suffix):
        """Make sure the generated name is not longer than 80 chars."""
        max_len = 80  # based on error messages
        remaining_len = max_len - len(DEV_NAME) - len(suffix) - 2
        middle = name[:remaining_len]
        name = f'{DEV_NAME} {middle} {suffix}'
        return name

    def run(self):
        """The injection worker that keeps injecting until terminated.

        Stuff is non-blocking by using asyncio in order to do multiple things
        somewhat concurrently.

        Use this function as starting point in a process. It creates
        the loops needed to read and map events and keeps running them.
        """
        logger.info('Starting injecting the mapping for "%s"', self.group.key)

        # create a new event loop, because somehow running an infinite loop
        # that sleeps on iterations (event_producer) in one process causes
        # another injection process to screw up reading from the grabbed
        # device.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # create this within the process after the event loop creation,
        # so that the macros use the correct loop
        self.context = Context(self.mapping)

        self._event_producer = EventProducer(self.context)

        numlock_state = is_numlock_on()
        coroutines = []

        # where mapped events go to.
        # See the Context docstring on why this is needed.
        self.context.uinput = evdev.UInput(
            name=self.get_udev_name(self.group.key, 'mapped'),
            phys=DEV_NAME,
            events=self._construct_capabilities(GAMEPAD in self.group.types)
        )

        # Watch over each one of the potentially multiple devices per hardware
        for path in self.group.paths:
            source = self._grab_device(path)
            if source is None:
                # this path doesn't need to be grabbed for injection, because
                # it doesn't provide the events needed to execute the mapping
                continue

            # certain capabilities can have side effects apparently. with an
            # EV_ABS capability, EV_REL won't move the mouse pointer anymore.
            # so don't merge all InputDevices into one UInput device.
            gamepad = classify(source) == GAMEPAD
            forward_to = evdev.UInput(
                name=self.get_udev_name(source.name, 'forwarded'),
                phys=DEV_NAME,
                events=self._copy_capabilities(source)
            )

            # actual reading of events
            coroutines.append(self._event_consumer(source, forward_to))

            # The event source of the current iteration will deliver events
            # that are needed for this. It is that one that will be mapped
            # to a mouse-like devnode.
            if gamepad and self.context.joystick_as_mouse():
                self._event_producer.set_abs_range_from(source)

        if len(coroutines) == 0:
            logger.error('Did not grab any device')
            self._msg_pipe[0].send(NO_GRAB)
            return

        coroutines.append(self._msg_listener())

        # run besides this stuff
        coroutines.append(self._event_producer.run())

        # set the numlock state to what it was before injecting, because
        # grabbing devices screws this up
        set_numlock(numlock_state)

        self._msg_pipe[0].send(OK)

        try:
            loop.run_until_complete(asyncio.gather(*coroutines))
        except RuntimeError:
            # stopped event loop most likely
            pass
        except OSError as error:
            logger.error(str(error))

        if len(coroutines) > 0:
            # expected when stop_injecting is called,
            # during normal operation as well as tests this point is not
            # reached otherwise.
            logger.debug('asyncio coroutines ended')

    async def _event_consumer(self, source, forward_to):
        """Reads input events to inject keycodes or talk to the event_producer.

        Can be stopped by stopping the asyncio loop. This loop
        reads events from a single device only. Other devnodes may be
        present for the hardware device, in which case this needs to be
        started multiple times.

        Parameters
        ----------
        source : evdev.InputDevice
            where to read keycodes from
        forward_to : evdev.UInput
            where to write keycodes to that were not mapped to anything.
            Should be an UInput with capabilities that work for all forwarded
            events, so ideally they should be copied from source.
        """
        logger.debug(
            'Started consumer to inject to %s, fd %s',
            source.path, source.fd
        )

        gamepad = classify(source) == GAMEPAD

        keycode_handler = KeycodeMapper(self.context, source, forward_to)

        async for event in source.async_read_loop():
            if self._event_producer.is_handled(event):
                # the event_producer will take care of it
                self._event_producer.notify(event)
                continue

            # for mapped stuff
            if utils.should_map_as_btn(event, self.context.mapping, gamepad):
                will_report_key_up = utils.will_report_key_up(event)

                keycode_handler.handle_keycode(event)

                if not will_report_key_up:
                    # simulate a key-up event if no down event arrives anymore.
                    # this may release macros, combinations or keycodes.
                    release = evdev.InputEvent(0, 0, event.type, event.code, 0)
                    self._event_producer.debounce(
                        debounce_id=(event.type, event.code, event.value),
                        func=keycode_handler.handle_keycode,
                        args=(release, False),
                        ticks=3,
                    )

                continue

            # forward the rest
            forward_to.write(event.type, event.code, event.value)
            # this already includes SYN events, so need to syn here again

        # This happens all the time in tests because the async_read_loop
        # stops when there is nothing to read anymore. Otherwise tests
        # would block.
        logger.error('The consumer for "%s" stopped early', source.path)
