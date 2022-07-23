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


"""Share a dictionary across processes."""


import atexit
import multiprocessing
import select

from inputremapper.logger import logger


class SharedDict:
    """Share a dictionary across processes."""

    # because unittests terminate all child processes in cleanup I can't use
    # multiprocessing.Manager
    def __init__(self):
        """Create a shared dictionary."""
        super().__init__()

        # To avoid blocking forever if something goes wrong. The maximum
        # observed time communication takes was 0.001 for me on a slow pc
        self._timeout = 0.02

        self.pipe = multiprocessing.Pipe()
        self.process = None
        atexit.register(self._stop)

    def start(self):
        """Ensure the process to manage the dictionary is running."""
        if self.process is not None and self.process.is_alive():
            logger.debug("SharedDict process already running")
            return

        # if the manager has already been running in the past but stopped
        # for some reason, the dictionary contents are lost.
        logger.debug("Starting SharedDict process")
        self.process = multiprocessing.Process(target=self.manage)
        self.process.start()

    def manage(self):
        """Manage the dictionary, handle read and write requests."""
        logger.debug("SharedDict process started")
        shared_dict = {}
        while True:
            message = self.pipe[0].recv()
            logger.debug("SharedDict got %s", message)

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
