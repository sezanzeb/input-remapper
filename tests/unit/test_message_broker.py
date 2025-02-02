#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2025 sezanzeb <b8x45ygc9@mozmail.com>
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
from dataclasses import dataclass

from inputremapper.gui.messages.message_broker import MessageBroker, MessageType, Signal
from tests.lib.test_setup import test_setup


class Listener:
    def __init__(self):
        self.calls = []

    def __call__(self, data):
        self.calls.append(data)


@dataclass
class Message:
    message_type: MessageType
    msg: str


@test_setup
class TestMessageBroker(unittest.TestCase):
    def test_calls_listeners(self):
        """The correct Listeners get called"""
        message_broker = MessageBroker()
        listener = Listener()
        message_broker.subscribe(MessageType.test1, listener)
        message_broker.publish(Message(MessageType.test1, "foo"))
        message_broker.publish(Message(MessageType.test2, "bar"))
        self.assertEqual(listener.calls[0], Message(MessageType.test1, "foo"))

    def test_unsubscribe(self):
        message_broker = MessageBroker()
        listener = Listener()
        message_broker.subscribe(MessageType.test1, listener)
        message_broker.publish(Message(MessageType.test1, "a"))
        message_broker.unsubscribe(listener)
        message_broker.publish(Message(MessageType.test1, "b"))
        self.assertEqual(len(listener.calls), 1)
        self.assertEqual(listener.calls[0], Message(MessageType.test1, "a"))

    def test_unsubscribe_unknown_listener(self):
        """nothing happens if we unsubscribe an unknown listener"""
        message_broker = MessageBroker()
        listener1 = Listener()
        listener2 = Listener()
        message_broker.subscribe(MessageType.test1, listener1)
        message_broker.unsubscribe(listener2)
        message_broker.publish(Message(MessageType.test1, "a"))
        self.assertEqual(listener1.calls[0], Message(MessageType.test1, "a"))

    def test_preserves_order(self):
        message_broker = MessageBroker()
        calls = []

        def listener1(_):
            message_broker.publish(Message(MessageType.test2, "f"))
            calls.append(1)

        def listener2(_):
            message_broker.publish(Message(MessageType.test2, "f"))
            calls.append(2)

        def listener3(_):
            message_broker.publish(Message(MessageType.test2, "f"))
            calls.append(3)

        def listener4(_):
            calls.append(4)

        message_broker.subscribe(MessageType.test1, listener1)
        message_broker.subscribe(MessageType.test1, listener2)
        message_broker.subscribe(MessageType.test1, listener3)
        message_broker.subscribe(MessageType.test2, listener4)
        message_broker.publish(Message(MessageType.test1, ""))

        first = calls[:3]
        first.sort()
        self.assertEqual([1, 2, 3], first)
        self.assertEqual([4, 4, 4], calls[3:])


@test_setup
class TestSignal(unittest.TestCase):
    def test_eq(self):
        self.assertEqual(Signal(MessageType.uinputs), Signal(MessageType.uinputs))
        self.assertNotEqual(Signal(MessageType.uinputs), Signal(MessageType.groups))
        self.assertNotEqual(Signal(MessageType.uinputs), "Signal: MessageType.uinputs")
