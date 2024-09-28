#!/usr/bin/python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2023 sezanzeb <proxima@sezanzeb.de>
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

from __future__ import annotations

import sys
import traceback
import tracemalloc
import warnings
import logging


tracemalloc.start()

logger = logging.getLogger("input-remapper-test")
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("\033[90mTest: %(message)s\033[0m"))
logger.addHandler(handler)
logger.setLevel(logging.INFO)


def update_inputremapper_verbosity():
    from inputremapper.logger.logger import logger

    logger.update_verbosity(True)


def warn_with_traceback(message, category, filename, lineno, file=None, line=None):
    log = file if hasattr(file, "write") else sys.stderr
    traceback.print_stack(file=log)
    log.write(warnings.formatwarning(message, category, filename, lineno, line))


def patch_warnings():
    # show traceback
    warnings.showwarning = warn_with_traceback
    warnings.simplefilter("always")
