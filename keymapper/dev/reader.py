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
import select
import multiprocessing
import threading

import evdev
from evdev.ecodes import EV_KEY, EV_ABS, ABS_MISC

from keymapper.logger import logger
from keymapper.key import Key
from keymapper.state import custom_mapping
from keymapper.getdevices import get_devices, refresh_devices
from keymapper.dev import utils


CLOSE = 1

PRIORITIES = {
    EV_KEY: 100,
    EV_ABS: 50,
}

FILTER_THRESHOLD = 0.01


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
        self.newest_event = None
        # to keep track of combinations.
        # "I have got this release event, what was this for?"
        # A release event for a D-Pad axis might be any direction, hence
        # this maps from release to input in order to remember it.
        self._unreleased = {}

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

    def start_reading(self, device_name):
        """Tell the evdev lib to start looking for keycodes.

        If read is called without prior start_reading, no keycodes
        will be available.
        """
        self.stop_reading()

        # make sure this sees up to date devices, including those created
        # by key-mapper
        refresh_devices()

        self.virtual_devices = []

        for name, group in get_devices().items():
            if device_name not in name:
                continue

            # Watch over each one of the potentially multiple devices per
            # hardware
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

    def _consume_event(self, event, device):
        """Write the event code into the pipe if it is a key-down press."""
        # value: 1 for down, 0 for up, 2 for hold.
        if self._pipe is None or self._pipe[1].closed:
            logger.debug('Pipe closed, reader stops.')
            sys.exit(0)

        click_events = [
            evdev.ecodes.BTN_LEFT,
            evdev.ecodes.BTN_TOOL_DOUBLETAP
        ]

        if event.type == EV_KEY and event.value == 2:
            # ignore hold-down events
            return

        if event.type == EV_KEY and event.code in click_events:
            # disable mapping the left mouse button because it would break
            # the mouse. Also it is emitted right when focusing the row
            # which breaks the current workflow.
            return

        if not utils.should_map_event_as_btn(device, event, custom_mapping):
            return

        if not (event.value == 0 and event.type == EV_ABS):
            # avoid gamepad trigger spam
            logger.spam(
                'got (%s, %s, %s)',
                event.type,
                event.code,
                event.value
            )
        self._pipe[1].send(event)

    def _read_worker(self):
        """Thread that reads keycodes and buffers them into a pipe."""
        # using a thread that blocks instead of read_one made it easier
        # to debug via the logs, because the UI was not polling properly
        # at some point which caused logs for events not to be written.
        rlist = {device.fd: device for device in self.virtual_devices}
        rlist[self._pipe[1]] = self._pipe[1]

        while True:
            ready = select.select(rlist, [], [])[0]
            for fd in ready:
                readable = rlist[fd]  # a device or a pipe
                if isinstance(readable, multiprocessing.connection.Connection):
                    msg = readable.recv()
                    if msg == CLOSE:
                        logger.debug('Reader stopped')
                        return
                    continue

                try:
                    for event in rlist[fd].read():
                        self._consume_event(event, readable)
                except OSError:
                    logger.debug(
                        'Device "%s" disappeared from the reader',
                        rlist[fd].path
                    )
                    del rlist[fd]

    def are_keys_pressed(self):
        """Check if any keys currently pressed down."""
        return len(self._unreleased) > 0

    def read(self):
        """Get the newest key as Key object

        If the timing of two recent events is very close, prioritize
        key events over abs events.
        """
        if self._pipe is None:
            self.fail_counter += 1
            if self.fail_counter % 10 == 0:
                # spam less
                logger.debug('No pipe available to read from')
            return None

        newest_event = self.newest_event
        newest_time = (
            0 if newest_event is None
            else newest_event.sec + newest_event.usec / 1000000
        )

        while self._pipe[0].poll():
            event = self._pipe[0].recv()
            event_tuple = (event.type, event.code, event.value)
            without_value = (event.type, event.code)

            if event.value == 0:
                if without_value in self._unreleased:
                    del self._unreleased[without_value]
                continue

            if self._unreleased.get(without_value) == event_tuple:
                # no duplicate down events (gamepad triggers)
                continue

            time = event.sec + event.usec / 1000000
            delta = time - newest_time

            if delta < FILTER_THRESHOLD:
                if prioritize([newest_event, event]) != event:
                    # two events happened very close, probably some weird
                    # spam from the device. The wacom intuos 5 adds an
                    # ABS_MISC event to every button press, filter that out
                    logger.spam(
                        'Ignoring event (%s, %s, %s)',
                        event.type, event.code, event.value
                    )
                    continue

                # the previous event is ignored
                previous_without_value = (newest_event.type, newest_event.code)
                if previous_without_value in self._unreleased:
                    del self._unreleased[previous_without_value]

            self._unreleased[without_value] = (
                event.type,
                event.code,
                event.value
            )

            newest_event = event
            newest_time = time

        if newest_event == self.newest_event:
            # don't return the same event twice
            return None

        self.newest_event = newest_event

        if len(self._unreleased) > 0:
            return Key(*self._unreleased.values())

        # nothing
        return None


keycode_reader = _KeycodeReader()
