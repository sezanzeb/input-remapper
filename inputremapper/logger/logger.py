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

"""Logging setup for input-remapper."""

import logging
import time
from typing import cast

from inputremapper.logger.formatter import ColorfulFormatter

try:
    from inputremapper.commit_hash import COMMIT_HASH
except ImportError:
    COMMIT_HASH = ""


start = time.time()

previous_key_debug_log = None
previous_write_debug_log = None


class Logger(logging.Logger):
    def debug_mapping_handler(self, mapping_handler):
        """Parse the structure of a mapping_handler and log it."""
        if not self.isEnabledFor(logging.DEBUG):
            return

        lines_and_indent = self._parse_mapping_handler(mapping_handler)
        for line in lines_and_indent:
            indent = "    "
            msg = indent * line[1] + line[0]
            self._log(logging.DEBUG, msg, args=None)

    def write(self, key, uinput):
        """Log that an event is being written

        Parameters
        ----------
        key
            anything that can be string formatted, but usually a tuple of
            (type, code, value) tuples
        """
        # pylint: disable=protected-access
        if not self.isEnabledFor(logging.DEBUG):
            return

        global previous_write_debug_log

        str_key = repr(key)
        str_key = str_key.replace(",)", ")")

        msg = f'Writing {str_key} to "{uinput.name}"'

        if msg == previous_write_debug_log:
            # avoid some super spam from EV_ABS events
            return

        previous_write_debug_log = msg

        self._log(logging.DEBUG, msg, args=None)

    def _parse_mapping_handler(self, mapping_handler):
        indent = 0
        lines_and_indent = []
        while True:
            if isinstance(mapping_handler, list):
                for sub_handler in mapping_handler:
                    sub_list = self._parse_mapping_handler(sub_handler)
                    for line in sub_list:
                        line[1] += indent
                    lines_and_indent.extend(sub_list)
                break

            lines_and_indent.append([repr(mapping_handler), indent])
            try:
                mapping_handler = mapping_handler.child
            except AttributeError:
                break

            indent += 1
        return lines_and_indent

    def is_debug(self):
        """True, if the logger is currently in DEBUG mode."""
        return self.level <= logging.DEBUG

    def log_info(self, name="input-remapper"):
        """Log version and name to the console."""
        logger.info(
            "%s %s %s https://github.com/sezanzeb/input-remapper",
            name,
            VERSION,
            COMMIT_HASH,
        )

        if EVDEV_VERSION:
            logger.info("python-evdev %s", EVDEV_VERSION)

        if self.is_debug():
            logger.warning(
                "Debug level will log all your keystrokes! Do not post this "
                "output in the internet if you typed in sensitive or private "
                "information with your device!"
            )

    def update_verbosity(self, debug):
        """Set the logging verbosity according to the settings object.

        Also enable rich tracebacks in debug mode.
        """
        # pylint really doesn't like what I'm doing with rich.traceback here
        # pylint: disable=broad-except,import-error,import-outside-toplevel
        if debug:
            self.setLevel(logging.DEBUG)

            try:
                from rich.traceback import install

                install(show_locals=True)
                self.debug("Using rich.traceback")
            except Exception as error:
                # since this is optional, just skip all exceptions
                if not isinstance(error, ImportError):
                    self.debug("Cannot use rich.traceback: %s", error)
        else:
            self.setLevel(logging.INFO)

        for handler in self.handlers:
            handler.setFormatter(ColorfulFormatter(debug))

    @classmethod
    def bootstrap_logger(cls):
        # https://github.com/python/typeshed/issues/1801
        logging.setLoggerClass(cls)
        logger = cast(cls, logging.getLogger("input-remapper"))

        handler = logging.StreamHandler()
        handler.setFormatter(ColorfulFormatter(False))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logging.getLogger("asyncio").setLevel(logging.WARNING)
        return logger


logger = Logger.bootstrap_logger()


# using pkg_resources to figure out the version fails in many cases,
# so we hardcode it instead
VERSION = "2.0.1"
EVDEV_VERSION = None
try:
    # pkg_resources very commonly fails/breaks
    import pkg_resources

    EVDEV_VERSION = pkg_resources.require("evdev")[0].version
except Exception as error:
    # there have been pkg_resources.DistributionNotFound and
    # pkg_resources.ContextualVersionConflict errors so far.
    # We can safely ignore all Exceptions here
    logger.info("Could not figure out the version")
    logger.debug(error)

# check if the version is something like 1.5.0-beta or 1.5.0-beta.5
IS_BETA = "beta" in VERSION
