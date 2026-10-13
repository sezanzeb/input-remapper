#!/usr/bin/env python3
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

import asyncio
import unittest

from inputremapper.configs.validation_errors import MacroError
from inputremapper.injection.macros.macro import macro_variables
from inputremapper.injection.macros.parse import Parser
from tests.lib.test_setup import test_setup
from tests.unit.test_macros.macro_test_base import MacroTestBase, DummyMapping


@test_setup
class TestWhileEq(MacroTestBase):
    async def test_does_not_run_when_condition_is_already_false(self):
        macro_variables.set("while_eq_a", 0)
        macro = Parser.parse(
            "while_eq(while_eq_a, 1, key(a))", self.context, DummyMapping
        )
        await macro.run(self.handler)
        self.assertListEqual(self.result, [])
        self.assertFalse(macro.running)

    async def test_stops_when_variable_changes(self):
        macro_variables.set("while_eq_b", 1)
        macro = Parser.parse(
            "while_eq(while_eq_b, 1, key(a).wait(10))", self.context, DummyMapping
        )

        async def stop_soon():
            await asyncio.sleep(0.05)
            # simulating a *different* mapping's `set()` stopping this loop
            macro_variables.set("while_eq_b", 0)

        asyncio.ensure_future(stop_soon())
        await asyncio.wait_for(macro.run(self.handler), timeout=1)

        # it actually ran the child macro at least once while the
        # condition was true
        self.assertGreater(len(self.result), 0)

        # and it returned (not just idling) once the condition became false,
        # unlike `repeat`, which keeps a fixed count running regardless
        self.assertFalse(macro.running)

    async def test_can_be_retriggered_immediately_after_stopping(self):
        # this is the whole point of `while_eq` over `repeat`+`if_eq`: since
        # the loop actually returns instead of running out a fixed budget,
        # the macro can be started again right away
        macro_variables.set("while_eq_c", 1)
        macro = Parser.parse(
            "while_eq(while_eq_c, 1, key(a).wait(10))", self.context, DummyMapping
        )

        async def stop_soon():
            await asyncio.sleep(0.05)
            macro_variables.set("while_eq_c", 0)

        asyncio.ensure_future(stop_soon())
        await asyncio.wait_for(macro.run(self.handler), timeout=1)
        self.assertFalse(macro.running)

        macro_variables.set("while_eq_c", 1)

        async def stop_again_soon():
            await asyncio.sleep(0.05)
            macro_variables.set("while_eq_c", 0)

        asyncio.ensure_future(stop_again_soon())
        # if the first run left the macro "running", this would silently
        # do nothing and the timeout would never be hit
        await asyncio.wait_for(macro.run(self.handler), timeout=1)
        self.assertFalse(macro.running)

    async def test_raises_error(self):
        # missing the macro argument
        self.assertRaises(
            MacroError, Parser.parse, "while_eq(a, 1)", self.context
        )
        Parser.parse("while_eq(a, 1, key(a))", self.context)  # no error


if __name__ == "__main__":
    unittest.main()
