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
from keymapper.groups import classify, GAMEPAD
from keymapper.mapping import DISABLE_CODE
from keymapper.injection.context import Context
from keymapper.injection.numlock import set_numlock, is_numlock_on, ensure_numlock
from keymapper.injection.consumer_control import ConsumerControl
from keymapper.injection.device_factory import DEV_NAME


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


def create_keyboard(name):
    """Create an uinput that can be used like a keyboard."""
    return evdev.UInput(
        name=f"key-mapper {name} keyboard",
        phys=DEV_NAME,
        events={
            evdev.ecodes.EV_KEY: evdev.ecodes.keys.keys()
        },
    )


def get_udev_name(name, suffix):
    """Make sure the generated name is not longer than 80 chars."""
    max_len = 80  # based on error messages
    remaining_len = max_len - len(DEV_NAME) - len(suffix) - 2
    middle = name[:remaining_len]
    name = f"{DEV_NAME} {middle} {suffix}"
    return name


class Injector(multiprocessing.Process):
    """Initializes, starts and stops injections.

    Is a process to make it non-blocking for the rest of the code and to
    make running multiple injector easier. There is one process per
    hardware-device that is being mapped.
    """

    regrab_timeout = 0.2

    def __init__(self, group, mapping):
        """

        Parameters
        ----------
        group : _Group
            the device group
        mapping : Mapping
        """
        self.group = group
        self._state = UNKNOWN

        # used to interact with the parts of this class that are running within
        # the new process
        self._msg_pipe = multiprocessing.Pipe()

        self.mapping = mapping
        self.context = None  # only needed inside the injection process

        self._consumer_controls = []

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
            logger.error("Injector was unexpectedly found stopped")

        return self._state

    @ensure_numlock
    def stop_injecting(self):
        """Stop injecting keycodes.

        Can be safely called from the main procss.
        """
        logger.info('Stopping injecting keycodes for group "%s"', self.group.key)
        self._msg_pipe[1].send(CLOSE)
        self._state = STOPPED

    """Process internal stuff"""

    def _grab_devices(self):
        """Grab all devices that are needed for the injection."""
        sources = []
        for path in self.group.paths:
            source = self._grab_device(path)
            if source is None:
                # this path doesn't need to be grabbed for injection, because
                # it doesn't provide the events needed to execute the mapping
                continue
            sources.append(source)

        return sources

    def _grab_device(self, path):
        """Try to grab the device, return None if not needed/possible.

        Without grab, original events from it would reach the display server
        even though they are mapped.
        """
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
            logger.debug("No need to grab %s", path)
            return None

        attempts = 0
        while True:
            try:
                device.grab()
                logger.debug("Grab %s", path)
                break
            except IOError as error:
                attempts += 1

                # it might take a little time until the device is free if
                # it was previously grabbed.
                logger.debug("Failed attempts to grab %s: %d", path, attempts)

                if attempts >= 10:
                    logger.error("Cannot grab %s, it is possibly in use", path)
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

    def _construct_capabilities(self):
        """Adds all used keycodes into a copy of a devices capabilities.

        Sometimes capabilities are a bit tricky and change how the system
        interprets the device.

        Returns
        -------
        a mapping of int event type to an array of int event codes.
        """
        ecodes = evdev.ecodes

        capabilities = {EV_KEY: []}

        # all keycodes that are injected by macros that are not EV_KEY
        for macro in self.context.macros.values():
            macro_capabilities = macro.get_capabilities()
            for ev_type in macro_capabilities:
                if ev_type == EV_KEY:
                    continue

                if len(macro_capabilities[ev_type]) == 0:
                    continue

                if ev_type not in capabilities:
                    capabilities[ev_type] = []

                capabilities[ev_type] += list(macro_capabilities[ev_type])

        gamepad = GAMEPAD in self.group.types
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
                logger.debug("Received close signal")
                # stop the event loop and cause the process to reach its end
                # cleanly. Using .terminate prevents coverage from working.
                loop.stop()
                return

    def run(self):
        """The injection worker that keeps injecting until terminated.

        Stuff is non-blocking by using asyncio in order to do multiple things
        somewhat concurrently.

        Use this function as starting point in a process. It creates
        the loops needed to read and map events and keeps running them.
        """
        # TODO run all injections in a single process via asyncio
        #   - Make sure that closing asyncio fds won't lag the service
        #   - SharedDict becomes obsolete
        #   - quick_cleanup needs to be able to reliably stop the injection
        #   - I think I want an event listener architecture so that macros,
        #     joystick_to_mouse, keycode_mapper and possibly other modules can get
        #     what they filter for whenever they want, without having to wire
        #     things through multiple other objects all the time
        #   - _new_event_arrived moves to the place where events are emitted. injector?
        #   - active macros and unreleased need to be per injection. it probably
        #     should move into the keycode_mapper class, but that only works if there
        #     is only one keycode_mapper per injection, and not per source. Problem was
        #     that I had to excessively pass around to which device to forward to...
        #     I also need to have information somewhere which source is a gamepad, I
        #     probably don't want to evaluate that from scratch each time `notify` is
        #     called.
        #   - benefit: writing macros that listen for events from other devices

        logger.info('Starting injecting the mapping for "%s"', self.group.key)

        # create a new event loop, because somehow running an infinite loop
        # that sleeps on iterations (joystick_to_mouse) in one process causes
        # another injection process to screw up reading from the grabbed
        # device.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # create this within the process after the event loop creation,
        # so that the macros use the correct loop
        self.context = Context(self.mapping)

        # grab devices as early as possible. If events appear that won't get
        # released anymore before the grab they appear to be held down
        # forever
        sources = self._grab_devices()

        if len(sources) == 0:
            logger.error("Did not grab any device")
            self._msg_pipe[0].send(NO_GRAB)
            return

        numlock_state = is_numlock_on()
        coroutines = []

        # where mapped events go to.
        # See the Context docstring on why this is needed.
        self.context.uinput = evdev.UInput(
            name=get_udev_name(self.group.key, "mapped"),
            phys=DEV_NAME,
            events=self._construct_capabilities(),
        )

        self.context.keyboard = create_keyboard(self.group.key)

        for source in sources:
            # certain capabilities can have side effects apparently. with an
            # EV_ABS capability, EV_REL won't move the mouse pointer anymore.
            # so don't merge all InputDevices into one UInput device.
            forward_to = evdev.UInput(
                name=get_udev_name(source.name, "forwarded"),
                phys=DEV_NAME,
                events=self._copy_capabilities(source),
                input_props=source.input_props()  # TODO test
            )

            # actually doing things
            consumer_control = ConsumerControl(self.context, source, forward_to)
            coroutines.append(consumer_control.run())
            self._consumer_controls.append(consumer_control)

        coroutines.append(self._msg_listener())

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
            logger.error("Failed to run injector coroutines: %s", str(error))

        if len(coroutines) > 0:
            # expected when stop_injecting is called,
            # during normal operation as well as tests this point is not
            # reached otherwise.
            logger.debug("Injector coroutines ended")

        for source in sources:
            # ungrab at the end to make the next injection process not fail
            # its grabs
            try:
                source.ungrab()
            except OSError as error:
                # it might have disappeared
                logger.debug("OSError for ungrab on %s: %s", source.path, str(error))
