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
import itertools
import unittest

from inputremapper.gui.event_handler import EventHandler, EventEnum


class Listener:
    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)


class TestEventHandler(unittest.TestCase):
    def test_unknown_event_raises(self):
        """The Event Handler throws an KeyError if the event is not known"""
        event_handler = EventHandler()
        self.assertRaises(KeyError, event_handler.emit, "foo")

    async def test_calls_listeners(self):
        """The correct Listeners get called"""
        event_handler = EventHandler()
        listener = Listener()
        event_handler.subscribe(EventEnum.test_ev1, listener)
        event_handler.emit(EventEnum.test_ev1, arg1="foo")
        event_handler.emit(EventEnum.test_ev2, arg1="bar")
        self.assertEqual(listener.calls[0], {"arg1": "foo"})

    def test_unsubscribe(self):
        event_handler = EventHandler()
        listener = Listener()
        event_handler.subscribe(EventEnum.test_ev1, listener)
        event_handler.emit(EventEnum.test_ev1, a=1)
        event_handler.unsubscribe(listener)
        event_handler.emit(EventEnum.test_ev1, b=2)
        self.assertEqual(len(listener.calls), 1)
        self.assertEqual(listener.calls[0], {"a": 1})

    def test_unsubscribe_unknown_listener(self):
        """nothing happens if we unsubscribe an unknown listener"""
        event_handler = EventHandler()
        listener1 = Listener()
        listener2 = Listener()
        event_handler.subscribe(EventEnum.test_ev1, listener1)
        event_handler.unsubscribe(listener2)
        event_handler.emit(EventEnum.test_ev1, a=1)
        self.assertEqual(listener1.calls[0], {"a": 1})

    def test_only_kwargs_allowed(self):
        """we cannot pass arguments to listeners, only keyword-arguments"""
        event_handler = EventHandler()
        event_handler.subscribe(EventEnum.test_ev1, lambda *_, **__: None)
        self.assertRaises(TypeError, event_handler.emit, EventEnum.test_ev1, 1, a=2)
        self.assertRaises(TypeError, event_handler.emit, EventEnum.test_ev2, 1, a=2)

    def test_calls_callbacks_after_listeners(self):
        event_handler = EventHandler()
        calls = []

        def listener1():
            calls.append(1)

            def callback():
                calls.append(6)

            return callback

        def listener2():
            calls.append(2)

        def listener3():
            calls.append(3)

            def callback():
                calls.append(5)

            return callback

        def listener4():
            calls.append(4)

        event_handler.subscribe(EventEnum.test_ev1, listener1)
        event_handler.subscribe(EventEnum.test_ev1, listener2)
        event_handler.subscribe(EventEnum.test_ev1, listener3)
        event_handler.subscribe(EventEnum.test_ev1, listener4)
        event_handler.emit(EventEnum.test_ev1)
        first = calls[:4]
        first.sort()
        last = calls[4:]
        last.sort()
        self.assertEqual([1, 2, 3, 4], first)
        self.assertEqual([5, 6], last)
