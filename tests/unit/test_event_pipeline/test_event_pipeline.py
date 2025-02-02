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
from typing import Iterable

import evdev
from evdev.ecodes import (
    EV_KEY,
    EV_ABS,
    EV_REL,
    ABS_X,
    ABS_Y,
    REL_X,
    REL_Y,
    REL_HWHEEL,
    REL_WHEEL,
    REL_WHEEL_HI_RES,
    REL_HWHEEL_HI_RES,
)

from inputremapper.configs.input_config import InputCombination, InputConfig
from inputremapper.configs.keyboard_layout import keyboard_layout
from inputremapper.configs.mapping import (
    Mapping,
    REL_XY_SCALING,
    WHEEL_SCALING,
    WHEEL_HI_RES_SCALING,
    DEFAULT_REL_RATE,
)
from inputremapper.configs.preset import Preset
from inputremapper.injection.context import Context
from inputremapper.injection.event_reader import EventReader
from inputremapper.injection.global_uinputs import GlobalUInputs, UInput
from inputremapper.injection.mapping_handlers.mapping_parser import MappingParser
from inputremapper.input_event import InputEvent
from tests.lib.cleanup import cleanup
from tests.lib.constants import MAX_ABS, MIN_ABS
from tests.lib.fixtures import Fixture, fixtures
from tests.lib.logger import logger
from tests.lib.test_setup import test_setup


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


@test_setup
class TestAbsToAbs(EventPipelineTestBase):
    async def test_abs_to_abs(self):
        gain = 0.5
        # left x to mouse x
        input_config = InputConfig(type=EV_ABS, code=ABS_X)
        mapping_config = {
            "input_combination": InputCombination([input_config]).to_config(),
            "target_uinput": "gamepad",
            "output_type": EV_ABS,
            "output_code": ABS_X,
            "gain": gain,
            "deadzone": 0,
        }
        mapping_1 = Mapping(**mapping_config)
        preset = Preset()
        preset.add(mapping_1)
        input_config = InputConfig(type=EV_ABS, code=ABS_Y)
        mapping_config["input_combination"] = InputCombination(
            [input_config]
        ).to_config()
        mapping_config["output_code"] = ABS_Y
        mapping_2 = Mapping(**mapping_config)
        preset.add(mapping_2)

        x = MAX_ABS
        y = MAX_ABS

        event_reader = self.create_event_reader(preset, fixtures.gamepad)

        await self.send_events(
            [
                InputEvent.abs(ABS_X, -x),
                InputEvent.abs(ABS_Y, y),
            ],
            event_reader,
        )

        await asyncio.sleep(0.2)

        history = self.global_uinputs.get_uinput("gamepad").write_history
        self.assertEqual(
            history,
            [
                InputEvent.from_tuple((3, 0, MIN_ABS / 2)),
                InputEvent.from_tuple((3, 1, MAX_ABS / 2)),
            ],
        )

    async def test_abs_to_abs_with_input_switch(self):
        gain = 0.5
        input_combination = InputCombination(
            (
                InputConfig(type=EV_ABS, code=0),
                InputConfig(type=EV_ABS, code=1, analog_threshold=10),
            )
        )
        # left x to mouse x
        mapping_config = {
            "input_combination": input_combination.to_config(),
            "target_uinput": "gamepad",
            "output_type": EV_ABS,
            "output_code": ABS_X,
            "gain": gain,
            "deadzone": 0,
        }
        mapping_1 = Mapping(**mapping_config)
        preset = Preset()
        preset.add(mapping_1)

        x = MAX_ABS
        y = MAX_ABS

        event_reader = self.create_event_reader(preset, fixtures.gamepad)

        await self.send_events(
            [
                InputEvent.abs(ABS_X, -x // 5),  # will not map
                InputEvent.abs(ABS_X, -x),  # will map later
                # switch axis on sends initial position (previous event)
                InputEvent.abs(ABS_Y, y),
                InputEvent.abs(ABS_X, x),  # normally mapped
                InputEvent.abs(ABS_Y, y // 15),  # off, re-centers axis
                InputEvent.abs(ABS_X, -x // 5),  # will not map
            ],
            event_reader,
        )

        await asyncio.sleep(0.2)

        history = self.global_uinputs.get_uinput("gamepad").write_history
        self.assertEqual(
            history,
            [
                InputEvent.from_tuple((3, 0, MIN_ABS / 2)),
                InputEvent.from_tuple((3, 0, MAX_ABS / 2)),
                InputEvent.from_tuple((3, 0, 0)),
            ],
        )


@test_setup
class TestAbsToRel(EventPipelineTestBase):
    async def test_abs_to_rel(self):
        """Map gamepad EV_ABS events to EV_REL events."""

        rel_rate = 60  # rate [Hz] at which events are produced
        gain = 0.5  # halve the speed of the rel axis
        # left x to mouse x
        input_config = InputConfig(type=EV_ABS, code=ABS_X)
        mapping_config = {
            "input_combination": InputCombination([input_config]).to_config(),
            "target_uinput": "mouse",
            "output_type": EV_REL,
            "output_code": REL_X,
            "rel_rate": rel_rate,
            "gain": gain,
            "deadzone": 0,
        }
        mapping_1 = Mapping(**mapping_config)
        preset = Preset()
        preset.add(mapping_1)
        # left y to mouse y
        input_config = InputConfig(type=EV_ABS, code=ABS_Y)
        mapping_config["input_combination"] = InputCombination(
            [input_config]
        ).to_config()
        mapping_config["output_code"] = REL_Y
        mapping_2 = Mapping(**mapping_config)
        preset.add(mapping_2)

        # set input axis to 100% in order to move
        # (gain * REL_XY_SCALING) pixel per event
        x = MAX_ABS
        y = MAX_ABS

        event_reader = self.create_event_reader(preset, fixtures.gamepad)

        await self.send_events(
            [
                InputEvent.abs(ABS_X, -x),
                InputEvent.abs(ABS_Y, -y),
            ],
            event_reader,
        )
        # wait a bit more for it to sum up
        sleep = 0.5
        await asyncio.sleep(sleep)
        # stop it
        await self.send_events(
            [
                InputEvent.abs(ABS_X, 0),
                InputEvent.abs(ABS_Y, 0),
            ],
            event_reader,
        )

        mouse_history = self.global_uinputs.get_uinput("mouse").write_history

        if mouse_history[0].type == EV_ABS:
            raise AssertionError(
                "The injector probably just forwarded them unchanged"
                # possibly in addition to writing mouse events
            )

        self.assertAlmostEqual(len(mouse_history), rel_rate * sleep * 2, delta=5)

        # those may be in arbitrary order
        expected_value = -gain * REL_XY_SCALING * (rel_rate / DEFAULT_REL_RATE)
        count_x = mouse_history.count((EV_REL, REL_X, expected_value))
        count_y = mouse_history.count((EV_REL, REL_Y, expected_value))
        self.assertGreater(count_x, 1)
        self.assertGreater(count_y, 1)
        # only those two types of events were written
        self.assertEqual(len(mouse_history), count_x + count_y)

    async def test_abs_to_wheel_hi_res_quirk(self):
        """When mapping to wheel events we always expect to see both,
        REL_WHEEL and REL_WHEEL_HI_RES events with an accumulative value ratio of 1/120
        """
        rel_rate = 60  # rate [Hz] at which events are produced
        gain = 1
        # left x to mouse x
        input_config = InputConfig(type=EV_ABS, code=ABS_X)
        mapping_config = {
            "input_combination": InputCombination([input_config]).to_config(),
            "target_uinput": "mouse",
            "output_type": EV_REL,
            "output_code": REL_WHEEL,
            "rel_rate": rel_rate,
            "gain": gain,
            "deadzone": 0,
        }
        mapping_1 = Mapping(**mapping_config)

        preset = Preset()
        preset.add(mapping_1)
        # left y to mouse y
        input_config = InputConfig(type=EV_ABS, code=ABS_Y)
        mapping_config["input_combination"] = InputCombination(
            [input_config]
        ).to_config()
        mapping_config["output_code"] = REL_HWHEEL_HI_RES
        mapping_2 = Mapping(**mapping_config)
        preset.add(mapping_2)

        # set input axis to 100% in order to move
        # speed*gain*rate=1*0.5*60 pixel per second
        x = MAX_ABS
        y = MAX_ABS

        event_reader = self.create_event_reader(preset, fixtures.gamepad)

        await self.send_events(
            [
                InputEvent.abs(ABS_X, x),
                InputEvent.abs(ABS_Y, -y),
            ],
            event_reader,
        )
        # wait a bit more for it to sum up
        sleep = 0.8
        await asyncio.sleep(sleep)
        # stop it
        await self.send_events(
            [
                InputEvent.abs(ABS_X, 0),
                InputEvent.abs(ABS_Y, 0),
            ],
            event_reader,
        )
        m_history = self.global_uinputs.get_uinput("mouse").write_history

        rel_wheel = sum([event.value for event in m_history if event.code == REL_WHEEL])
        rel_wheel_hi_res = sum(
            [event.value for event in m_history if event.code == REL_WHEEL_HI_RES]
        )
        rel_hwheel = sum(
            [event.value for event in m_history if event.code == REL_HWHEEL]
        )
        rel_hwheel_hi_res = sum(
            [event.value for event in m_history if event.code == REL_HWHEEL_HI_RES]
        )

        self.assertAlmostEqual(rel_wheel, rel_wheel_hi_res / 120, places=0)
        self.assertAlmostEqual(rel_hwheel, rel_hwheel_hi_res / 120, places=0)


@test_setup
class TestRelToBtn(EventPipelineTestBase):
    async def test_rel_to_btn(self):
        """Rel axis mapped to buttons are automatically released if no new rel event arrives."""

        # map those two to stuff
        w_up = (EV_REL, REL_WHEEL, -1)
        hw_right = (EV_REL, REL_HWHEEL, 1)

        # should be forwarded and present in the capabilities
        hw_left = (EV_REL, REL_HWHEEL, -1)

        keyboard_layout.clear()
        code_b = 91
        code_c = 92
        keyboard_layout._set("b", code_b)
        keyboard_layout._set("c", code_c)

        # set a high release timeout to make sure the tests pass
        release_timeout = 0.2
        mapping_1 = Mapping.from_combination(
            InputCombination(InputCombination.from_tuples(hw_right)), "keyboard", "k(b)"
        )
        mapping_2 = Mapping.from_combination(
            InputCombination(InputCombination.from_tuples(w_up)), "keyboard", "c"
        )
        mapping_1.release_timeout = release_timeout
        mapping_2.release_timeout = release_timeout

        preset = Preset()
        preset.add(mapping_1)
        preset.add(mapping_2)

        event_reader = self.create_event_reader(preset, fixtures.foo_device_2_mouse)

        await self.send_events(
            [InputEvent.from_tuple(hw_right), InputEvent.from_tuple(w_up)] * 5,
            event_reader,
        )
        # wait less than the release timeout and send more events
        await asyncio.sleep(release_timeout / 5)
        await self.send_events(
            [InputEvent.from_tuple(hw_right), InputEvent.from_tuple(w_up)] * 5
            + [InputEvent.from_tuple(hw_left)]
            * 3,  # one event will release hw_right, the others are forwarded
            event_reader,
        )
        # wait more than the release_timeout to make sure all handlers finish
        await asyncio.sleep(release_timeout * 1.2)

        keyboard_history = self.global_uinputs.get_uinput("keyboard").write_history
        forwarded_history = self.forward_uinput.write_history
        self.assertEqual(keyboard_history.count((EV_KEY, code_b, 1)), 1)
        self.assertEqual(keyboard_history.count((EV_KEY, code_c, 1)), 1)
        self.assertEqual(keyboard_history.count((EV_KEY, code_b, 0)), 1)
        self.assertEqual(keyboard_history.count((EV_KEY, code_c, 0)), 1)
        # the unmapped wheel direction
        self.assertEqual(forwarded_history.count(hw_left), 2)

        # the unmapped wheel won't get a debounced release command, it's
        # forwarded as is
        self.assertNotIn((EV_REL, REL_HWHEEL, 0), forwarded_history)

    async def test_rel_trigger_threshold(self):
        """Test that different activation points for rel_to_btn work correctly."""

        # at 5 map to a
        mapping_1 = Mapping.from_combination(
            InputCombination(
                [InputConfig(type=EV_REL, code=REL_X, analog_threshold=5)]
            ),
            output_symbol="a",
        )
        # at 15 map to b
        mapping_2 = Mapping.from_combination(
            InputCombination(
                [InputConfig(type=EV_REL, code=REL_X, analog_threshold=15)]
            ),
            output_symbol="b",
        )
        release_timeout = 0.2  # give some time to do assertions before the release
        mapping_1.release_timeout = release_timeout
        mapping_2.release_timeout = release_timeout
        preset = Preset()
        preset.add(mapping_1)
        preset.add(mapping_2)

        a = keyboard_layout.get("a")
        b = keyboard_layout.get("b")

        event_reader = self.create_event_reader(preset, fixtures.foo_device_2_mouse)

        await self.send_events(
            [
                InputEvent.rel(REL_X, -5),  # forward
                InputEvent.rel(REL_X, 0),  # forward
                InputEvent.rel(REL_X, 3),  # forward
                InputEvent.rel(REL_X, 10),  # trigger a
            ],
            event_reader,
        )
        await asyncio.sleep(release_timeout * 1.5)  # release a
        keyboard_history = self.global_uinputs.get_uinput("keyboard").write_history

        self.assertEqual(keyboard_history, [(EV_KEY, a, 1), (EV_KEY, a, 0)])
        self.assertEqual(keyboard_history.count((EV_KEY, a, 1)), 1)
        self.assertEqual(keyboard_history.count((EV_KEY, a, 0)), 1)
        self.assertNotIn((EV_KEY, b, 1), keyboard_history)

        await self.send_events(
            [
                InputEvent.rel(REL_X, 10),  # trigger a
                InputEvent.rel(REL_X, 20),  # trigger b
                InputEvent.rel(REL_X, 10),  # release b
            ],
            event_reader,
        )
        keyboard_history = self.global_uinputs.get_uinput("keyboard").write_history
        self.assertEqual(keyboard_history.count((EV_KEY, a, 1)), 2)
        self.assertEqual(keyboard_history.count((EV_KEY, b, 1)), 1)
        self.assertEqual(keyboard_history.count((EV_KEY, b, 0)), 1)
        self.assertEqual(keyboard_history.count((EV_KEY, a, 0)), 1)

        await asyncio.sleep(release_timeout * 1.5)  # release a
        keyboard_history = self.global_uinputs.get_uinput("keyboard").write_history
        forwarded_history = self.forward_uinput.write_history
        self.assertEqual(keyboard_history.count((EV_KEY, a, 0)), 2)
        self.assertEqual(
            forwarded_history,
            [(EV_REL, REL_X, -5), (EV_REL, REL_X, 0), (EV_REL, REL_X, 3)],
        )


@test_setup
class TestAbsToBtn(EventPipelineTestBase):
    async def test_abs_trigger_threshold(self):
        """Test that different activation points for abs_to_btn work correctly."""

        # at 30% map to a
        mapping_1 = Mapping.from_combination(
            InputCombination(
                [InputConfig(type=EV_ABS, code=ABS_X, analog_threshold=30)]
            ),
            output_symbol="a",
        )
        # at 70% map to b
        mapping_2 = Mapping.from_combination(
            InputCombination(
                [InputConfig(type=EV_ABS, code=ABS_X, analog_threshold=70)]
            ),
            output_symbol="b",
        )
        preset = Preset()
        preset.add(mapping_1)
        preset.add(mapping_2)

        a = keyboard_layout.get("a")
        b = keyboard_layout.get("b")

        event_reader = self.create_event_reader(preset, fixtures.gamepad)

        await self.send_events(
            [
                # -10%, do nothing
                InputEvent.abs(ABS_X, MIN_ABS // 10),
                # 0%, do noting
                InputEvent.abs(ABS_X, 0),
                # 10%, do nothing
                InputEvent.abs(ABS_X, MAX_ABS // 10),
                # 50%, trigger a
                InputEvent.abs(ABS_X, MAX_ABS // 2),
            ],
            event_reader,
        )
        keyboard_history = self.global_uinputs.get_uinput("keyboard").write_history

        self.assertEqual(keyboard_history.count((EV_KEY, a, 1)), 1)
        self.assertNotIn((EV_KEY, a, 0), keyboard_history)
        self.assertNotIn((EV_KEY, b, 1), keyboard_history)

        await self.send_events(
            [
                # 80%, trigger b
                InputEvent.abs(ABS_X, int(MAX_ABS * 0.8)),
                InputEvent.abs(ABS_X, MAX_ABS // 2),  # 50%, release b
            ],
            event_reader,
        )
        keyboard_history = self.global_uinputs.get_uinput("keyboard").write_history
        self.assertEqual(keyboard_history.count((EV_KEY, a, 1)), 1)
        self.assertEqual(keyboard_history.count((EV_KEY, b, 1)), 1)
        self.assertEqual(keyboard_history.count((EV_KEY, b, 0)), 1)
        self.assertNotIn((EV_KEY, a, 0), keyboard_history)

        # 0% release a
        await event_reader.handle(InputEvent.abs(ABS_X, 0))
        keyboard_history = self.global_uinputs.get_uinput("keyboard").write_history
        forwarded_history = self.forward_uinput.write_history
        self.assertEqual(keyboard_history.count((EV_KEY, a, 0)), 1)
        self.assertEqual(len(forwarded_history), 0)


@test_setup
class TestRelToRel(EventPipelineTestBase):
    async def _test(self, input_code, input_value, output_code, output_value, gain=1):
        preset = Preset()

        input_config = InputConfig(type=EV_REL, code=input_code)
        mapping = Mapping(
            input_combination=InputCombination([input_config]).to_config(),
            target_uinput="mouse",
            output_type=EV_REL,
            output_code=output_code,
            deadzone=0,
            gain=gain,
        )
        preset.add(mapping)

        event_reader = self.create_event_reader(preset, fixtures.gamepad)

        await self.send_events(
            [InputEvent(0, 0, EV_REL, input_code, input_value)],
            event_reader,
        )

        history = self.global_uinputs.get_uinput("mouse").write_history

        self.assertEqual(len(history), 1)
        self.assertEqual(
            history[0],
            InputEvent(0, 0, EV_REL, output_code, output_value),
        )

    async def test_wheel_to_y(self):
        await self._test(
            input_code=REL_WHEEL,
            input_value=2 * WHEEL_SCALING,
            output_code=REL_Y,
            output_value=2 * REL_XY_SCALING,
        )

    async def test_hi_res_wheel_to_y(self):
        await self._test(
            input_code=REL_WHEEL_HI_RES,
            input_value=3 * WHEEL_HI_RES_SCALING,
            output_code=REL_Y,
            output_value=3 * REL_XY_SCALING,
        )

    async def test_x_to_hwheel(self):
        # injects both hi_res and regular wheel events at the same time

        input_code = REL_X
        input_value = 100
        output_code = REL_HWHEEL
        gain = 2

        output_value = int(input_value / REL_XY_SCALING * WHEEL_SCALING * gain)
        output_value_hi_res = int(
            input_value / REL_XY_SCALING * WHEEL_HI_RES_SCALING * gain
        )

        preset = Preset()

        input_config = InputConfig(type=EV_REL, code=input_code)
        mapping = Mapping(
            input_combination=InputCombination([input_config]).to_config(),
            target_uinput="mouse",
            output_type=EV_REL,
            output_code=output_code,
            deadzone=0,
            gain=gain,
        )
        preset.add(mapping)

        event_reader = self.create_event_reader(preset, fixtures.gamepad)

        await self.send_events(
            [InputEvent(0, 0, EV_REL, input_code, input_value)],
            event_reader,
        )

        history = self.global_uinputs.get_uinput("mouse").write_history
        # injects both REL_WHEEL and REL_WHEEL_HI_RES events
        self.assertEqual(len(history), 2)
        self.assertEqual(
            history[0],
            InputEvent(
                0,
                0,
                EV_REL,
                REL_HWHEEL,
                output_value,
            ),
        )

        self.assertEqual(
            history[1],
            InputEvent(
                0,
                0,
                EV_REL,
                REL_HWHEEL_HI_RES,
                output_value_hi_res,
            ),
        )

    async def test_remainder(self):
        preset = Preset()
        history = self.global_uinputs.get_uinput("mouse").write_history

        # REL_WHEEL_HI_RES to REL_Y
        input_config = InputConfig(type=EV_REL, code=REL_WHEEL_HI_RES)
        gain = 0.01
        mapping = Mapping(
            input_combination=InputCombination([input_config]).to_config(),
            target_uinput="mouse",
            output_type=EV_REL,
            output_code=REL_Y,
            deadzone=0,
            gain=gain,
        )
        preset.add(mapping)

        event_reader = self.create_event_reader(preset, fixtures.gamepad)

        events_until_one_rel_y_written = int(
            WHEEL_HI_RES_SCALING / REL_XY_SCALING / gain
        )
        # due to the low gain and low input value, it needs to be sent many times
        # until one REL_Y event is written
        await self.send_events(
            [InputEvent(0, 0, EV_REL, REL_WHEEL_HI_RES, 1)]
            * (events_until_one_rel_y_written - 1),
            event_reader,
        )
        self.assertEqual(len(history), 0)

        # write the final event that causes the input to accumulate to 1
        # plus one extra event because of floating-point math
        await self.send_events(
            [InputEvent(0, 0, EV_REL, REL_WHEEL_HI_RES, 1)],
            event_reader,
        )
        self.assertEqual(len(history), 1)
        self.assertEqual(
            history[0],
            InputEvent(0, 0, EV_REL, REL_Y, 1),
        )

        # repeat it one more time to see if the remainder is reset correctly
        await self.send_events(
            [InputEvent(0, 0, EV_REL, REL_WHEEL_HI_RES, 1)]
            * (events_until_one_rel_y_written - 1),
            event_reader,
        )
        self.assertEqual(len(history), 1)

        # the event that causes the second REL_Y to be written
        # this should never need the one extra if the remainder is reset correctly
        await self.send_events(
            [InputEvent(0, 0, EV_REL, REL_WHEEL_HI_RES, 1)],
            event_reader,
        )
        self.assertEqual(len(history), 2)
        self.assertEqual(
            history[1],
            InputEvent(0, 0, EV_REL, REL_Y, 1),
        )


if __name__ == "__main__":
    unittest.main()
