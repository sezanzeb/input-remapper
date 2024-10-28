#!/usr/bin/python3
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

"""Starts the root reader-service."""

import asyncio
import atexit
import os
import signal
import sys
import time
from argparse import ArgumentParser

from inputremapper.bin.process_utils import ProcessUtils
from inputremapper.groups import _Groups
from inputremapper.gui.reader_service import ReaderService
from inputremapper.injection.global_uinputs import GlobalUInputs, FrontendUInput
from inputremapper.logging.logger import logger


class InputRemapperReaderServiceBin:
    @staticmethod
    def main() -> None:
        parser = ArgumentParser()
        parser.add_argument(
            "-d",
            "--debug",
            action="store_true",
            dest="debug",
            help="Displays additional debug information",
            default=False,
        )

        options = parser.parse_args(sys.argv[1:])

        logger.update_verbosity(options.debug)

        if ProcessUtils.count_python_processes("input-remapper-reader-service") >= 2:
            logger.warning(
                "Another input-remapper-reader-service process is already running. "
                "This can cause problems while recording keys"
            )

        if os.getuid() != 0:
            logger.warning("The reader-service usually needs elevated privileges")

        if not ReaderService.pipes_exist():
            logger.info("Waiting for pipes to be created by the GUI")
            while not ReaderService.pipes_exist():
                time.sleep(0.5)
                logger.debug("Waiting...")

        def on_exit():
            """Don't remain idle and alive when the GUI exits via ctrl+c."""
            # makes no sense to me, but after the keyboard interrupt it is still
            # waiting for an event to complete (`S` in `ps ax`), even when using
            # sys.exit
            os.kill(os.getpid(), signal.SIGKILL)

        atexit.register(on_exit)
        groups = _Groups()
        global_uinputs = GlobalUInputs(FrontendUInput)
        reader_service = ReaderService(groups, global_uinputs)
        asyncio.run(reader_service.run())
