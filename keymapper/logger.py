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


"""Logging setup for key-mapper."""


import os
import shutil
import time
import logging
import pkg_resources
from datetime import datetime

from keymapper.user import HOME

try:
    from keymapper.commit_hash import COMMIT_HASH
except ImportError:
    COMMIT_HASH = ""


SPAM = 5

start = time.time()

previous_key_spam = None


def spam(self, message, *args, **kwargs):
    """Log a more-verbose message than debug."""
    # pylint: disable=protected-access
    if self.isEnabledFor(SPAM):
        # https://stackoverflow.com/a/13638084
        self._log(SPAM, message, args, **kwargs)


def key_spam(self, key, msg, *args):
    """Log a spam message custom tailored to keycode_mapper.

    Parameters
    ----------
    key : tuple of int
        anything that can be string formatted, but usually a tuple of
        (type, code, value) tuples
    """
    # pylint: disable=protected-access
    if not self.isEnabledFor(SPAM):
        return

    global previous_key_spam

    msg = msg % args
    str_key = str(key)
    str_key = str_key.replace(",)", ")")
    spacing = " " + "-" * max(0, 30 - len(str_key))
    if len(spacing) == 1:
        spacing = ""
    msg = f"{str_key}{spacing} {msg}"

    if msg == previous_key_spam:
        # avoid some super spam from EV_ABS events
        return

    previous_key_spam = msg

    self._log(SPAM, msg, args=None)


logging.addLevelName(SPAM, "SPAM")
logging.Logger.spam = spam
logging.Logger.key_spam = key_spam

LOG_PATH = (
    "/var/log/key-mapper"
    if os.access("/var/log", os.W_OK)
    else f"{HOME}/.log/key-mapper"
)

logger = logging.getLogger()


def is_debug():
    """True, if the logger is currently in DEBUG or SPAM mode."""
    return logger.level <= logging.DEBUG


class Formatter(logging.Formatter):
    """Overwritten Formatter to print nicer logs."""

    def format(self, record):
        """Overwritten format function."""
        # pylint: disable=protected-access
        debug = is_debug()
        if record.levelno == logging.INFO and not debug:
            # if not launched with --debug, then don't print "INFO:"
            self._style._fmt = "%(message)s"
        else:
            # see https://en.wikipedia.org/wiki/ANSI_escape_code#3/4_bit
            # for those numbers
            color = {
                logging.WARNING: 33,
                logging.ERROR: 31,
                logging.FATAL: 31,
                logging.DEBUG: 36,
                SPAM: 34,
                logging.INFO: 32,
            }.get(record.levelno, 0)

            if debug:
                delta = f"{str(time.time() - start)[:7]}"
                self._style._fmt = (  # noqa
                    f"\033[{color}m"  # color
                    f"{os.getpid()} "
                    f"{delta} "
                    f"%(levelname)s "
                    f"%(filename)s:%(lineno)d: "
                    "%(message)s"
                    "\033[0m"  # end style
                )
            else:
                self._style._fmt = (  # noqa
                    f"\033[{color}m%(levelname)s\033[0m: %(message)s"
                )
        return super().format(record)


handler = logging.StreamHandler()
handler.setFormatter(Formatter())
logger.addHandler(handler)
logger.setLevel(logging.INFO)
logging.getLogger("asyncio").setLevel(logging.WARNING)


VERSION = ""
EVDEV_VERSION = None
try:
    VERSION = pkg_resources.require("key-mapper")[0].version
    EVDEV_VERSION = pkg_resources.require("evdev")[0].version
except pkg_resources.DistributionNotFound as error:
    logger.info("Could not figure out the version")
    logger.debug(error)


def log_info(name="key-mapper"):
    """Log version and name to the console."""
    logger.info(
        "%s %s %s https://github.com/sezanzeb/key-mapper", name, VERSION, COMMIT_HASH
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
        logger.setLevel(SPAM)

        try:
            from rich.traceback import install

            install(show_locals=True)
            logger.debug("Using rich.traceback")
        except Exception as error:
            # since this is optional, just skip all exceptions
            if not isinstance(error, ImportError):
                logger.debug("Cannot use rich.traceback: %s", error)

        logger.debug("Started debug logs at: %s", str(datetime.now()))
    else:
        logger.setLevel(logging.INFO)


def add_filehandler(log_path=LOG_PATH):
    """Clear the existing logfile and start logging to it."""
    try:
        log_path = os.path.expanduser(log_path)
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

        if os.path.isdir(log_path):
            # used to be a folder < 0.8.0
            shutil.rmtree(log_path)

        if os.path.exists(log_path):
            # the logfile should not be too long to avoid overflowing the storage
            with open(log_path, "r") as file:
                content = file.readlines()[-1000:] + ["---\n"]

            with open(log_path, "w") as file:
                file.truncate(0)
                file.writelines(content)

        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(Formatter())

        logger.info('%d Logging to "%s"', os.getpid(), log_path)

        logger.addHandler(file_handler)
    except PermissionError:
        logger.debug('No permission to log to "%s"', log_path)
