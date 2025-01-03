#!/usr/bin/env python3
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

from __future__ import annotations

import asyncio
import time
from typing import AsyncIterator


async def precise_iteration_frequency(frequency: float) -> AsyncIterator[None]:
    """A generator to iterate over in a fixed frequency.

    asyncio.sleep might end up sleeping too long, for whatever reason. Maybe there are
    other async function calls that take longer than expected in the background.
    """
    sleep = 1 / frequency
    corrected_sleep = sleep
    error = 0

    while True:
        start = time.time()

        yield

        corrected_sleep -= error
        await asyncio.sleep(corrected_sleep)
        error = (time.time() - start) - sleep
