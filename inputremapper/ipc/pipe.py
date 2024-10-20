# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2024 sezanzeb <b8x45ygc9@mozmail.com>
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

import asyncio
import json
import os
import time
from typing import Optional, AsyncIterator, Union

from inputremapper.configs.paths import PathUtils
from inputremapper.logging.logger import logger


class Pipe:
    """Pipe object.

    This is not for secure communication. If pipes already exist, they will be used,
    but existing pipes might have open permissions! Only use this for stuff that
    non-privileged users would be allowed to read.
    """

    def __init__(self, path):
        """Create a pipe, or open it if it already exists."""
        self._path = path
        self._unread = []
        self._created_at = time.time()

        self._transport: Optional[asyncio.ReadTransport] = None
        self._async_iterator: Optional[AsyncIterator] = None

        paths = (f"{path}r", f"{path}w")

        PathUtils.mkdir(os.path.dirname(path))

        if not os.path.exists(paths[0]):
            logger.debug("Creating new pipes %s", paths)
            # The fd the link points to is closed, or none ever existed
            # If there is a link, remove it.
            if os.path.islink(paths[0]):
                os.remove(paths[0])
            if os.path.islink(paths[1]):
                os.remove(paths[1])

            self._fds = os.pipe()
            fds_dir = f"/proc/{os.getpid()}/fd/"
            PathUtils.chown(f"{fds_dir}{self._fds[0]}")
            PathUtils.chown(f"{fds_dir}{self._fds[1]}")

            # to make it accessible by path constants, create symlinks
            os.symlink(f"{fds_dir}{self._fds[0]}", paths[0])
            os.symlink(f"{fds_dir}{self._fds[1]}", paths[1])
        else:
            logger.debug("Using existing pipes %s", paths)

        # thanks to os.O_NONBLOCK, readline will return b'' when there
        # is nothing to read
        self._fds = (
            os.open(paths[0], os.O_RDONLY | os.O_NONBLOCK),
            os.open(paths[1], os.O_WRONLY | os.O_NONBLOCK),
        )

        self._handles = (open(self._fds[0], "r"), open(self._fds[1], "w"))

        # clear the pipe of any contents, to avoid leftover messages from breaking
        # the reader-client or reader-service
        while self.poll():
            leftover = self.recv()
            logger.debug('Cleared leftover message "%s"', leftover)

    def __del__(self):
        if self._transport:
            logger.debug("closing transport")
            self._transport.close()
        for file in self._handles:
            file.close()

    def recv(self):
        """Read an object from the pipe or None if nothing available.

        Doesn't transmit pickles, to avoid injection attacks on the
        privileged reader-service. Only messages that can be converted to json
        are allowed.
        """
        if len(self._unread) > 0:
            return self._unread.pop(0)

        line = self._handles[0].readline()
        if len(line) == 0:
            return None

        return self._get_msg(line)

    def _get_msg(self, line: str):
        parsed = json.loads(line)
        if parsed[0] < self._created_at and os.environ.get("UNITTEST"):
            # important to avoid race conditions between multiple unittests,
            # for example old terminate messages reaching a new instance of
            # the reader-service.
            logger.debug("Ignoring old message %s", parsed)
            return None

        return parsed[1]

    def send(self, message: Union[str, int, float, dict, list, tuple]):
        """Write a serializable object to the pipe."""
        dump = json.dumps((time.time(), message))
        # there aren't any newlines supposed to be,
        # but if there are it breaks readline().
        self._handles[1].write(dump.replace("\n", ""))
        self._handles[1].write("\n")
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
        """Compatibility to select.select."""
        return self._handles[0].fileno()

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._async_iterator:
            loop = asyncio.get_running_loop()
            reader = asyncio.StreamReader()

            self._transport, _ = await loop.connect_read_pipe(
                lambda: asyncio.StreamReaderProtocol(reader), self._handles[0]
            )
            self._async_iterator = reader.__aiter__()

        return self._get_msg(await self._async_iterator.__anext__())

    async def recv_async(self):
        """Read the next line with async. Do not use this when using
        the async for loop."""
        return await self.__aiter__().__anext__()
