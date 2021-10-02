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


"""Share a dictionary across processes."""


import multiprocessing
import atexit
import select

from keymapper.logger import logger


class SharedDict:
    """Share a dictionary across processes."""

    # because unittests terminate all child processes in cleanup I can't use
    # multiprocessing.Manager
    def __init__(self):
        """Create a shared dictionary."""
        super().__init__()
        self.pipe = multiprocessing.Pipe()
        self.process = None
        atexit.register(self._stop)
        self._start()

        # To avoid blocking forever if something goes wrong. The maximum
        # observed time communication takes was 0.001 for me on a slow pc
        self._timeout = 0.02

    def _start(self):
        """Ensure the process to manage the dictionary is running."""
        if self.process is not None and self.process.is_alive():
            return

        # if the manager has already been running in the past but stopped
        # for some reason, the dictionary contents are lost
        self.process = multiprocessing.Process(target=self.manage)
        self.process.start()

    def manage(self):
        """Manage the dictionary, handle read and write requests."""
        shared_dict = dict()
        while True:
            message = self.pipe[0].recv()
            logger.spam("SharedDict got %s", message)

            if message[0] == "stop":
                return

            if message[0] == "set":
                shared_dict[message[1]] = message[2]

            if message[0] == "clear":
                shared_dict.clear()

            if message[0] == "get":
                self.pipe[0].send(shared_dict.get(message[1]))

            if message[0] == "ping":
                self.pipe[0].send("pong")

    def _stop(self):
        """Stop the managing process."""
        self.pipe[1].send(("stop",))

    def _clear(self):
        """Clears the memory."""
        self.pipe[1].send(("clear",))

    def get(self, key):
        """Get a value from the dictionary.

        If it doesn't exist, returns None.
        """
        return self.__getitem__(key)

    def is_alive(self, timeout=None):
        """Check if the manager process is running."""
        self.pipe[1].send(("ping",))
        select.select([self.pipe[1]], [], [], timeout or self._timeout)
        if self.pipe[1].poll():
            return self.pipe[1].recv() == "pong"

        return False

    def __setitem__(self, key, value):
        self.pipe[1].send(("set", key, value))

    def __getitem__(self, key):
        self.pipe[1].send(("get", key))

        select.select([self.pipe[1]], [], [], self._timeout)
        if self.pipe[1].poll():
            return self.pipe[1].recv()

        logger.error("select.select timed out")
        return None

    def __del__(self):
        self._stop()
