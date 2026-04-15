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

"""Logging setup for input-remapper."""

from __future__ import annotations  # needed for the TYPE_CHECKING import

import logging
import time
from typing import cast, Type, TYPE_CHECKING, List, Tuple
from evdev.ecodes import EV_ABS, EV_KEY, EV_REL, ABS_HAT0X, ABS_HAT0Y

from inputremapper.input_event import InputEvent
from inputremapper.logging.formatter import ColorfulFormatter
from inputremapper.installation_info import VERSION, COMMIT_HASH

if TYPE_CHECKING:
    from inputremapper.injection.mapping_handler import MappingHandler


start = time.time()


class Logger(logging.Logger):
    previous_abs_rel_log_time = 0.0
    previous_write_debug_log = None
    analog_log_threshold = 0.1  # s

    def debug_mapping_handler(self, mapping_handler: MappingHandler) -> None:
        """Parse the structure of a mapping_handler and log it."""
        if not self.isEnabledFor(logging.DEBUG):
            return

        lines_and_indent = self._build_mapping_handler_description_tree(mapping_handler)
        for line in lines_and_indent:
            indent = "    "
            msg = indent * line[1] + line[0]
            self._log(logging.DEBUG, msg, args=())

    def write(self, key, uinput) -> None:
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

        if isinstance(key, InputEvent):
            if key.type not in [EV_ABS, EV_REL, EV_KEY]:
                return

            # Avoid spaming the terminal with tons of high-resolution logs
            now = time.time()
            if key.type in [EV_ABS, EV_REL] and key.code not in [ABS_HAT0X, ABS_HAT0Y]:
                if now - self.previous_abs_rel_log_time < self.analog_log_threshold:
                    return

                self.previous_abs_rel_log_time = now

        str_key = repr(key)
        str_key = str_key.replace(",)", ")")

        msg = f'Writing {str_key} to "{uinput.name}"'

        if msg == self.previous_write_debug_log:
            # avoid some spam
            return

        self.previous_write_debug_log = msg

        self._log(logging.DEBUG, msg, args=(), stacklevel=2)

    def _build_mapping_handler_description_tree(
        self,
        mapping_handler: MappingHandler,
        indent=0,
    ) -> List[Tuple[str, int]]:
        lines_and_indent = [
            (str(mapping_handler), indent),
        ]

        mapping_handlers = mapping_handler.get_children()
        for sub_handler in mapping_handlers:
            sub_list = self._build_mapping_handler_description_tree(
                sub_handler, indent + 1
            )
            lines_and_indent.extend(sub_list)

        return lines_and_indent

    def is_debug(self) -> bool:
        """True, if the logger is currently in DEBUG mode."""
        return self.level <= logging.DEBUG

    def log_info(self, name: str = "input-remapper") -> None:
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

    def update_verbosity(self, debug: bool) -> None:
        """Set the logging verbosity according to the settings object."""
        if debug:
            self.setLevel(logging.DEBUG)
        else:
            self.setLevel(logging.INFO)

        for handler in self.handlers:
            handler.setFormatter(ColorfulFormatter(debug))

    @classmethod
    def bootstrap_logger(cls: Type[Logger]) -> Logger:
        # https://github.com/python/typeshed/issues/1801
        logging.setLoggerClass(cls)
        logger = cast(Logger, logging.getLogger("input-remapper"))

        handler = logging.StreamHandler()
        handler.setFormatter(ColorfulFormatter(False))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logging.getLogger("asyncio").setLevel(logging.WARNING)
        return logger


logger = Logger.bootstrap_logger()


EVDEV_VERSION = None
try:
    from importlib.metadata import version

    EVDEV_VERSION = version("evdev")
except Exception as error:
    logger.info("Could not figure out the evdev version")
    logger.debug(error)

# check if the version is something like 1.5.0-beta or 1.5.0-beta.5
IS_BETA = "beta" in VERSION
