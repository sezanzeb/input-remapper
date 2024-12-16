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


import time
import unittest

from inputremapper.injection.macros.macro import Macro
from inputremapper.injection.macros.parse import Parser
from tests.lib.test_setup import test_setup
from tests.unit.test_macros.macro_test_base import DummyMapping, MacroTestBase


@test_setup
class TestWait(MacroTestBase):
    async def assert_time_randomized(
        self,
        macro: Macro,
        min_: float,
        max_: float,
    ):
        for _ in range(100):
            start = time.time()
            await macro.run(self.handler)
            time_taken = time.time() - start

            # Any of the runs should be within the defined range, to prove that they
            # are indeed random.
            if min_ < time_taken < max_:
                return

        raise AssertionError("`wait` was not randomized")

    async def test_wait_1_core(self):
        mapping = DummyMapping()
        mapping.macro_key_sleep_ms = 0
        macro = Parser.parse("repeat(5, wait(50))", self.context, mapping, True)

        start = time.time()
        await macro.run(self.handler)
        time_per_iteration = (time.time() - start) / 5

        self.assertLess(abs(time_per_iteration - 0.05), 0.005)

    async def test_wait_2_ranged(self):
        mapping = DummyMapping()
        mapping.macro_key_sleep_ms = 0
        macro = Parser.parse("wait(1, 100)", self.context, mapping, True)
        await self.assert_time_randomized(macro, 0.02, 0.08)

    async def test_wait_3_ranged_single_get(self):
        mapping = DummyMapping()
        mapping.macro_key_sleep_ms = 0
        macro = Parser.parse("set(a, 100).wait(1, $a)", self.context, mapping, True)
        await self.assert_time_randomized(macro, 0.02, 0.08)

    async def test_wait_4_ranged_double_get(self):
        mapping = DummyMapping()
        mapping.macro_key_sleep_ms = 0
        macro = Parser.parse(
            "set(a, 1).set(b, 100).wait($a, $b)", self.context, mapping, True
        )
        await self.assert_time_randomized(macro, 0.02, 0.08)


if __name__ == "__main__":
    unittest.main()
