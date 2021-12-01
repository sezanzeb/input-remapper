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


"""Consumer base class.

Can be notified of new events so that inheriting classes can map them and
inject new events based on them.
"""


import evdev


class Consumer:
    """Can be notified of new events to inject them. Base class."""

    def __init__(self, context, source, forward_to=None):
        """Initialize event consuming functionality.

        Parameters
        ----------
        context : Context
            The configuration of the Injector process
        source : InputDevice
            Where events used in handle_keycode come from
        forward_to : evdev.UInput
            Where to write keycodes to that were not mapped to anything.
            Should be an UInput with capabilities that work for all forwarded
            events, so ideally they should be copied from source.
        """
        self.context = context
        self.forward_to = forward_to
        self.source = source
        self.context.update_purposes()

    def is_enabled(self):
        """Check if the consumer will have work to do."""
        raise NotImplementedError

    def write(self, key):
        """Shorthand to write stuff."""
        self.context.keyboard.write(*key)
        self.context.keyboard.syn()

    def forward(self, key):
        """Shorthand to forward an event."""
        uinput = self.forward_to

        code = key[1]
        if code in evdev.ecodes.KEY:
            # This is really important to not cause confusion with modifiers for the
            # environment. E.g. having a macro that releases a modifier that has
            # previously been injected, but has not been mapped. Instead of putting
            # the first one into the "mapped" device and the other one into the
            # "forwarded" device, all of them go into the same device.
            # But not BTN_LEFT and such, those can be safely forwarded. Also, they are
            # not really keyboard events even though being of the EV_KEY events.
            uinput = self.context.keyboard

        uinput.write(*key)
        uinput.syn()

    async def notify(self, event):
        """A new event is ready.

        Overwrite this function if the consumer should do something each time
        a new event arrives. E.g. mapping a single button once clicked.
        """
        raise NotImplementedError

    def is_handled(self, event):
        """Check if the consumer will take care of this event.

        If this returns true, the event will not be forwarded anymore
        automatically. If you want to forward the event after all you can
        inject it into `self.forward_to`.
        """
        raise NotImplementedError

    async def run(self):
        """Start doing things.

        Overwrite this function if the consumer should do something
        continuously even if no new event arrives. e.g. continuously injecting
        mouse movement events.
        """
        raise NotImplementedError
