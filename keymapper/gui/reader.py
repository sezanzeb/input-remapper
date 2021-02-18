#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@hip70890b.de>
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
import time
import select
import multiprocessing
import threading

import evdev
from evdev.ecodes import EV_KEY, EV_ABS, ABS_MISC, EV_REL

from keymapper.logger import logger
from keymapper.key import Key
from keymapper.state import custom_mapping
from keymapper.getdevices import get_devices, is_gamepad
from keymapper import utils

CLOSE = 1

PRIORITIES = {
    EV_KEY: 100,
    EV_ABS: 50,
}

FILTER_THRESHOLD = 0.01

DEBOUNCE_TICKS = 3


def prioritize(events):
    """Return the event that is most likely desired to be mapped.

    KEY over ABS and everything over ABS_MISC.
    """
    events = [
        event for event in events
        if event is not None
    ]
    return sorted(events, key=lambda e: (
        PRIORITIES.get(e.type, 0),
        not (e.type == EV_ABS and e.code == ABS_MISC),
        abs(e.value)
    ))[-1]


def will_report_up(ev_type):
    """Check if this event will ever report a key up (wheels)."""
    return ev_type != EV_REL


def event_unix_time(event):
    """Get the unix timestamp of an event."""
    if event is None:
        return 0
    return event.sec + event.usec / 1000000


class _KeycodeReader:
    """Keeps reading keycodes in the background for the UI to use.

    Does not serve any purpose for the injection service.

    When a button was pressed, the newest keycode can be obtained from this
    object. GTK has get_key for keyboard keys, but KeycodeReader also
    has knowledge of buttons like the middle-mouse button.
    """
    def __init__(self):
        self.virtual_devices = []
        self._pipe = None
        self._process = None
        self.fail_counter = 0
        self.previous_event = None
        self.previous_result = None
        self._unreleased = {}
        self._debounce_remove = {}

    def __del__(self):
        self.stop_reading()

    def stop_reading(self):
        """Stop reading keycodes."""
        if self._pipe is not None:
            logger.debug('Sending close msg to reader')
            self._pipe[0].send(CLOSE)
            self._pipe = None

    def clear(self):
        """Next time when reading don't return the previous keycode."""
        # just call read to clear the pipe
        self.read()
        self._unreleased = {}
        self.previous_event = None
        self.previous_result = None

    def start_reading(self, device_name):
        """Tell the evdev lib to start looking for keycodes.

        If read is called without prior start_reading, no keycodes
        will be available.

        Parameters
        ----------
        device_name : string
            As indexed in get_devices()
        """
        if self._pipe is not None:
            self.stop_reading()
            time.sleep(0.1)

        self.virtual_devices = []

        group = get_devices()[device_name]

        # Watch over each one of the potentially multiple devices per hardware
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
        self._process = threading.Thread(target=self._read_worker)
        self._process.start()

    def _pipe_event(self, event, device, gamepad):
        """Write the event into the pipe to the main process.

        Parameters
        ----------
        event : evdev.InputEvent
        device : evdev.InputDevice
        gamepad : bool
            If true, ABS_X and ABS_Y might be mapped to buttons as well
            depending on the purpose configuration
        """
        # value: 1 for down, 0 for up, 2 for hold.
        if self._pipe is None or self._pipe[1].closed:
            logger.debug('Pipe closed, reader stops.')
            sys.exit(0)

        if event.type == EV_KEY and event.value == 2:
            # ignore hold-down events
            return

        click_events = [
            evdev.ecodes.BTN_LEFT,
            evdev.ecodes.BTN_TOOL_DOUBLETAP
        ]

        if event.type == EV_KEY and event.code in click_events:
            # disable mapping the left mouse button because it would break
            # the mouse. Also it is emitted right when focusing the row
            # which breaks the current workflow.
            return

        if not utils.should_map_as_btn(event, custom_mapping, gamepad):
            return

        max_abs = utils.get_max_abs(device)
        event.value = utils.normalize_value(event, max_abs)

        self._pipe[1].send(event)

    def _read_worker(self):
        """Thread that reads keycodes and buffers them into a pipe."""
        # using a thread that blocks instead of read_one made it easier
        # to debug via the logs, because the UI was not polling properly
        # at some point which caused logs for events not to be written.
        rlist = {}
        gamepad = {}
        for device in self.virtual_devices:
            rlist[device.fd] = device
            gamepad[device.fd] = is_gamepad(device)

        rlist[self._pipe[1]] = self._pipe[1]

        while True:
            ready = select.select(rlist, [], [])[0]
            for fd in ready:
                readable = rlist[fd]  # an InputDevice or a pipe
                if isinstance(readable, multiprocessing.connection.Connection):
                    msg = readable.recv()
                    if msg == CLOSE:
                        logger.debug('Reader stopped')
                        return
                    continue

                try:
                    for event in rlist[fd].read():
                        self._pipe_event(
                            event,
                            readable,
                            gamepad.get(fd, False)
                        )
                except OSError:
                    logger.debug(
                        'Device "%s" disappeared from the reader',
                        rlist[fd].path
                    )
                    del rlist[fd]

    def get_unreleased_keys(self):
        """Get a Key object of the current keyboard state."""
        unreleased = list(self._unreleased.values())

        if len(unreleased) == 0:
            return None

        return Key(*unreleased)

    def _release(self, type_code):
        """Modify the state to recognize the releasing of the key."""
        if type_code in self._unreleased:
            del self._unreleased[type_code]
        if type_code in self._debounce_remove:
            del self._debounce_remove[type_code]

    def _debounce_start(self, event_tuple):
        """Act like the key was released if no new event arrives in time."""
        if not will_report_up(event_tuple[0]):
            self._debounce_remove[event_tuple[:2]] = DEBOUNCE_TICKS

    def _debounce_tick(self):
        """If the counter reaches 0, the key is not considered held down."""
        for type_code in list(self._debounce_remove.keys()):
            if type_code not in self._unreleased:
                continue

            # clear wheel events from unreleased after some time
            if self._debounce_remove[type_code] == 0:
                logger.key_spam(
                    self._unreleased[type_code],
                    'Considered as released'
                )
                self._release(type_code)
            else:
                self._debounce_remove[type_code] -= 1

    def read(self):
        """Get the newest key/combination as Key object.

        Only reports keys from down-events.

        On key-down events the pipe returns changed combinations. Release
        events won't cause that and the reader will return None as in
        "nothing new to report". So In order to change a combination, one
        of its keys has to be released and then a different one pressed.

        Otherwise making combinations wouldn't be possible. Because at
        some point the keys have to be released, and that shouldn't cause
        the combination to get trimmed.

        If the timing of two recent events is very close, prioritize
        key events over abs events.
        """
        # this is in some ways similar to the keycode_mapper and
        # event_producer, but its much simpler because it doesn't
        # have to trigger anything, manage any macros and only
        # reports key-down events. This function is called periodically
        # by the window.
        if self._pipe is None:
            self.fail_counter += 1
            if self.fail_counter % 10 == 0:  # spam less
                logger.debug('No pipe available to read from')
            return None

        # remember the prevous down-event from the pipe in order to
        # be able to prioritize events, and to be able to tell if the reader
        # should return the updated combination
        previous_event = self.previous_event
        key_down_received = False

        self._debounce_tick()

        while self._pipe[0].poll():
            # loop over all new and unhandled events
            event = self._pipe[0].recv()
            event_tuple = (event.type, event.code, event.value)
            type_code = (event.type, event.code)

            if event.value == 0:
                logger.key_spam(event_tuple, 'release')
                self._release(type_code)
                continue

            if self._unreleased.get(type_code) == event_tuple:
                logger.key_spam(event_tuple, 'duplicate key down')
                self._debounce_start(event_tuple)
                continue

            delta = event_unix_time(event) - event_unix_time(previous_event)
            if delta < FILTER_THRESHOLD:
                if prioritize([previous_event, event]) == previous_event:
                    # two events happened very close, probably some weird
                    # spam from the device. The wacom intuos 5 adds an
                    # ABS_MISC event to every button press, filter that out
                    logger.key_spam(event_tuple, 'ignoring new event')
                    continue

                # the previous event of the previous iteration is ignored.
                # clean stuff up to remove its side effects
                prev_tuple = (
                    previous_event.type,
                    previous_event.code,
                    previous_event.value
                )
                if prev_tuple[:2] in self._unreleased:
                    logger.key_spam(
                        event_tuple,
                        'ignoring previous event %s', prev_tuple
                    )
                    self._release(prev_tuple[:2])

            # to keep track of combinations.
            # "I have got this release event, what was this for?" A release
            # event for a D-Pad axis might be any direction, hence this maps
            # from release to input in order to remember it. Since all release
            # events have value 0, the value is not used in the key.
            key_down_received = True
            logger.key_spam(event_tuple, 'down')
            self._unreleased[type_code] = event_tuple
            self._debounce_start(event_tuple)
            previous_event = event

        if not key_down_received:
            # This prevents writing a subset of the combination into
            # result after keys were released. In order to control the gui,
            # they have to be released.
            return None

        self.previous_event = previous_event

        if len(self._unreleased) > 0:
            result = Key(*self._unreleased.values())
            if result == self.previous_result:
                # don't return the same stuff twice
                return None

            self.previous_result = result
            logger.key_spam(result.keys, 'read result')

            return result

        return None


keycode_reader = _KeycodeReader()
