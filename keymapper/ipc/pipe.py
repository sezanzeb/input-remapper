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


"""Named bidirectional non-blocking pipes.

>>> p1 = Pipe('foo')
>>> p2 = Pipe('foo')

>>> p1.send(1)
>>> p2.poll()
>>> p2.recv()

>>> p2.send(2)
>>> p1.poll()
>>> p1.recv()

Beware that pipes read any available messages,
even those written by themselves.
"""


import os
import time
import json

from keymapper.logger import logger
from keymapper.paths import mkdir, chown


class Pipe:
    """Pipe object."""
    def __init__(self, path):
        """Create a pipe, or open it if it already exists."""
        self._path = path
        self._unread = []
        self._created_at = time.time()

        paths = (
            f'{path}r',
            f'{path}w'
        )

        mkdir(os.path.dirname(path))

        if not os.path.exists(paths[0]):
            logger.spam('Creating new pipe for "%s"', path)
            # The fd the link points to is closed, or none ever existed
            # If there is a link, remove it.
            if os.path.islink(paths[0]):
                os.remove(paths[0])
            if os.path.islink(paths[1]):
                os.remove(paths[1])

            self._fds = os.pipe()
            fds_dir = f'/proc/{os.getpid()}/fd/'
            chown(f'{fds_dir}{self._fds[0]}')
            chown(f'{fds_dir}{self._fds[1]}')

            # to make it accessible by path constants, create symlinks
            os.symlink(f'{fds_dir}{self._fds[0]}', paths[0])
            os.symlink(f'{fds_dir}{self._fds[1]}', paths[1])
        else:
            logger.spam('Using existing pipe for "%s"', path)

        # thanks to os.O_NONBLOCK, readline will return b'' when there
        # is nothing to read
        self._fds = (
            os.open(paths[0], os.O_RDONLY | os.O_NONBLOCK),
            os.open(paths[1], os.O_WRONLY | os.O_NONBLOCK)
        )

        self._handles = (
            open(self._fds[0], 'r'),
            open(self._fds[1], 'w')
        )

    def recv(self):
        """Read an object from the pipe or None if nothing available.

        Doesn't transmit pickles, to avoid injection attacks on the
        privileged helper. Only messages that can be converted to json
        are allowed.
        """
        if len(self._unread) > 0:
            return self._unread.pop(0)

        line = self._handles[0].readline()
        if len(line) == 0:
            return None

        parsed = json.loads(line)
        if parsed[0] < self._created_at and os.environ.get('UNITTEST'):
            # important to avoid race conditions between multiple unittests,
            # for example old terminate messages reaching a new instance of
            # the helper.
            logger.spam('Ignoring old message %s', parsed)
            return None

        return parsed[1]

    def send(self, message):
        """Write an object to the pipe."""
        dump = json.dumps((time.time(), message))
        # there aren't any newlines supposed to be,
        # but if there are it breaks readline().
        self._handles[1].write(dump.replace('\n', ''))
        self._handles[1].write('\n')
        self._handles[1].flush()

    def poll(self):
        """Check if there is anything that can be read."""
        if len(self._unread) > 0:
            return True

        # using select.select apparently won't mark the pipe as ready
        # anymore when there are multiple lines to read but only a single
        # line is retreived. Using read instead.
        msg = self.recv()
        if msg is not None:
            self._unread.append(msg)

        return len(self._unread) > 0

    def fileno(self):
        """Compatibility to select.select"""
        return self._handles[0].fileno()
