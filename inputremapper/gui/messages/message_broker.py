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

import os.path
import re
import traceback
from collections import defaultdict, deque
from typing import (
    Callable,
    Dict,
    Set,
    Protocol,
    Tuple,
    Deque,
    Any,
    TYPE_CHECKING,
)

from inputremapper.gui.messages.message_types import MessageType
from inputremapper.logger import logger

if TYPE_CHECKING:
    pass


class Message(Protocol):
    """The protocol any message must follow to be sent with the MessageBroker."""

    message_type: MessageType


# useful type aliases
MessageListener = Callable[[Any], None]


class MessageBroker:
    shorten_path = re.compile("inputremapper/")

    def __init__(self):
        self._listeners: Dict[MessageType, Set[MessageListener]] = defaultdict(set)
        self._messages: Deque[Tuple[Message, str, int]] = deque()
        self._publishing = False

    def publish(self, data: Message):
        """Schedule a massage to be sent.
        The message will be sent after all currently pending messages are sent."""
        self._messages.append((data, *self.get_caller()))
        self._publish_all()

    def signal(self, signal: MessageType):
        """Send a signal without any data payload."""
        self.publish(Signal(signal))

    def _publish(self, data: Message, file: str, line: int):
        logger.debug(f"from {file}:{line}: Signal={data.message_type.name}: {data}")
        for listener in self._listeners[data.message_type].copy():
            listener(data)

    def _publish_all(self):
        """Send all scheduled messages in order."""
        if self._publishing:
            # don't run this twice, so we not mess up the order
            return

        self._publishing = True
        try:
            while self._messages:
                self._publish(*self._messages.popleft())
        finally:
            self._publishing = False

    def subscribe(self, massage_type: MessageType, listener: MessageListener):
        """Attach a listener to an event."""
        logger.debug("adding new Listener for %s: %s", massage_type, listener)
        self._listeners[massage_type].add(listener)
        return self

    @staticmethod
    def get_caller(position: int = 3) -> Tuple[str, int]:
        """Extract a file and line from current stack and format for logging."""
        tb = traceback.extract_stack(limit=position)[0]
        return os.path.basename(tb.filename), tb.lineno or 0

    def unsubscribe(self, listener: MessageListener) -> None:
        for listeners in self._listeners.values():
            try:
                listeners.remove(listener)
            except KeyError:
                pass


class Signal(Message):
    """Send a Message without any associated data over the MassageBus."""

    def __init__(self, message_type: MessageType):
        self.message_type: MessageType = message_type

    def __str__(self):
        return f"Signal: {self.message_type}"

    def __eq__(self, other: Any):
        return type(self) == type(other) and self.message_type == other.message_type
