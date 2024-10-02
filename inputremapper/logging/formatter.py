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
import os
import sys
from datetime import datetime
from typing import Dict


class ColorfulFormatter(logging.Formatter):
    """Overwritten Formatter to print nicer logs.

    It colors all logs from the same filename in the same color to visually group them
    together. It also adds process name, process id, file, line-number and time.

    If debug mode is not active, it will not do any of this.
    """

    def __init__(self, debug_mode: bool = False):
        super().__init__()

        self.debug_mode = debug_mode
        self.file_color_mapping: Dict[str, int] = {}

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

    def _get_ansi_code(self, r: int, g: int, b: int) -> int:
        return 16 + b + (6 * g) + (36 * r)

    def _word_to_color(self, word: str) -> int:
        """Convert a word to a 8bit ansi color code."""
        digit_sum = sum([ord(char) for char in word])
        index = digit_sum % len(self.allowed_colors)
        return self.allowed_colors[index]

    def _allocate_debug_log_color(self, record: logging.LogRecord):
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
        process_path = sys.argv[0]
        process_name = process_path.split("/")[-1]

        if "input-remapper-" in process_name:
            process_name = process_name.replace("input-remapper-", "")

        if process_name == "gtk":
            process_name = "GUI"

        return process_name

    def _get_format(self, record: logging.LogRecord):
        """Generate a message format string."""
        if record.levelno == logging.INFO and not self.debug_mode:
            # if not launched with --debug, then don't print "INFO:"
            return "%(message)s"

        if not self.debug_mode:
            color = self.level_based_colors.get(record.levelno, 9)
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

    def format(self, record: logging.LogRecord):
        """Overwritten format function."""
        # pylint: disable=protected-access
        self._style._fmt = self._get_format(record)
        return super().format(record)
