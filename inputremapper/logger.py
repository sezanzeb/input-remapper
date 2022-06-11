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


"""Logging setup for input-remapper."""


import os
import sys
import shutil
import time
import logging
import pkg_resources
from datetime import datetime

from inputremapper.user import HOME

try:
    from inputremapper.commit_hash import COMMIT_HASH
except ImportError:
    COMMIT_HASH = ""


start = time.time()

previous_key_debug_log = None


def debug_key(self, key, msg, *args):
    """Log a spam message custom tailored to keycode_mapper.

    Parameters
    ----------
    key : tuple of int
        anything that can be string formatted, but usually a tuple of
        (type, code, value) tuples
    """
    # pylint: disable=protected-access
    if not self.isEnabledFor(logging.DEBUG):
        return

    global previous_key_debug_log

    msg = msg % args
    str_key = str(key)
    str_key = str_key.replace(",)", ")")
    spacing = " " + "·" * max(0, 30 - len(msg))
    if len(spacing) == 1:
        spacing = ""
    msg = f"{msg}{spacing} {str_key}"

    if msg == previous_key_debug_log:
        # avoid some super spam from EV_ABS events
        return

    previous_key_debug_log = msg

    self._log(logging.DEBUG, msg, args=None)


logging.Logger.debug_key = debug_key


logger = logging.getLogger("input-remapper")


def is_debug():
    """True, if the logger is currently in DEBUG or DEBUG mode."""
    return logger.level <= logging.DEBUG


class ColorfulFormatter(logging.Formatter):
    """Overwritten Formatter to print nicer logs.

    It colors all logs from the same filename in the same color to visually group them
    together. It also adds process name, process id, file, line-number and time.

    If debug mode is not active, it will not do any of this.
    """

    def __init__(self):
        super().__init__()

        self.file_color_mapping = {}

        # see https://en.wikipedia.org/wiki/ANSI_escape_code#8-bit
        self.allowed_colors = []
        for r in range(0, 6):
            for g in range(0, 6):
                for b in range(0, 6):
                    # https://stackoverflow.com/a/596243
                    brightness = 0.2126 * r + 0.7152 * g + 0.0722 * b
                    if brightness < 1:
                        # prefer light colors, because most people have a dark
                        # terminal background
                        continue

                    if g + b <= 1:
                        # red makes it look like it's an error
                        continue

                    if abs(g - b) < 2 and abs(b - r) < 2 and abs(r - g) < 2:
                        # no colors that are too grey
                        continue

                    self.allowed_colors.append(self._get_ansi_code(r, g, b))

        self.level_based_colors = {
            logging.WARNING: 11,
            logging.ERROR: 9,
            logging.FATAL: 9,
        }

    def _get_ansi_code(self, r, g, b):
        return 16 + b + (6 * g) + (36 * r)

    def _word_to_color(self, word):
        """Convert a word to a 8bit ansi color code."""
        digit_sum = sum([ord(char) for char in word])
        index = digit_sum % len(self.allowed_colors)
        return self.allowed_colors[index]

    def _allocate_debug_log_color(self, record):
        """Get the color that represents the source file of the log."""
        if self.file_color_mapping.get(record.filename) is not None:
            return self.file_color_mapping[record.filename]

        color = self._word_to_color(record.filename)

        if self.file_color_mapping.get(record.filename) is None:
            # calculate the color for each file only once
            self.file_color_mapping[record.filename] = color

        return color

    def _get_process_name(self):
        """Generate a beaitiful to read name for this process."""
        name = sys.argv[0].split("/")[-1].split("-")[-1]
        return {
            "gtk": "GUI",
            "helper": "GUI-Helper",
            "service": "Service",
            "control": "Control",
        }.get(name, name)

    def _get_format(self, record):
        """Generate a message format string."""
        debug_mode = is_debug()

        if record.levelno == logging.INFO and not debug_mode:
            # if not launched with --debug, then don't print "INFO:"
            return "%(message)s"

        if not debug_mode:
            color = self.level_based_colors[record.levelno]
            return f"\033[38;5;{color}m%(levelname)s\033[0m: %(message)s"

        color = self._allocate_debug_log_color(record)
        if record.levelno in [logging.ERROR, logging.WARNING, logging.FATAL]:
            # underline
            style = f"\033[4;38;5;{color}m"
        else:
            style = f"\033[38;5;{color}m"

        process_color = self._word_to_color(f"{os.getpid()}{sys.argv[0]}")

        return (  # noqa
            f'{datetime.now().strftime("%H:%M:%S.%f")} '
            f"\033[38;5;{process_color}m"  # color
            f"{os.getpid()} "
            f"{self._get_process_name()} "
            "\033[0m"  # end style
            f"{style}"
            f"%(levelname)s "
            f"%(filename)s:%(lineno)d: "
            "%(message)s"
            "\033[0m"  # end style
        ).replace("  ", " ")

    def format(self, record):
        """Overwritten format function."""
        # pylint: disable=protected-access
        self._style._fmt = self._get_format(record)
        return super().format(record)


handler = logging.StreamHandler()
handler.setFormatter(ColorfulFormatter())
logger.addHandler(handler)
logger.setLevel(logging.INFO)
logging.getLogger("asyncio").setLevel(logging.WARNING)


VERSION = ""
EVDEV_VERSION = None
try:
    VERSION = pkg_resources.require("input-remapper")[0].version
    EVDEV_VERSION = pkg_resources.require("evdev")[0].version
except pkg_resources.DistributionNotFound as error:
    logger.info("Could not figure out the version")
    logger.debug(error)


def log_info(name="input-remapper"):
    """Log version and name to the console."""
    logger.info(
        "%s %s %s https://github.com/sezanzeb/input-remapper",
        name,
        VERSION,
        COMMIT_HASH,
    )

    if EVDEV_VERSION:
        logger.info("python-evdev %s", EVDEV_VERSION)

    if is_debug():
        logger.warning(
            "Debug level will log all your keystrokes! Do not post this "
            "output in the internet if you typed in sensitive or private "
            "information with your device!"
        )


def update_verbosity(debug):
    """Set the logging verbosity according to the settings object.

    Also enable rich tracebacks in debug mode.
    """
    # pylint really doesn't like what I'm doing with rich.traceback here
    # pylint: disable=broad-except,import-error,import-outside-toplevel
    if debug:
        logger.setLevel(logging.DEBUG)

        try:
            from rich.traceback import install

            install(show_locals=True)
            logger.debug("Using rich.traceback")
        except Exception as error:
            # since this is optional, just skip all exceptions
            if not isinstance(error, ImportError):
                logger.debug("Cannot use rich.traceback: %s", error)
    else:
        logger.setLevel(logging.INFO)


def trim_logfile(log_path):
    """Keep the logfile short."""
    if not os.path.exists(log_path):
        return

    file_size_mb = os.path.getsize(log_path) / 1000 / 1000
    if file_size_mb > 100:
        # something went terribly wrong here. The service might timeout because
        # it takes too long to trim this file. delete it instead. This probably
        # only happens when doing funny things while in debug mode.
        logger.warning(
            "Removing enormous log file of %dMB",
            file_size_mb,
        )
        os.remove(log_path)
        return

    # the logfile should not be too long to avoid overflowing the storage
    try:
        with open(log_path, "rb") as file:
            binary = file.readlines()[-1000:]
            content = [line.decode("utf-8", errors="ignore") for line in binary]

        with open(log_path, "w") as file:
            file.truncate(0)
            file.writelines(content)
    except PermissionError:
        # let the outermost PermissionError handler handle it
        raise
    except Exception as e:
        logger.error('Failed to trim logfile: "%s"', str(e))
