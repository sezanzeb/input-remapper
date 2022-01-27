#!/usr/bin/python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2022 sezanzeb <proxima@sezanzeb.de>
#
# This file is part of input-remapper.
#
# input-remapper is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# input-remapper is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with input-remapper.  If not, see <https://www.gnu.org/licenses/>.


"""Talking to the GUI helper that has root permissions.

see gui.helper.helper
"""


import evdev
from evdev.ecodes import EV_REL

from inputremapper.logger import logger
from inputremapper.event_combination import EventCombination
from inputremapper.groups import groups, GAMEPAD
from inputremapper.ipc.pipe import Pipe
from inputremapper.gui.helper import TERMINATE, REFRESH_GROUPS
from inputremapper import utils
from inputremapper.gui.active_preset import active_preset
from inputremapper.user import USER


DEBOUNCE_TICKS = 3


def will_report_up(ev_type):
    """Check if this event will ever report a key up (wheels)."""
    return ev_type != EV_REL


class Reader:
    """Processes events from the helper for the GUI to use.

    Does not serve any purpose for the injection service.

    When a button was pressed, the newest keycode can be obtained from this
    object. GTK has get_key for keyboard keys, but Reader also
    has knowledge of buttons like the middle-mouse button.
    """

    def __init__(self):
        self.previous_event = None
        self.previous_result = None
        self._unreleased = {}
        self._debounce_remove = {}
        self._groups_updated = False
        self._cleared_at = 0
        self.group = None

        self._results = None
        self._commands = None
        self.connect()

    def connect(self):
        """Connect to the helper."""
        self._results = Pipe(f"/tmp/input-remapper-{USER}/results")
        self._commands = Pipe(f"/tmp/input-remapper-{USER}/commands")

    def are_new_groups_available(self):
        """Check if groups contains new devices.

        The ui should then update its list.
        """
        outdated = self._groups_updated
        self._groups_updated = False  # assume the ui will react accordingly
        return outdated

    def _get_event(self, message):
        """Return an InputEvent if the message contains one. None otherwise."""
        message_type = message["type"]
        message_body = message["message"]

        if message_type == "groups":
            if message_body != groups.dumps():
                groups.loads(message_body)
                logger.debug("Received %d devices", len(groups))
                self._groups_updated = True
            return None

        if message_type == "event":
            return evdev.InputEvent(*message_body)

        logger.error('Received unknown message "%s"', message)
        return None

    def read(self):
        """Get the newest key/combination as EventCombination object.

        Only reports keys from down-events.

        On key-down events the pipe returns changed combinations. Release
        events won't cause that and the reader will return None as in
        "nothing new to report". So In order to change a combination, one
        of its keys has to be released and then a different one pressed.

        Otherwise making combinations wouldn't be possible. Because at
        some point the keys have to be released, and that shouldn't cause
        the combination to get trimmed.
        """
        # this is in some ways similar to the keycode_mapper and
        # joystick_to_mouse, but its much simpler because it doesn't
        # have to trigger anything, manage any macros and only
        # reports key-down events. This function is called periodically
        # by the window.

        # remember the previous down-event from the pipe in order to
        # be able to tell if the reader should return the updated combination
        previous_event = self.previous_event
        key_down_received = False

        self._debounce_tick()

        while self._results.poll():
            message = self._results.recv()
            event = self._get_event(message)
            if event is None:
                continue

            gamepad = GAMEPAD in self.group.types
            if not utils.should_map_as_btn(event, active_preset, gamepad):
                continue

            event_tuple = (event.type, event.code, event.value)

            type_code = (event.type, event.code)

            if event.value == 0:
                logger.debug_key(event_tuple, "release")
                self._release(type_code)
                continue

            if self._unreleased.get(type_code) == event_tuple:
                logger.debug_key(event_tuple, "duplicate key down")
                self._debounce_start(event_tuple)
                continue

            # to keep track of combinations.
            # "I have got this release event, what was this for?" A release
            # event for a D-Pad axis might be any direction, hence this maps
            # from release to input in order to remember it. Since all release
            # events have value 0, the value is not used in the combination.
            key_down_received = True
            logger.debug_key(event_tuple, "down")
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
            result = EventCombination(*self._unreleased.values())
            if result == self.previous_result:
                # don't return the same stuff twice
                return None

            self.previous_result = result
            logger.debug_key(result.keys, "read result")

            return result

        return None

    def start_reading(self, group):
        """Start reading keycodes for a device."""
        logger.debug('Sending start msg to helper for "%s"', group.key)
        self._commands.send(group.key)
        self.group = group
        self.clear()

    def terminate(self):
        """Stop reading keycodes for good."""
        logger.debug("Sending close msg to helper")
        self._commands.send(TERMINATE)

    def refresh_groups(self):
        """Ask the helper for new device groups."""
        self._commands.send(REFRESH_GROUPS)

    def clear(self):
        """Next time when reading don't return the previous keycode."""
        logger.debug("Clearing reader")
        while self._results.poll():
            # clear the results pipe and handle any non-event messages,
            # otherwise a 'groups' message might get lost
            message = self._results.recv()
            self._get_event(message)

        self._unreleased = {}
        self.previous_event = None
        self.previous_result = None

    def get_unreleased_keys(self):
        """Get a EventCombination object of the current keyboard state."""
        unreleased = list(self._unreleased.values())

        if len(unreleased) == 0:
            return None

        return EventCombination(*unreleased)

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
                logger.debug_key(self._unreleased[type_code], "Considered as released")
                self._release(type_code)
            else:
                self._debounce_remove[type_code] -= 1


reader = Reader()
