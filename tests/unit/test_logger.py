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

import evdev
import os
import shutil
import unittest
import logging

from tests.lib.tmp import tmp

from inputremapper.logger import logger, update_verbosity, log_info, ColorfulFormatter
from inputremapper.configs.paths import remove


def add_filehandler(log_path):
    """Start logging to a file."""
    log_path = os.path.expanduser(log_path)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(ColorfulFormatter())
    logger.addHandler(file_handler)
    logger.info('Starting logging to "%s"', log_path)


class TestLogger(unittest.TestCase):
    def tearDown(self):
        update_verbosity(debug=True)

        # remove the file handler
        logger.handlers = [
            handler
            for handler in logger.handlers
            if not isinstance(logger.handlers, logging.FileHandler)
        ]
        path = os.path.join(tmp, "logger-test")
        remove(path)

    def test_write(self):
        uinput = evdev.UInput(name="foo")
        path = os.path.join(tmp, "logger-test")
        add_filehandler(path)
        logger.write(
            (
                evdev.ecodes.EV_KEY,
                evdev.ecodes.KEY_A,
                1
            ),
            uinput
        )
        with open(path, "r") as f:
            content = f.read()
            self.assertIn(
                f'Writing (1, 30, 1) to "foo"',
                content,
            )

    def test_log_info(self):
        update_verbosity(debug=False)
        path = os.path.join(tmp, "logger-test")
        add_filehandler(path)
        log_info()
        with open(path, "r") as f:
            content = f.read().lower()
            self.assertIn("input-remapper", content)

    def test_makes_path(self):
        path = os.path.join(tmp, "logger-test")
        if os.path.exists(path):
            shutil.rmtree(path)

        new_path = os.path.join(tmp, "logger-test", "a", "b", "c")
        add_filehandler(new_path)
        self.assertTrue(os.path.exists(new_path))

    def test_debug(self):
        path = os.path.join(tmp, "logger-test")
        add_filehandler(path)
        logger.error("abc")
        logger.warning("foo")
        logger.info("123")
        logger.debug("456")
        logger.debug("789")
        with open(path, "r") as f:
            content = f.read().lower()
            self.assertIn("logger.py", content)

            self.assertIn("error", content)
            self.assertIn("abc", content)

            self.assertIn("warn", content)
            self.assertIn("foo", content)

            self.assertIn("info", content)
            self.assertIn("123", content)

            self.assertIn("debug", content)
            self.assertIn("456", content)

            self.assertIn("debug", content)
            self.assertIn("789", content)

    def test_default(self):
        path = os.path.join(tmp, "logger-test")
        update_verbosity(debug=False)
        add_filehandler(path)
        logger.error("abc")
        logger.warning("foo")
        logger.info("123")
        logger.debug("456")
        logger.debug("789")
        with open(path, "r") as f:
            content = f.read().lower()
            self.assertNotIn("logger.py", content)
            self.assertNotIn("line", content)

            self.assertIn("error", content)
            self.assertIn("abc", content)

            self.assertIn("warn", content)
            self.assertIn("foo", content)

            self.assertNotIn("info", content)
            self.assertIn("123", content)

            self.assertNotIn("debug", content)
            self.assertNotIn("456", content)

            self.assertNotIn("debug", content)
            self.assertNotIn("789", content)


if __name__ == "__main__":
    unittest.main()
