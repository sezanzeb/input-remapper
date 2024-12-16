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


import asyncio
import unittest

from inputremapper.configs.preset import Preset
from inputremapper.injection.context import Context
from inputremapper.injection.global_uinputs import GlobalUInputs, UInput
from inputremapper.injection.macros.macro import Macro, macro_variables
from inputremapper.injection.mapping_handlers.mapping_parser import MappingParser
from tests.lib.fixtures import fixtures
from tests.lib.logger import logger
from tests.lib.patches import InputDevice


class MacroTestBase(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        macro_variables.start()

    def setUp(self):
        self.result = []
        self.global_uinputs = GlobalUInputs(UInput)
        self.mapping_parser = MappingParser(self.global_uinputs)

        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            # suddenly "There is no current event loop in thread 'MainThread'"
            # errors started to appear
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        self.source_device = InputDevice(fixtures.bar_device.path)

        self.context = Context(
            Preset(),
            source_devices={fixtures.bar_device.get_device_hash(): self.source_device},
            forward_devices={},
            mapping_parser=self.mapping_parser,
        )

    def tearDown(self):
        self.result = []

    def handler(self, type_: int, code: int, value: int):
        """Where macros should write codes to."""
        logger.info(f"macro wrote{(type_, code, value)}")
        self.result.append((type_, code, value))

    async def trigger_sequence(self, macro: Macro, event):
        for listener in self.context.listeners:
            asyncio.ensure_future(listener(event))
            # this still might cause race conditions and the test to fail
            await asyncio.sleep(0)

        macro.press_trigger()
        if macro.running:
            return
        asyncio.ensure_future(macro.run(self.handler))

    async def release_sequence(self, macro: Macro, event):
        for listener in self.context.listeners:
            asyncio.ensure_future(listener(event))
            # this still might cause race conditions and the test to fail
            await asyncio.sleep(0)

        macro.release_trigger()

    def count_child_macros(self, macro) -> int:
        count = 0
        for task in macro.tasks:
            count += len(task.child_macros)
            for child_macro in task.child_macros:
                count += self.count_child_macros(child_macro)
        return count

    def count_tasks(self, macro) -> int:
        count = len(macro.tasks)
        for task in macro.tasks:
            for child_macro in task.child_macros:
                count += self.count_tasks(child_macro)
        return count


class DummyMapping:
    macro_key_sleep_ms = 10
    rel_rate = 60
    target_uinput = "keyboard + mouse"


if __name__ == "__main__":
    unittest.main()
