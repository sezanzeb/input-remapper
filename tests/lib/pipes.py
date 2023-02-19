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

"""Reading events from fixtures, making fixtures act like they are sending events."""

from __future__ import annotations

import multiprocessing
from multiprocessing.connection import Connection
from typing import Dict, Tuple

from tests.lib.fixtures import Fixture
from tests.lib.logger import logger

uinput_write_history = []
# for tests that makes the injector create its processes
uinput_write_history_pipe = multiprocessing.Pipe()
pending_events: Dict[Fixture, Tuple[Connection, Connection]] = {}


def read_write_history_pipe():
    """Convert the write history from the pipe to some easier to manage list."""
    history = []
    while uinput_write_history_pipe[0].poll():
        event = uinput_write_history_pipe[0].recv()
        history.append((event.type, event.code, event.value))
    return history


def setup_pipe(fixture: Fixture):
    """Create a pipe that can be used to send events to the reader-service,
    which in turn will be sent to the reader-client
    """
    if pending_events.get(fixture) is None:
        pending_events[fixture] = multiprocessing.Pipe()


def get_events():
    """Get all events written by the injector."""
    return uinput_write_history


def push_event(fixture: Fixture, event, force: bool = False):
    """Make a device act like it is reading events from evdev.

    push_event is like hitting a key on a keyboard for stuff that reads from
    evdev.InputDevice (which is patched in test.py to work that way)

    Parameters
    ----------
    fixture
        For example 'Foo Device'
    event
        The InputEvent to send
    force
        don't check if the event is in fixture.capabilities
    """
    setup_pipe(fixture)
    if not force and (
        not fixture.capabilities.get(event.type)
        or event.code not in fixture.capabilities[event.type]
    ):
        raise AssertionError(f"Fixture {fixture.path} cannot send {event}")
    logger.info("Simulating %s for %s", event, fixture.path)
    pending_events[fixture][0].send(event)


def push_events(fixture: Fixture, events, force=False):
    """Push multiple events."""
    for event in events:
        push_event(fixture, event, force)
