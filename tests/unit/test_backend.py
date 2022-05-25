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
import unittest
from typing import List, Dict, Any

import gi

gi.require_version("GLib", "2.0")
from gi.repository import GLib

from inputremapper.groups import _Groups
from inputremapper.gui.event_handler import EventHandler, EventEnum
from inputremapper.gui.reader import Reader
from inputremapper.injection.global_uinputs import GlobalUInputs
from tests.test import quick_cleanup, get_backend, push_events


class Listener:
    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)


class TestBackend(unittest.TestCase):
    def setUp(self) -> None:
        self.event_handler = EventHandler()

    def tearDown(self) -> None:
        quick_cleanup()

    def test_should_provide_groups(self):
        event_handler = EventHandler()
        groups = _Groups()
        backend = get_backend(reader=Reader(event_handler, groups))
        self.assertIs(backend.groups, groups)

    def test_should_emit_groups(self):
        event_handler = EventHandler()
        backend = get_backend(
            event_handler=event_handler, reader=Reader(event_handler, _Groups())
        )
        listener = Listener()
        event_handler.subscribe(EventEnum.groups_changed, listener)

        backend.emit_groups()
        emitted = listener.calls[0]

        # we expect a list of tuples with the group key and their device types
        self.assertEqual(
            emitted,
            {
                "groups": [
                    ("Foo Device", ["keyboard"]),
                    ("Foo Device 2", ["gamepad", "keyboard", "mouse"]),
                    ("Bar Device", ["keyboard"]),
                    ("gamepad", ["gamepad"]),
                ]
            },
        )

    def test_should_set_active_group(self):
        event_handler = EventHandler()
        groups = _Groups()
        backend = get_backend(reader=Reader(event_handler, groups))
        group = groups.find(key="Foo Device 2")

        backend.set_active_group("Foo Device 2")
        self.assertIs(backend.active_group, group)

    def test_should_start_reading_active_group(self):
        reader = Reader(EventHandler(), _Groups())
        backend = get_backend(reader=reader)

        def f(*_):
            raise AssertionError()

        reader.set_group = f

        self.assertRaises(AssertionError, backend.set_active_group, "Foo Device")

    def test_should_emit_uinputs(self):
        event_handler = EventHandler()
        uinputs = GlobalUInputs()
        uinputs.prepare_all()
        backend = get_backend(
            event_handler=event_handler, reader=Reader(event_handler, _Groups())
        )
        listener = Listener()
        event_handler.subscribe(EventEnum.uinputs_changed, listener)

        backend.emit_uinputs()
        emitted = listener.calls[0]

        # we expect a list of tuples with the group key and their device types
        self.assertEqual(
            emitted,
            {
                "uinputs": {
                    "gamepad": uinputs.get_uinput("gamepad").capabilities(),
                    "keyboard": uinputs.get_uinput("keyboard").capabilities(),
                    "mouse": uinputs.get_uinput("mouse").capabilities(),
                }
            },
        )
