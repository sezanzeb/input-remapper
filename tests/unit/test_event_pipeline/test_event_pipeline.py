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
    BTN_A,
    REL_HWHEEL,
    REL_WHEEL,
    REL_WHEEL_HI_RES,
    REL_HWHEEL_HI_RES,
    ABS_HAT0X,
    BTN_LEFT,
    BTN_B,
    KEY_A,
    ABS_HAT0Y,
    KEY_B,
    KEY_C,
    BTN_TL,
)

from inputremapper.configs.mapping import (
    Mapping,
    REL_XY_SCALING,
    WHEEL_SCALING,
    WHEEL_HI_RES_SCALING,
    DEFAULT_REL_RATE,
)
from inputremapper.configs.preset import Preset
from inputremapper.configs.system_mapping import system_mapping
from inputremapper.configs.input_config import InputCombination, InputConfig
from inputremapper.injection.context import Context
from inputremapper.injection.event_reader import EventReader
from inputremapper.injection.global_uinputs import global_uinputs
from inputremapper.input_event import InputEvent
from tests.lib.cleanup import cleanup
from tests.lib.logger import logger
from tests.lib.constants import MAX_ABS, MIN_ABS
from tests.lib.stuff import convert_to_internal_events
from tests.lib.fixtures import (
    Fixture,
    fixtures,
    get_key_mapping,
    get_combination_config,
)


class EventPipelineTestBase(unittest.IsolatedAsyncioTestCase):
    """Test the event pipeline form event_reader to UInput."""

    def setUp(self):
        global_uinputs.is_service = True
        global_uinputs.prepare_all()
        self.forward_uinput = evdev.UInput()
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
        )
        reader = EventReader(
            context,
            evdev.InputDevice(source.path),
            self.stop_event,
        )
        asyncio.ensure_future(reader.run())
        return reader


class TestIdk(EventPipelineTestBase):
    async def test_any_event_as_button(self):
        """As long as there is an event handler and a mapping we should be able
        to map anything to a button"""

        # value needs to be higher than 10% below center of axis (absinfo)
        w_down = (EV_ABS, ABS_Y, -12345)
        w_up = (EV_ABS, ABS_Y, 0)

        s_down = (EV_ABS, ABS_Y, 12345)
        s_up = (EV_ABS, ABS_Y, 0)

        d_down = (EV_REL, REL_X, 100)
        d_up = (EV_REL, REL_X, 0)

        a_down = (EV_REL, REL_X, -100)
        a_up = (EV_REL, REL_X, 0)

        b_down = (EV_ABS, ABS_HAT0X, 1)
        b_up = (EV_ABS, ABS_HAT0X, 0)

        c_down = (EV_ABS, ABS_HAT0X, -1)
        c_up = (EV_ABS, ABS_HAT0X, 0)

        # first change the system mapping because Mapping will validate against it
        system_mapping.clear()
        code_w = 71
        code_b = 72
        code_c = 73
        code_d = 74
        code_a = 75
        code_s = 76
        system_mapping._set("w", code_w)
        system_mapping._set("d", code_d)
        system_mapping._set("a", code_a)
        system_mapping._set("s", code_s)
        system_mapping._set("b", code_b)
        system_mapping._set("c", code_c)

        preset = Preset()
        preset.add(
            get_key_mapping(
                InputCombination(get_combination_config(b_down)), "keyboard", "b"
            )
        )
        preset.add(
            get_key_mapping(
                InputCombination(get_combination_config(c_down)), "keyboard", "c"
            )
        )
        preset.add(
            get_key_mapping(
                InputCombination(get_combination_config((*w_down[:2], -10))),
                "keyboard",
                "w",
            )
        )
        preset.add(
            get_key_mapping(
                InputCombination(get_combination_config((*d_down[:2], 10))),
                "keyboard",
                "k(d)",
            )
        )
        preset.add(
            get_key_mapping(
                InputCombination(get_combination_config((*s_down[:2], 10))),
                "keyboard",
                "s",
            )
        )
        preset.add(
            get_key_mapping(
                InputCombination(get_combination_config((*a_down[:2], -10))),
                "keyboard",
                "a",
            )
        )

        # gamepad fixture
        event_reader = self.create_event_reader(preset, fixtures.gamepad)

        await self.send_events(
            [
                InputEvent.from_tuple(b_down),
                InputEvent.from_tuple(c_down),
                InputEvent.from_tuple(w_down),
                InputEvent.from_tuple(d_down),
                InputEvent.from_tuple(s_down),
                InputEvent.from_tuple(a_down),
                InputEvent.from_tuple(b_up),
                InputEvent.from_tuple(c_up),
                InputEvent.from_tuple(w_up),
                InputEvent.from_tuple(d_up),
                InputEvent.from_tuple(s_up),
                InputEvent.from_tuple(a_up),
            ],
            event_reader,
        )
        # wait a bit for the rel_to_btn handler to send the key up
        await asyncio.sleep(0.1)

        history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )

        self.assertEqual(history.count((EV_KEY, code_b, 1)), 1)
        self.assertEqual(history.count((EV_KEY, code_c, 1)), 1)
        self.assertEqual(history.count((EV_KEY, code_w, 1)), 1)
        self.assertEqual(history.count((EV_KEY, code_d, 1)), 1)
        self.assertEqual(history.count((EV_KEY, code_a, 1)), 1)
        self.assertEqual(history.count((EV_KEY, code_s, 1)), 1)
        self.assertEqual(history.count((EV_KEY, code_b, 0)), 1)
        self.assertEqual(history.count((EV_KEY, code_c, 0)), 1)
        self.assertEqual(history.count((EV_KEY, code_w, 0)), 1)
        self.assertEqual(history.count((EV_KEY, code_d, 0)), 1)
        self.assertEqual(history.count((EV_KEY, code_a, 0)), 1)
        self.assertEqual(history.count((EV_KEY, code_s, 0)), 1)

    async def test_reset_releases_keys(self):
        """Make sure that macros and keys are releases when the stop event is set."""
        preset = Preset()
        input_cfg = InputCombination(InputConfig(type=EV_KEY, code=1)).to_config()
        preset.add(
            get_key_mapping(input_combination=input_cfg, output_symbol="hold(a)")
        )

        input_cfg = InputCombination(InputConfig(type=EV_KEY, code=2)).to_config()
        preset.add(get_key_mapping(input_combination=input_cfg, output_symbol="b"))

        input_cfg = InputCombination(InputConfig(type=EV_KEY, code=3)).to_config()
        preset.add(
            get_key_mapping(
                input_combination=input_cfg, output_symbol="modify(c,hold(d))"
            ),
        )
        event_reader = self.create_event_reader(preset, fixtures.foo_device_2_keyboard)

        a = system_mapping.get("a")
        b = system_mapping.get("b")
        c = system_mapping.get("c")
        d = system_mapping.get("d")

        await self.send_events(
            [
                InputEvent.key(1, 1),
                InputEvent.key(2, 1),
                InputEvent.key(3, 1),
            ],
            event_reader,
        )
        await asyncio.sleep(0.1)

        forwarded_history = convert_to_internal_events(
            self.forward_uinput.write_history
        )
        keyboard_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )

        self.assertEqual(len(forwarded_history), 0)
        # a down, b down, c down, d down
        self.assertEqual(len(keyboard_history), 4)

        event_reader.context.reset()
        await asyncio.sleep(0.1)

        forwarded_history = convert_to_internal_events(
            self.forward_uinput.write_history
        )
        keyboard_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )

        self.assertEqual(len(forwarded_history), 0)
        # all a, b, c, d down+up
        self.assertEqual(len(keyboard_history), 8)
        keyboard_history = keyboard_history[-4:]
        self.assertIn((EV_KEY, a, 0), keyboard_history)
        self.assertIn((EV_KEY, b, 0), keyboard_history)
        self.assertIn((EV_KEY, c, 0), keyboard_history)
        self.assertIn((EV_KEY, d, 0), keyboard_history)

    async def test_forward_abs(self):
        """Test if EV_ABS events are forwarded when other events of the same input are not."""
        preset = Preset()
        # BTN_A -> 77
        system_mapping._set("b", 77)
        preset.add(
            get_key_mapping(
                InputCombination(InputConfig(type=EV_KEY, code=BTN_A)),
                "keyboard",
                "b",
            )
        )
        event_reader = self.create_event_reader(preset, fixtures.gamepad)

        # should forward them unmodified
        await self.send_events(
            [
                InputEvent.abs(ABS_X, 10),
                InputEvent.abs(ABS_Y, 20),
                InputEvent.abs(ABS_X, -30),
                InputEvent.abs(ABS_Y, -40),
                # send them to keyboard 77
                InputEvent.key(BTN_A, 1),
                InputEvent.key(BTN_A, 0),
            ],
            event_reader,
        )

        # convert the write-history to some easier to manage list
        history = convert_to_internal_events(self.forward_uinput.write_history)
        keyboard_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )

        self.assertEqual(history.count((EV_ABS, ABS_X, 10)), 1)
        self.assertEqual(history.count((EV_ABS, ABS_Y, 20)), 1)
        self.assertEqual(history.count((EV_ABS, ABS_X, -30)), 1)
        self.assertEqual(history.count((EV_ABS, ABS_Y, -40)), 1)
        self.assertEqual(keyboard_history.count((EV_KEY, 77, 1)), 1)
        self.assertEqual(keyboard_history.count((EV_KEY, 77, 0)), 1)

    async def test_forward_rel(self):
        """Test if EV_REL events are forwarded when other events of the same input are not."""
        preset = Preset()
        # BTN_A -> 77
        system_mapping._set("b", 77)
        preset.add(
            get_key_mapping(
                InputCombination(InputConfig(type=EV_KEY, code=BTN_LEFT)),
                "keyboard",
                "b",
            )
        )
        event_reader = self.create_event_reader(preset, fixtures.gamepad)

        # should forward them unmodified
        await self.send_events(
            [
                InputEvent.rel(REL_X, 10),
                InputEvent.rel(REL_Y, 20),
                InputEvent.rel(REL_X, -30),
                InputEvent.rel(REL_Y, -40),
                # send them to keyboard 77
                InputEvent.key(BTN_LEFT, 1),
                InputEvent.key(BTN_LEFT, 0),
            ],
            event_reader,
        )
        await asyncio.sleep(0.1)

        # convert the write-history to some easier to manage list
        history = convert_to_internal_events(self.forward_uinput.write_history)
        keyboard_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )

        self.assertEqual(history.count((EV_REL, REL_X, 10)), 1)
        self.assertEqual(history.count((EV_REL, REL_Y, 20)), 1)
        self.assertEqual(history.count((EV_REL, REL_X, -30)), 1)
        self.assertEqual(history.count((EV_REL, REL_Y, -40)), 1)
        self.assertEqual(keyboard_history.count((EV_KEY, 77, 1)), 1)
        self.assertEqual(keyboard_history.count((EV_KEY, 77, 0)), 1)

    async def test_combination(self):
        """Test if combinations map to keys properly."""
        a = system_mapping.get("a")
        b = system_mapping.get("b")
        c = system_mapping.get("c")

        origin = fixtures.gamepad
        origin_hash = origin.get_device_hash()

        mapping_1 = get_key_mapping(
            InputCombination(InputConfig.abs(ABS_X, 1, origin_hash)),
            output_symbol="a",
        )

        mapping_2 = get_key_mapping(
            InputCombination(
                [
                    InputConfig.abs(ABS_X, 1, origin_hash),
                    InputConfig.key(BTN_A, origin_hash),
                ]
            ),
            output_symbol="b",
        )

        mapping_3 = get_key_mapping(
            InputCombination(
                [
                    InputConfig.abs(ABS_X, 1, origin_hash),
                    InputConfig.key(BTN_A, origin_hash),
                    InputConfig.key(BTN_B, origin_hash),
                ]
            ),
            output_symbol="c",
        )

        preset = Preset()
        preset.add(mapping_1)
        preset.add(mapping_2)
        preset.add(mapping_3)

        event_reader = self.create_event_reader(preset, origin)

        # send_events awaits the event_reader to do its thing
        await self.send_events(
            [
                # forwarded
                InputEvent.key(BTN_A, 1, origin_hash),
                # triggers b, releases BTN_A, ABS_X
                InputEvent.abs(ABS_X, 1234, origin_hash),
                # triggers c, releases BTN_A, ABS_X, BTN_B
                InputEvent.key(BTN_B, 1, origin_hash),
            ],
            event_reader,
        )

        keyboard_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )

        forwarded_history = convert_to_internal_events(
            self.forward_uinput.write_history
        )

        self.assertNotIn((EV_KEY, a, 1), keyboard_history)

        # c and b should have been written, because the input from send_events
        # should trigger the combination
        self.assertEqual(keyboard_history.count((EV_KEY, c, 1)), 1)
        self.assertEqual(keyboard_history.count((EV_KEY, b, 1)), 1)

        self.assertEqual(forwarded_history.count((EV_KEY, BTN_A, 1)), 1)
        self.assertIn((EV_KEY, BTN_A, 0), forwarded_history)
        self.assertNotIn((EV_ABS, ABS_X, 1234), forwarded_history)
        self.assertNotIn((EV_KEY, BTN_B, 1), forwarded_history)

        # release b and c)
        await self.send_events(
            [InputEvent.abs(ABS_X, 0, origin_hash)],
            event_reader,
        )

        keyboard_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )

        self.assertNotIn((EV_KEY, a, 1), keyboard_history)
        self.assertNotIn((EV_KEY, a, 0), keyboard_history)
        self.assertEqual(keyboard_history.count((EV_KEY, c, 0)), 1)
        self.assertEqual(keyboard_history.count((EV_KEY, b, 0)), 1)

    async def test_ignore_hold(self):
        # hold as in event-value 2, not in macro-hold.
        # linux will generate events with value 2 after input-remapper injected
        # the key-press, so input-remapper doesn't need to forward them. That
        # would cause duplicate events of those values otherwise.
        key = (EV_KEY, KEY_A)
        ev_1 = InputEvent.from_tuple((*key, 1))
        ev_2 = InputEvent.from_tuple((*key, 2))
        ev_3 = InputEvent.from_tuple((*key, 0))

        preset = Preset()
        preset.add(
            get_key_mapping(
                InputCombination(get_combination_config(ev_1)), output_symbol="a"
            )
        )
        a = system_mapping.get("a")

        event_reader = self.create_event_reader(preset, fixtures.gamepad)
        await self.send_events(
            [
                InputEvent.from_tuple(ev_1),
                InputEvent.from_tuple(ev_2),
                InputEvent.from_tuple(ev_3),
            ],
            event_reader,
        )

        keyboard_history = global_uinputs.get_uinput("keyboard").write_history
        forwarded_history = self.forward_uinput.write_history
        self.assertEqual(len(keyboard_history), 2)
        self.assertEqual(len(forwarded_history), 0)
        self.assertNotIn((EV_KEY, a, 2), keyboard_history)

    async def test_ignore_disabled(self):
        origin = fixtures.gamepad
        origin_hash = origin.get_device_hash()

        ev_1 = InputEvent.abs(ABS_HAT0Y, 1, origin_hash)
        ev_2 = InputEvent.abs(ABS_HAT0Y, 0, origin_hash)

        ev_3 = InputEvent.abs(ABS_HAT0X, 1, origin_hash)  # disabled
        ev_4 = InputEvent.abs(ABS_HAT0X, 0, origin_hash)

        ev_5 = InputEvent.key(KEY_A, 1, origin_hash)
        ev_6 = InputEvent.key(KEY_A, 0, origin_hash)

        combi_1 = (ev_5, ev_3)
        combi_2 = (ev_3, ev_5)

        preset = Preset()
        preset.add(
            get_key_mapping(
                input_combination=InputCombination(
                    InputConfig.from_input_event(ev_1),
                ),
                output_symbol="a",
            )
        )
        preset.add(
            get_key_mapping(
                input_combination=InputCombination(
                    InputConfig.from_input_event(ev_3),
                ),
                output_symbol="disable",
            )
        )
        preset.add(
            get_key_mapping(
                input_combination=InputCombination(
                    (
                        InputConfig.from_input_event(combi_1[0]),
                        InputConfig.from_input_event(combi_1[1]),
                    )
                ),
                output_symbol="b",
            )
        )
        preset.add(
            get_key_mapping(
                input_combination=InputCombination(
                    (
                        InputConfig.from_input_event(combi_2[0]),
                        InputConfig.from_input_event(combi_2[1]),
                    )
                ),
                output_symbol="c",
            )
        )

        a = system_mapping.get("a")
        b = system_mapping.get("b")
        c = system_mapping.get("c")

        event_reader = self.create_event_reader(preset, origin)

        """Single keys"""
        await self.send_events(
            [
                ev_1,  # press a
                ev_3,  # disabled
                ev_2,  # release a
                ev_4,  # disabled
            ],
            event_reader,
        )
        keyboard_history = global_uinputs.get_uinput("keyboard").write_history
        forwarded_history = self.forward_uinput.write_history
        self.assertIn((EV_KEY, a, 1), keyboard_history)
        self.assertIn((EV_KEY, a, 0), keyboard_history)
        self.assertEqual(len(keyboard_history), 2)
        self.assertEqual(len(forwarded_history), 0)

        """A combination that ends in a disabled key"""
        # ev_5 should be forwarded and the combination triggered
        await self.send_events(combi_1, event_reader)
        keyboard_history = global_uinputs.get_uinput("keyboard").write_history
        forwarded_history = self.forward_uinput.write_history
        self.assertIn((EV_KEY, b, 1), keyboard_history)
        self.assertEqual(len(keyboard_history), 3)
        self.assertEqual(forwarded_history.count(ev_3), 0)
        self.assertEqual(forwarded_history.count(ev_5), 1)
        self.assertTrue(forwarded_history.count(ev_6) >= 1)

        # release what the combination maps to
        await self.send_events([ev_4, ev_6], event_reader)
        keyboard_history = global_uinputs.get_uinput("keyboard").write_history
        forwarded_history = self.forward_uinput.write_history
        self.assertIn((EV_KEY, b, 0), keyboard_history)
        self.assertEqual(len(keyboard_history), 4)
        self.assertEqual(forwarded_history.count(ev_3), 0)
        self.assertTrue(forwarded_history.count(ev_6) >= 1)

        """A combination that starts with a disabled key"""
        # only the combination should get triggered
        await self.send_events(combi_2, event_reader)
        keyboard_history = global_uinputs.get_uinput("keyboard").write_history
        forwarded_history = self.forward_uinput.write_history
        self.assertIn((EV_KEY, c, 1), keyboard_history)
        self.assertEqual(len(keyboard_history), 5)
        self.assertEqual(forwarded_history.count(ev_3), 0)
        self.assertEqual(forwarded_history.count(ev_5), 1)
        self.assertTrue(forwarded_history.count(ev_6) >= 1)

        # release what the combination maps to
        await self.send_events([ev_4, ev_6], event_reader)
        keyboard_history = global_uinputs.get_uinput("keyboard").write_history
        forwarded_history = self.forward_uinput.write_history
        for event in keyboard_history:
            print(event.event_tuple)
        self.assertIn((EV_KEY, c, 0), keyboard_history)
        self.assertEqual(len(keyboard_history), 6)
        self.assertEqual(forwarded_history.count(ev_3), 0)
        self.assertTrue(forwarded_history.count(ev_6) >= 1)

    async def test_combination_keycode_macro_mix(self):
        """Ev_1 triggers macro, ev_1 + ev_2 triggers key while the macro is
        still running"""

        down_1 = (EV_ABS, ABS_HAT0X, 1)
        down_2 = (EV_ABS, ABS_HAT0Y, -1)
        up_1 = (EV_ABS, ABS_HAT0X, 0)
        up_2 = (EV_ABS, ABS_HAT0Y, 0)

        a = system_mapping.get("a")
        b = system_mapping.get("b")

        preset = Preset()
        preset.add(
            get_key_mapping(
                InputCombination(get_combination_config(down_1)),
                output_symbol="h(k(a))",
            )
        )
        preset.add(
            get_key_mapping(
                InputCombination(get_combination_config(down_1, down_2)),
                output_symbol="b",
            )
        )

        event_reader = self.create_event_reader(preset, fixtures.gamepad)
        # macro starts
        await self.send_events([InputEvent.from_tuple(down_1)], event_reader)
        await asyncio.sleep(0.05)
        keyboard_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        forwarded_history = convert_to_internal_events(
            self.forward_uinput.write_history
        )
        self.assertEqual(len(forwarded_history), 0)
        self.assertGreater(len(keyboard_history), 1)
        self.assertNotIn((EV_KEY, b, 1), keyboard_history)
        self.assertIn((EV_KEY, a, 1), keyboard_history)
        self.assertIn((EV_KEY, a, 0), keyboard_history)

        # combination triggered
        await self.send_events([InputEvent.from_tuple(down_2)], event_reader)
        await asyncio.sleep(0)
        keyboard_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        self.assertIn((EV_KEY, b, 1), keyboard_history)

        len_a = len(global_uinputs.get_uinput("keyboard").write_history)
        await asyncio.sleep(0.05)
        len_b = len(global_uinputs.get_uinput("keyboard").write_history)
        # still running
        self.assertGreater(len_b, len_a)

        # release
        await self.send_events([InputEvent.from_tuple(up_1)], event_reader)
        keyboard_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        self.assertEqual(keyboard_history[-1], (EV_KEY, b, 0))
        await asyncio.sleep(0.05)
        len_c = len(global_uinputs.get_uinput("keyboard").write_history)
        await asyncio.sleep(0.05)
        len_d = len(global_uinputs.get_uinput("keyboard").write_history)
        # not running anymore
        self.assertEqual(len_c, len_d)

        await self.send_events([InputEvent.from_tuple(up_2)], event_reader)
        await asyncio.sleep(0.05)
        len_e = len(global_uinputs.get_uinput("keyboard").write_history)
        self.assertEqual(len_e, len_d)

    async def test_wheel_combination_release_failure(self):
        # test based on a bug that once occurred
        # 1 | 22.6698, ((1, 276, 1)) -------------- forwarding
        # 2 | 22.9904, ((1, 276, 1), (2, 8, -1)) -- maps to 30
        # 3 | 23.0103, ((1, 276, 1), (2, 8, -1)) -- duplicate key down
        # 4 | ... 34 more duplicate key downs (scrolling)
        # 5 | 23.7104, ((1, 276, 1), (2, 8, -1)) -- duplicate key down
        # 6 | 23.7283, ((1, 276, 0)) -------------- forwarding release
        # 7 | 23.7303, ((2, 8, -1)) --------------- forwarding
        # 8 | 23.7865, ((2, 8, 0)) ---------------- not forwarding release
        # line 7 should have been "duplicate key down" as well
        # line 8 should have released 30, instead it was never released
        #
        # Note: the test was modified for the new Event pipeline:
        # line 6 now releases the combination
        # line 7 get forwarded
        # line 8 get forwarded

        scroll = InputEvent.from_tuple((2, 8, -1))
        scroll_release = InputEvent.from_tuple((2, 8, 0))
        btn_down = InputEvent.key(276, 1)
        btn_up = InputEvent.key(276, 0)
        combination = InputCombination(get_combination_config((1, 276, 1), (2, 8, -1)))

        system_mapping.clear()
        system_mapping._set("a", 30)
        a = 30

        m = get_key_mapping(combination, output_symbol="a")
        m.release_timeout = 0.1  # a higher release timeout to give time for assertions

        preset = Preset()
        preset.add(m)

        event_reader = self.create_event_reader(preset, fixtures.foo_device_2_mouse)

        await self.send_events([btn_down], event_reader)
        forwarded_history = convert_to_internal_events(
            self.forward_uinput.write_history
        )
        self.assertEqual(forwarded_history[0], btn_down)

        await self.send_events([scroll], event_reader)
        # "maps to 30"
        keyboard_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        self.assertEqual(keyboard_history[0], (EV_KEY, a, 1))

        await self.send_events([scroll] * 5, event_reader)

        # nothing new since all of them were duplicate key downs
        keyboard_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        self.assertEqual(len(keyboard_history), 1)

        await self.send_events([btn_up], event_reader)
        # releasing the combination
        keyboard_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        self.assertEqual(keyboard_history[1], (EV_KEY, a, 0))

        # more scroll events
        # it should be ignored as duplicate key-down
        await self.send_events([scroll] * 5, event_reader)
        forwarded_history = convert_to_internal_events(
            self.forward_uinput.write_history
        )
        self.assertEqual(forwarded_history.count(scroll), 5)

        await self.send_events([scroll_release], event_reader)
        forwarded_history = convert_to_internal_events(
            self.forward_uinput.write_history
        )
        self.assertEqual(forwarded_history[-1], scroll_release)

    async def test_can_not_map(self):
        """Inject events to wrong or invalid uinput."""
        ev_1 = InputEvent.key(KEY_A, 1)
        ev_2 = InputEvent.key(KEY_B, 1)
        ev_3 = InputEvent.key(KEY_C, 1)

        ev_4 = InputEvent.key(KEY_A, 0)
        ev_5 = InputEvent.key(KEY_B, 0)
        ev_6 = InputEvent.key(KEY_C, 0)

        mapping_1 = Mapping(
            input_combination=InputCombination(InputConfig.from_input_event(ev_2)),
            target_uinput="keyboard",
            output_type=EV_KEY,
            output_code=BTN_TL,
        )
        mapping_2 = Mapping(
            input_combination=InputCombination(InputConfig.from_input_event(ev_3)),
            target_uinput="keyboard",
            output_type=EV_KEY,
            output_code=KEY_A,
        )

        preset = Preset()
        preset.add(mapping_1)
        preset.add(mapping_2)

        event_reader = self.create_event_reader(preset, fixtures.foo_device_2_mouse)
        # send key-down and up
        await self.send_events(
            [
                ev_1,
                ev_2,
                ev_3,
                ev_4,
                ev_5,
                ev_6,
            ],
            event_reader,
        )

        keyboard_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        forwarded_history = convert_to_internal_events(
            self.forward_uinput.write_history
        )

        self.assertEqual(len(forwarded_history), 4)
        self.assertEqual(len(keyboard_history), 2)
        self.assertIn(ev_1, forwarded_history)
        self.assertIn(ev_2, forwarded_history)
        self.assertIn(ev_4, forwarded_history)
        self.assertIn(ev_5, forwarded_history)
        self.assertNotIn(ev_3, forwarded_history)
        self.assertNotIn(ev_6, forwarded_history)

        self.assertIn((EV_KEY, KEY_A, 1), keyboard_history)
        self.assertIn((EV_KEY, KEY_A, 0), keyboard_history)

    async def test_axis_switch(self):
        """Test a mapping for an axis that can be switched on or off."""

        rel_rate = 60  # rate [Hz] at which events are produced
        gain = 0.5  # halve the speed of the rel axis
        preset = Preset()
        mouse = global_uinputs.get_uinput("mouse")
        forward_history = self.forward_uinput.write_history
        mouse_history = mouse.write_history

        # ABS_X to REL_Y if ABS_Y is above 10%
        combination = InputCombination(
            get_combination_config((EV_ABS, ABS_X, 0), (EV_ABS, ABS_Y, 10))
        )
        cfg = {
            "input_combination": combination.to_config(),
            "target_uinput": "mouse",
            "output_type": EV_REL,
            "output_code": REL_X,
            "rel_rate": rel_rate,
            "gain": gain,
            "deadzone": 0,
        }
        m1 = Mapping(**cfg)
        preset.add(m1)

        event_reader = self.create_event_reader(preset, fixtures.gamepad)

        # set ABS_X input to 100%
        await event_reader.handle(InputEvent.abs(ABS_X, MAX_ABS))

        # wait a bit more for nothing to sum up, because ABS_Y is still 0
        await asyncio.sleep(0.2)
        self.assertEqual(len(mouse_history), 0)
        self.assertEqual(len(forward_history), 1)
        self.assertEqual(
            InputEvent.from_event(forward_history[0]),
            (EV_ABS, ABS_X, MAX_ABS),
        )

        # move ABS_Y above 10%
        await self.send_events(
            (
                InputEvent.abs(ABS_Y, MAX_ABS * 0.05),
                InputEvent.abs(ABS_Y, MAX_ABS * 0.11),
                InputEvent.abs(ABS_Y, MAX_ABS * 0.5),
            ),
            event_reader,
        )

        # wait a bit more for it to sum up
        sleep = 0.5
        await asyncio.sleep(sleep)

        self.assertAlmostEqual(len(mouse_history), rel_rate * sleep, delta=3)
        self.assertEqual(len(forward_history), 1)

        # send some more x events
        await self.send_events(
            (
                InputEvent.abs(ABS_X, MAX_ABS),
                InputEvent.abs(ABS_X, MAX_ABS * 0.9),
            ),
            event_reader,
        )

        # stop it
        await event_reader.handle(InputEvent.abs(ABS_Y, MAX_ABS * 0.05))

        await asyncio.sleep(0.2)  # wait a bit more for nothing to sum up
        if mouse_history[0].type == EV_ABS:
            raise AssertionError(
                "The injector probably just forwarded them unchanged"
                # possibly in addition to writing mouse events
            )

        self.assertAlmostEqual(len(mouse_history), rel_rate * sleep, delta=3)

        # does not contain anything else
        expected_rel_event = (EV_REL, REL_X, int(gain * REL_XY_SCALING))
        count_x = convert_to_internal_events(mouse_history).count(expected_rel_event)
        self.assertEqual(len(mouse_history), count_x)


class TestAbsToAbs(EventPipelineTestBase):
    async def test_abs_to_abs(self):
        gain = 0.5
        # left x to mouse x
        input_config = InputConfig(type=EV_ABS, code=ABS_X)
        mapping_config = {
            "input_combination": InputCombination(input_config).to_config(),
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
        mapping_config["input_combination"] = InputCombination(input_config).to_config()
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
        # convert the write-history to some easier to manage list
        history = convert_to_internal_events(
            global_uinputs.get_uinput("gamepad").write_history
        )
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
        # convert the write-history to some easier to manage list
        history = convert_to_internal_events(
            global_uinputs.get_uinput("gamepad").write_history
        )
        self.assertEqual(
            history,
            [
                InputEvent.from_tuple((3, 0, MIN_ABS / 2)),
                InputEvent.from_tuple((3, 0, MAX_ABS / 2)),
                InputEvent.from_tuple((3, 0, 0)),
            ],
        )


class TestRelToAbs(EventPipelineTestBase):
    async def test_rel_to_abs(self):
        timestamp = 0

        def next_usec_time():
            nonlocal timestamp
            timestamp += 1000000 / DEFAULT_REL_RATE
            return timestamp

        gain = 0.5
        # left mouse x to abs x
        cutoff = 2
        input_combination = InputCombination(InputConfig(type=EV_REL, code=REL_X))
        mapping_config = {
            "input_combination": input_combination.to_config(),
            "target_uinput": "gamepad",
            "output_type": EV_ABS,
            "output_code": ABS_X,
            "gain": gain,
            "rel_to_abs_input_cutoff": cutoff,
            "release_timeout": 0.5,
            "deadzone": 0,
        }
        mapping_1 = Mapping(**mapping_config)
        preset = Preset()
        preset.add(mapping_1)
        input_combination = InputCombination(InputConfig(type=EV_REL, code=REL_Y))
        mapping_config["input_combination"] = input_combination.to_config()
        mapping_config["output_code"] = ABS_Y
        mapping_2 = Mapping(**mapping_config)
        preset.add(mapping_2)

        event_reader = self.create_event_reader(preset, fixtures.gamepad)

        next_time = next_usec_time()
        await self.send_events(
            [
                InputEvent(0, next_time, EV_REL, REL_X, -int(REL_XY_SCALING * cutoff)),
                InputEvent(0, next_time, EV_REL, REL_Y, int(REL_XY_SCALING * cutoff)),
            ],
            event_reader,
        )

        await asyncio.sleep(0.1)
        # convert the write-history to some easier to manage list
        history = convert_to_internal_events(
            global_uinputs.get_uinput("gamepad").write_history
        )
        self.assertEqual(
            history,
            [
                InputEvent.from_tuple((3, 0, MIN_ABS / 2)),
                InputEvent.from_tuple((3, 1, MAX_ABS / 2)),
            ],
        )

        # send more events, then wait until the release timeout
        next_time = next_usec_time()
        await self.send_events(
            [
                InputEvent(0, next_time, EV_REL, REL_X, -int(REL_XY_SCALING)),
                InputEvent(0, next_time, EV_REL, REL_Y, int(REL_XY_SCALING)),
            ],
            event_reader,
        )
        await asyncio.sleep(0.7)
        history = convert_to_internal_events(
            global_uinputs.get_uinput("gamepad").write_history
        )
        self.assertEqual(
            history,
            [
                InputEvent.from_tuple((3, 0, MIN_ABS / 2)),
                InputEvent.from_tuple((3, 1, MAX_ABS / 2)),
                InputEvent.from_tuple((3, 0, MIN_ABS / 4)),
                InputEvent.from_tuple((3, 1, MAX_ABS / 4)),
                InputEvent.from_tuple((3, 0, 0)),
                InputEvent.from_tuple((3, 1, 0)),
            ],
        )

    async def test_rel_to_abs_with_input_switch(self):
        # use 0 everywhere, because that will cause the handler to not update the rate,
        # and we are able to test things without worrying about that at all
        timestamp = 0

        gain = 0.5
        cutoff = 1
        input_combination = InputCombination(
            (
                InputConfig(type=EV_REL, code=REL_X),
                InputConfig(type=EV_REL, code=REL_Y, analog_threshold=10),
            )
        )
        # left mouse x to x
        mapping_config = {
            "input_combination": input_combination.to_config(),
            "target_uinput": "gamepad",
            "output_type": EV_ABS,
            "output_code": ABS_X,
            "gain": gain,
            "rel_to_abs_input_cutoff": cutoff,
            "deadzone": 0,
        }
        mapping_1 = Mapping(**mapping_config)
        preset = Preset()
        preset.add(mapping_1)

        event_reader = self.create_event_reader(preset, fixtures.gamepad)

        # if the cutoff is higher, the test sends higher values to overcome the cutoff
        await self.send_events(
            [
                # will not map
                InputEvent(0, timestamp, EV_REL, REL_X, -REL_XY_SCALING / 4 * cutoff),
                # switch axis on
                InputEvent(0, timestamp, EV_REL, REL_Y, REL_XY_SCALING / 5 * cutoff),
                # normally mapped
                InputEvent(0, timestamp, EV_REL, REL_X, REL_XY_SCALING * cutoff),
                # off, re-centers axis
                InputEvent(0, timestamp, EV_REL, REL_Y, REL_XY_SCALING / 20 * cutoff),
                # will not map
                InputEvent(0, timestamp, EV_REL, REL_X, REL_XY_SCALING / 2 * cutoff),
            ],
            event_reader,
        )

        await asyncio.sleep(0.2)
        # convert the write-history to some easier to manage list
        history = convert_to_internal_events(
            global_uinputs.get_uinput("gamepad").write_history
        )
        self.assertEqual(
            history,
            [
                InputEvent.from_tuple((3, 0, MAX_ABS / 2)),
                InputEvent.from_tuple((3, 0, 0)),
            ],
        )


class TestAbsToRel(EventPipelineTestBase):
    async def test_abs_to_rel(self):
        """Map gamepad EV_ABS events to EV_REL events."""

        rel_rate = 60  # rate [Hz] at which events are produced
        gain = 0.5  # halve the speed of the rel axis
        # left x to mouse x
        input_config = InputConfig(type=EV_ABS, code=ABS_X)
        mapping_config = {
            "input_combination": InputCombination(input_config).to_config(),
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
        mapping_config["input_combination"] = InputCombination(input_config).to_config()
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

        # convert the write-history to some easier to manage list
        mouse_history = convert_to_internal_events(
            global_uinputs.get_uinput("mouse").write_history
        )

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
            "input_combination": InputCombination(input_config).to_config(),
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
        mapping_config["input_combination"] = InputCombination(input_config).to_config()
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
        m_history = convert_to_internal_events(
            global_uinputs.get_uinput("mouse").write_history
        )

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


class TestRelToBtn(EventPipelineTestBase):
    async def test_rel_to_btn(self):
        """Rel axis mapped to buttons are automatically released if no new rel event arrives."""

        # map those two to stuff
        w_up = (EV_REL, REL_WHEEL, -1)
        hw_right = (EV_REL, REL_HWHEEL, 1)

        # should be forwarded and present in the capabilities
        hw_left = (EV_REL, REL_HWHEEL, -1)

        system_mapping.clear()
        code_b = 91
        code_c = 92
        system_mapping._set("b", code_b)
        system_mapping._set("c", code_c)

        # set a high release timeout to make sure the tests pass
        release_timeout = 0.2
        mapping_1 = get_key_mapping(
            InputCombination(get_combination_config(hw_right)), "keyboard", "k(b)"
        )
        mapping_2 = get_key_mapping(
            InputCombination(get_combination_config(w_up)), "keyboard", "c"
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

        keyboard_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        forwarded_history = convert_to_internal_events(
            self.forward_uinput.write_history
        )
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
        mapping_1 = get_key_mapping(
            InputCombination(InputConfig(type=EV_REL, code=REL_X, analog_threshold=5)),
            output_symbol="a",
        )
        # at 15 map to b
        mapping_2 = get_key_mapping(
            InputCombination(InputConfig(type=EV_REL, code=REL_X, analog_threshold=15)),
            output_symbol="b",
        )
        release_timeout = 0.2  # give some time to do assertions before the release
        mapping_1.release_timeout = release_timeout
        mapping_2.release_timeout = release_timeout
        preset = Preset()
        preset.add(mapping_1)
        preset.add(mapping_2)

        a = system_mapping.get("a")
        b = system_mapping.get("b")

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
        keyboard_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )

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
        keyboard_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        self.assertEqual(keyboard_history.count((EV_KEY, a, 1)), 2)
        self.assertEqual(keyboard_history.count((EV_KEY, b, 1)), 1)
        self.assertEqual(keyboard_history.count((EV_KEY, b, 0)), 1)
        self.assertEqual(keyboard_history.count((EV_KEY, a, 0)), 1)

        await asyncio.sleep(release_timeout * 1.5)  # release a
        keyboard_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        forwarded_history = convert_to_internal_events(
            self.forward_uinput.write_history
        )
        self.assertEqual(keyboard_history.count((EV_KEY, a, 0)), 2)
        self.assertEqual(
            forwarded_history,
            [(EV_REL, REL_X, -5), (EV_REL, REL_X, 0), (EV_REL, REL_X, 3)],
        )


class TestAbsToBtn(EventPipelineTestBase):
    async def test_abs_trigger_threshold(self):
        """Test that different activation points for abs_to_btn work correctly."""

        # at 30% map to a
        mapping_1 = get_key_mapping(
            InputCombination(InputConfig(type=EV_ABS, code=ABS_X, analog_threshold=30)),
            output_symbol="a",
        )
        # at 70% map to b
        mapping_2 = get_key_mapping(
            InputCombination(InputConfig(type=EV_ABS, code=ABS_X, analog_threshold=70)),
            output_symbol="b",
        )
        preset = Preset()
        preset.add(mapping_1)
        preset.add(mapping_2)

        a = system_mapping.get("a")
        b = system_mapping.get("b")

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
        keyboard_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )

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
        keyboard_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        self.assertEqual(keyboard_history.count((EV_KEY, a, 1)), 1)
        self.assertEqual(keyboard_history.count((EV_KEY, b, 1)), 1)
        self.assertEqual(keyboard_history.count((EV_KEY, b, 0)), 1)
        self.assertNotIn((EV_KEY, a, 0), keyboard_history)

        # 0% release a
        await event_reader.handle(InputEvent.abs(ABS_X, 0))
        keyboard_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        forwarded_history = convert_to_internal_events(
            self.forward_uinput.write_history
        )
        self.assertEqual(keyboard_history.count((EV_KEY, a, 0)), 1)
        self.assertEqual(len(forwarded_history), 0)


class TestRelToRel(EventPipelineTestBase):
    async def _test(self, input_code, input_value, output_code, output_value, gain=1):
        preset = Preset()

        input_config = InputConfig(type=EV_REL, code=input_code)
        mapping = Mapping(
            input_combination=InputCombination(input_config).to_config(),
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

        # convert the write-history to some easier to manage list
        history = convert_to_internal_events(
            global_uinputs.get_uinput("mouse").write_history
        )

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
            input_combination=InputCombination(input_config).to_config(),
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

        history = global_uinputs.get_uinput("mouse").write_history
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
        history = global_uinputs.get_uinput("mouse").write_history

        # REL_WHEEL_HI_RES to REL_Y
        input_config = InputConfig(type=EV_REL, code=REL_WHEEL_HI_RES)
        gain = 0.01
        mapping = Mapping(
            input_combination=InputCombination(input_config).to_config(),
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
