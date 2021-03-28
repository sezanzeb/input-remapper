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


"""Non-blocking abstraction of unix domain sockets.

>>> server = Server('foo')
>>> client = Client('foo')

>>> server.send(1)
>>> client.poll()
>>> client.recv()

>>> client.send(2)
>>> server.poll()
>>> server.recv()

I seems harder to sniff on a socket than using pipes for other non-root
processes, but it doesn't guarantee security. As long as the GUI is open
and not running as root user, it is most likely possible to somehow log
keycodes by looking into the memory of the gui process (just like with most
other applications because they end up receiving keyboard input as well).
It still appears to be a bit overkill to use a socket considering pipes
are much easier to handle.
"""


# Issues:
# - Tests don't pass with Server (reader) and Client (helper) instead of Pipe
# - Had one case of a test that was blocking forever, seems very rare.
# - Hard to debug, generally very problematic compared to Pipes
# The tool works fine, it's just the tests. BrokenPipe errors reported
# by _Server all the time.


import select
import socket
import os
import time
import json

from keymapper.logger import logger
from keymapper.paths import mkdir, chown


# something funny that most likely won't appear in messages.
# also add some ones so that 01 in the payload won't offset
# a match by 2 bits
END = b'\x55\x55\xff\x55'  # should be 01010101 01010101 11111111 01010101

ENCODING = 'utf8'


# reusing existing objects makes tests easier, no headaches about closing
# and reopening anymore. The ui also only runs only one instance of each all
# the time.
existing_servers = {}
existing_clients = {}


class Base:
    """Abstract base class for Socket and Client."""
    def __init__(self, path):
        self._path = path
        self._unread = []
        self.unsent = []
        mkdir(os.path.dirname(path))
        self.connection = None
        self.socket = None
        self._created_at = 0
        self.reset()

    def reset(self):
        """Ignore older messages than now."""
        # ensure it is connected
        self.connect()
        self._created_at = time.time()

    def connect(self):
        """Returns True if connected, and if not attempts to connect."""
        raise NotImplementedError

    def fileno(self):
        """For compatibility with select.select."""
        raise NotImplementedError

    def reconnect(self):
        """Try to make a new connection."""
        raise NotImplementedError

    def _receive_new_messages(self):
        if not self.connect():
            logger.spam('Not connected')
            return

        messages = b''
        attempts = 0
        while True:
            try:
                chunk = self.connection.recvmsg(4096)[0]
                messages += chunk

                if len(chunk) == 0:
                    # select keeps telling me the socket has messages
                    # ready to be received, and I keep getting empty
                    # buffers. Happened during a test that ran two helper
                    # processes without stopping the first one.
                    attempts += 1
                    if attempts == 2 or not self.reconnect():
                        return

            except (socket.timeout, BlockingIOError):
                break

        split = messages.split(END)
        for message in split:
            if len(message) > 0:
                parsed = json.loads(message.decode(ENCODING))
                if parsed[0] < self._created_at:
                    # important to avoid race conditions between multiple
                    # unittests, for example old terminate messages reaching
                    # a new instance of the helper.
                    logger.spam('Ignoring old message %s', parsed)
                    continue

                self._unread.append(parsed[1])

    def recv(self):
        """Get the next message or None if nothing to read.

        Doesn't transmit pickles, to avoid injection attacks on the
        privileged helper. Only messages that can be converted to json
        are allowed.
        """
        self._receive_new_messages()

        if len(self._unread) == 0:
            return None

        return self._unread.pop(0)

    def poll(self):
        """Check if a message to read is available."""
        if len(self._unread) > 0:
            return True

        self._receive_new_messages()
        return len(self._unread) > 0

    def send(self, message):
        """Send jsonable messages, like numbers, strings or objects."""
        dump = bytes(json.dumps((time.time(), message)), ENCODING)
        self.unsent.append(dump)

        if not self.connect():
            logger.spam('Not connected')
            return

        def send_all():
            while len(self.unsent) > 0:
                unsent = self.unsent[0]
                self.connection.sendall(unsent + END)
                # sending worked, remove message
                self.unsent.pop(0)

        # attempt sending twice in case it fails
        try:
            send_all()
        except BrokenPipeError:
            if not self.reconnect():
                logger.error(
                    '%s: The other side of "%s" disappeared',
                    type(self).__name__, self._path
                )
                return

            try:
                send_all()
            except BrokenPipeError as error:
                logger.error(
                    '%s: Failed to send via "%s": %s',
                    type(self).__name__, self._path, error
                )


class _Client(Base):
    """A socket that can be written to and read from."""
    def connect(self):
        if self.socket is not None:
            return True

        try:
            _socket = socket.socket(socket.AF_UNIX)
            _socket.connect(self._path)
            logger.spam('Connected to socket: "%s"', self._path)
            _socket.setblocking(False)
        except Exception as error:
            logger.spam('Failed to connect to "%s": "%s"', self._path, error)
            return False

        self.socket = _socket
        self.connection = _socket
        existing_clients[self._path] = self
        return True

    def fileno(self):
        """For compatibility with select.select"""
        self.connect()
        return self.socket.fileno()

    def reconnect(self):
        self.connection = None
        self.socket = None
        return self.connect()


def Client(path):
    if path in existing_clients:
        # ensure it is running, might have been closed
        existing_clients[path].reset()
        return existing_clients[path]

    return _Client(path)


class _Server(Base):
    """A socket that can be written to and read from.

    It accepts one connection at a time, and drops old connections if
    a new one is in sight.
    """
    def connect(self):
        if self.socket is None:
            if os.path.exists(self._path):
                # leftover from the previous execution
                os.remove(self._path)

            _socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            _socket.bind(self._path)
            _socket.listen(1)
            chown(self._path)
            logger.spam('Created socket: "%s"', self._path)
            self.socket = _socket
            self.socket.setblocking(False)
            existing_servers[self._path] = self

        incoming = len(select.select([self.socket], [], [], 0)[0]) != 0
        if not incoming and self.connection is None:
            # no existing connection, no client attempting to connect
            return False

        if not incoming and self.connection is not None:
            # old connection
            return True

        if incoming:
            logger.spam('Incoming connection: "%s"', self._path)
            connection = self.socket.accept()[0]
            self.connection = connection
            self.connection.setblocking(False)

        return True

    def fileno(self):
        """For compatibility with select.select."""
        self.connect()
        return self.connection.fileno()

    def reconnect(self):
        self.connection = None
        return self.connect()


def Server(path):
    if path in existing_servers:
        # ensure it is running, might have been closed
        existing_servers[path].reset()
        return existing_servers[path]

    return _Server(path)
