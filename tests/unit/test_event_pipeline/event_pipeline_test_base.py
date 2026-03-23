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
from typing import Iterable

import evdev

from inputremapper.configs.preset import Preset
from inputremapper.injection.context import Context
from inputremapper.injection.event_reader import EventReader
from inputremapper.injection.global_uinputs import GlobalUInputs, UInput
from inputremapper.injection.mapping_handlers.mapping_parser import MappingParser
from inputremapper.input_event import InputEvent
from tests.lib.cleanup import cleanup
from tests.lib.logger import logger
from tests.lib.fixtures import Fixture


class EventPipelineTestBase(unittest.IsolatedAsyncioTestCase):
    """Test the event pipeline form event_reader to UInput."""

    def setUp(self):
        self.global_uinputs = GlobalUInputs(UInput)
        self.global_uinputs.prepare_all()
        self.mapping_parser = MappingParser(self.global_uinputs)
        self.global_uinputs.is_service = True
        self.global_uinputs.prepare_all()
        self.forward_uinput = evdev.UInput(name="test-forward-uinput")
        self.stop_event = asyncio.Event()

    def tearDown(self) -> None:
        cleanup()

    async def asyncTearDown(self) -> None:
        logger.info("setting stop_event for the reader")
        self.stop_event.set()
        await asyncio.sleep(0.5)

    @staticmethod
    async def send_events(events: Iterable[InputEvent], event_reader: EventReader):
        for event in events:
            logger.info("sending into event_pipeline: %s", event)
            await event_reader.handle(event)

    def create_event_reader(
        self,
        preset: Preset,
        source: Fixture,
    ) -> EventReader:
        """Create and start an EventReader."""
        context = Context(
            preset,
            source_devices={},
            forward_devices={source.get_device_hash(): self.forward_uinput},
            mapping_parser=self.mapping_parser,
        )
        reader = EventReader(
            context,
            evdev.InputDevice(source.path),
            self.stop_event,
        )
        asyncio.ensure_future(reader.run())
        return reader


if __name__ == "__main__":
    unittest.main()
