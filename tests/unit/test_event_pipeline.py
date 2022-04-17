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

from inputremapper.logger import logger
from inputremapper.configs.mapping import Mapping
from inputremapper.injection.context import Context
from inputremapper.injection.event_reader import EventReader
from tests.test import (
    get_key_mapping,
    InputDevice,
    cleanup,
    convert_to_internal_events,
    MAX_ABS,
    MIN_ABS,
)

from inputremapper.input_event import InputEvent
from inputremapper.event_combination import EventCombination
from inputremapper.configs.system_mapping import system_mapping
from inputremapper.configs.preset import Preset
from inputremapper.injection.global_uinputs import global_uinputs


class TestEventPipeline(unittest.IsolatedAsyncioTestCase):
    """Test the event pipeline form event_reader to UInput."""

    def setUp(self):
        # print("in setup")
        # global_uinputs.prepare_all()
        self.forward_uinput = evdev.UInput()
        self.stop_event = asyncio.Event()

    def tearDown(self) -> None:
        cleanup()

    @staticmethod
    async def send_events(events: Iterable[InputEvent], event_reader: EventReader):
        for event in events:
            logger.info("sending into event_pipeline:  %s", event.event_tuple)
            await event_reader.handle(event)

    def get_event_reader(
        self,
        preset: Preset,
        source: evdev.InputDevice,
    ) -> EventReader:
        context = Context(preset)
        return EventReader(context, source, self.forward_uinput, self.stop_event)

    async def test_any_event_as_button(self):
        """As long as there is an event handler and a mapping we should be able
        to map anything to a button"""

        w_down = (
            EV_ABS,
            ABS_Y,
            -12345,
        )  # value needs to be higher than 10% below center of axis (absinfo)
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
        preset.add(get_key_mapping(EventCombination(b_down), "keyboard", "b"))
        preset.add(get_key_mapping(EventCombination(c_down), "keyboard", "c"))
        preset.add(
            get_key_mapping(EventCombination([*w_down[:2], -10]), "keyboard", "w"),
        )
        preset.add(
            get_key_mapping(EventCombination([*d_down[:2], 10]), "keyboard", "k(d)"),
        )
        preset.add(
            get_key_mapping(EventCombination([*s_down[:2], 10]), "keyboard", "s"),
        )
        preset.add(
            get_key_mapping(EventCombination([*a_down[:2], -10]), "keyboard", "a"),
        )

        event_reader = self.get_event_reader(
            preset, InputDevice("/dev/input/event30")
        )  # gamepad fixture

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
        await asyncio.sleep(
            0.1
        )  # wait a bit for the rel_to_btn handler to send the key up

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
        preset.add(get_key_mapping(combination="1,1,1", output_symbol="hold(a)"))
        preset.add(get_key_mapping(combination="1,2,1", output_symbol="b"))
        preset.add(
            get_key_mapping(combination="1,3,1", output_symbol="modify(c,hold(d))"),
        )
        event_reader = self.get_event_reader(preset, InputDevice("/dev/input/event10"))

        a = system_mapping.get("a")
        b = system_mapping.get("b")
        c = system_mapping.get("c")
        d = system_mapping.get("d")

        await self.send_events(
            [
                InputEvent.from_tuple((1, 1, 1)),
                InputEvent.from_tuple((1, 2, 1)),
                InputEvent.from_tuple((1, 3, 1)),
            ],
            event_reader,
        )
        await asyncio.sleep(0.1)

        fw_history = convert_to_internal_events(self.forward_uinput.write_history)
        kb_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )

        self.assertEqual(len(fw_history), 0)
        # a down, b down, c down, d down
        self.assertEqual(len(kb_history), 4)

        event_reader.context.reset()
        await asyncio.sleep(0.1)

        fw_history = convert_to_internal_events(self.forward_uinput.write_history)
        kb_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )

        self.assertEqual(len(fw_history), 0)
        # all a, b, c, d down+up
        self.assertEqual(len(kb_history), 8)
        kb_history = kb_history[-4:]
        self.assertIn((1, a, 0), kb_history)
        self.assertIn((1, b, 0), kb_history)
        self.assertIn((1, c, 0), kb_history)
        self.assertIn((1, d, 0), kb_history)

    async def test_abs_to_rel(self):
        """Map gamepad EV_ABS events to EV_REL events."""

        rate = 60  # rate [Hz] at which events are produced
        gain = 0.5  # halve the speed of the rel axis
        speed = 1
        preset = Preset()
        # left x to mouse x
        cfg = {
            "event_combination": ",".join((str(EV_ABS), str(ABS_X), "0")),
            "target_uinput": "mouse",
            "output_type": EV_REL,
            "output_code": REL_X,
            "rate": rate,
            "gain": gain,
            "deadzone": 0,
            "rel_speed": speed,
        }
        m1 = Mapping(**cfg)
        preset.add(m1)
        # left y to mouse y
        cfg["event_combination"] = ",".join((str(EV_ABS), str(ABS_Y), "0"))
        cfg["output_code"] = REL_Y
        m2 = Mapping(**cfg)
        preset.add(m2)

        # set input axis to 100% in order to move
        # speed*gain*rate=1*0.5*60 pixel per second
        x = MAX_ABS
        y = MAX_ABS

        event_reader = self.get_event_reader(
            preset, InputDevice("/dev/input/event30")
        )  # gamepad Fixture

        await self.send_events(
            [
                InputEvent.from_tuple((EV_ABS, ABS_X, -x)),
                InputEvent.from_tuple((EV_ABS, ABS_Y, -y)),
            ],
            event_reader,
        )
        # wait a bit more for it to sum up
        sleep = 0.5
        await asyncio.sleep(sleep)
        # stop it
        await self.send_events(
            [
                InputEvent.from_tuple((EV_ABS, ABS_X, 0)),
                InputEvent.from_tuple((EV_ABS, ABS_Y, 0)),
            ],
            event_reader,
        )

        # convert the write history to some easier to manage list
        history = convert_to_internal_events(
            global_uinputs.get_uinput("mouse").write_history
        )

        if history[0].type == EV_ABS:
            raise AssertionError(
                "The injector probably just forwarded them unchanged"
                # possibly in addition to writing mouse events
            )

        # each axis writes speed*gain*rate*sleep=1*0.5*60 events
        self.assertGreater(len(history), speed * gain * rate * sleep * 0.9 * 2)
        self.assertLess(len(history), speed * gain * rate * sleep * 1.1 * 2)

        # those may be in arbitrary order
        count_x = history.count((EV_REL, REL_X, -1))
        count_y = history.count((EV_REL, REL_Y, -1))
        self.assertGreater(count_x, 1)
        self.assertGreater(count_y, 1)
        # only those two types of events were written
        self.assertEqual(len(history), count_x + count_y)

    async def test_abs_to_wheel_hi_res_quirk(self):
        """When mapping to wheel events we always expect to see both,
        REL_WHEEL and REL_WHEEL_HI_RES events with a accumulative value ratio of 1/120
        """
        rate = 60  # rate [Hz] at which events are produced
        gain = 1
        speed = 30
        preset = Preset()
        # left x to mouse x
        cfg = {
            "event_combination": ",".join((str(EV_ABS), str(ABS_X), "0")),
            "target_uinput": "mouse",
            "output_type": EV_REL,
            "output_code": REL_WHEEL,
            "rate": rate,
            "gain": gain,
            "deadzone": 0,
            "rel_speed": speed,
        }
        m1 = Mapping(**cfg)
        preset.add(m1)
        # left y to mouse y
        cfg["event_combination"] = ",".join((str(EV_ABS), str(ABS_Y), "0"))
        cfg["output_code"] = REL_HWHEEL_HI_RES
        m2 = Mapping(**cfg)
        preset.add(m2)

        # set input axis to 100% in order to move
        # speed*gain*rate=1*0.5*60 pixel per second
        x = MAX_ABS
        y = MAX_ABS

        event_reader = self.get_event_reader(
            preset, InputDevice("/dev/input/event30")
        )  # gamepad Fixture

        await self.send_events(
            [
                InputEvent.from_tuple((EV_ABS, ABS_X, x)),
                InputEvent.from_tuple((EV_ABS, ABS_Y, -y)),
            ],
            event_reader,
        )
        # wait a bit more for it to sum up
        sleep = 0.5
        await asyncio.sleep(sleep)
        # stop it
        await self.send_events(
            [
                InputEvent.from_tuple((EV_ABS, ABS_X, 0)),
                InputEvent.from_tuple((EV_ABS, ABS_Y, 0)),
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

    async def test_forward_abs(self):
        """Test if EV_ABS events are forwarded when other events of the same input are not."""
        preset = Preset()
        # BTN_A -> 77
        system_mapping._set("b", 77)
        preset.add(get_key_mapping(EventCombination([1, BTN_A, 1]), "keyboard", "b"))
        event_reader = self.get_event_reader(
            preset, InputDevice("/dev/input/event30")
        )  # gamepad Fixture

        # should forward them unmodified
        await self.send_events(
            [
                InputEvent.from_tuple((EV_ABS, ABS_X, 10)),
                InputEvent.from_tuple((EV_ABS, ABS_Y, 20)),
                InputEvent.from_tuple((EV_ABS, ABS_X, -30)),
                InputEvent.from_tuple((EV_ABS, ABS_Y, -40)),
                # send them to keyboard 77
                InputEvent.from_tuple((EV_KEY, BTN_A, 1)),
                InputEvent.from_tuple((EV_KEY, BTN_A, 0)),
            ],
            event_reader,
        )

        # convert the write history to some easier to manage list
        history = convert_to_internal_events(self.forward_uinput.write_history)
        kb_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )

        self.assertEqual(history.count((EV_ABS, ABS_X, 10)), 1)
        self.assertEqual(history.count((EV_ABS, ABS_Y, 20)), 1)
        self.assertEqual(history.count((EV_ABS, ABS_X, -30)), 1)
        self.assertEqual(history.count((EV_ABS, ABS_Y, -40)), 1)
        self.assertEqual(kb_history.count((EV_KEY, 77, 1)), 1)
        self.assertEqual(kb_history.count((EV_KEY, 77, 0)), 1)

    async def test_forward_rel(self):
        """Test if EV_REL events are forwarded when other events of the same input are not."""
        preset = Preset()
        # BTN_A -> 77
        system_mapping._set("b", 77)
        preset.add(get_key_mapping(EventCombination([1, BTN_LEFT, 1]), "keyboard", "b"))
        event_reader = self.get_event_reader(
            preset, InputDevice("/dev/input/event11")
        )  # gamepad Fixture

        # should forward them unmodified
        await self.send_events(
            [
                InputEvent.from_tuple((EV_REL, REL_X, 10)),
                InputEvent.from_tuple((EV_REL, REL_Y, 20)),
                InputEvent.from_tuple((EV_REL, REL_X, -30)),
                InputEvent.from_tuple((EV_REL, REL_Y, -40)),
                # send them to keyboard 77
                InputEvent.from_tuple((EV_KEY, BTN_LEFT, 1)),
                InputEvent.from_tuple((EV_KEY, BTN_LEFT, 0)),
            ],
            event_reader,
        )
        await asyncio.sleep(0.1)

        # convert the write history to some easier to manage list
        history = convert_to_internal_events(self.forward_uinput.write_history)
        kb_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )

        self.assertEqual(history.count((EV_REL, REL_X, 10)), 1)
        self.assertEqual(history.count((EV_REL, REL_Y, 20)), 1)
        self.assertEqual(history.count((EV_REL, REL_X, -30)), 1)
        self.assertEqual(history.count((EV_REL, REL_Y, -40)), 1)
        self.assertEqual(kb_history.count((EV_KEY, 77, 1)), 1)
        self.assertEqual(kb_history.count((EV_KEY, 77, 0)), 1)

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
        preset = Preset()
        m1 = get_key_mapping(EventCombination(hw_right), "keyboard", "k(b)")
        m2 = get_key_mapping(EventCombination(w_up), "keyboard", "c")
        m1.release_timeout = release_timeout
        m2.release_timeout = release_timeout
        preset.add(m1)
        preset.add(m2)

        device = InputDevice("/dev/input/event11")
        event_reader = self.get_event_reader(preset, device)

        # make sure this test uses a device that has the needed capabilities
        # for the injector to grab it
        self.assertIn(EV_REL, device.capabilities())
        self.assertIn(REL_WHEEL, device.capabilities()[EV_REL])
        self.assertIn(REL_HWHEEL, device.capabilities()[EV_REL])

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

        kb_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        fw_history = convert_to_internal_events(self.forward_uinput.write_history)
        self.assertEqual(kb_history.count((EV_KEY, code_b, 1)), 1)
        self.assertEqual(kb_history.count((EV_KEY, code_c, 1)), 1)
        self.assertEqual(kb_history.count((EV_KEY, code_b, 0)), 1)
        self.assertEqual(kb_history.count((EV_KEY, code_c, 0)), 1)
        self.assertEqual(fw_history.count(hw_left), 2)  # the unmapped wheel direction

        # the unmapped wheel won't get a debounced release command, it's
        # forwarded as is
        self.assertNotIn((EV_REL, REL_HWHEEL, 0), fw_history)

    async def test_abs_trigger_threshold(self):
        """Test that different activation points for abs_to_btn work correctly."""

        m1 = get_key_mapping(
            EventCombination((EV_ABS, ABS_X, 30)),
            output_symbol="a",
        )  # at 30% map to a
        m2 = get_key_mapping(
            EventCombination((EV_ABS, ABS_X, 70)),
            output_symbol="b",
        )  # at 70% map to b
        preset = Preset()
        preset.add(m1)
        preset.add(m2)

        a = system_mapping.get("a")
        b = system_mapping.get("b")

        event_reader = self.get_event_reader(preset, InputDevice("/dev/input/event30"))

        await self.send_events(
            [
                # -10%, do nothing
                InputEvent.from_tuple((EV_ABS, ABS_X, MIN_ABS // 10)),
                # 0%, do noting
                InputEvent.from_tuple((EV_ABS, ABS_X, 0)),
                # 10%, do nothing
                InputEvent.from_tuple((EV_ABS, ABS_X, MAX_ABS // 10)),
                # 50%, trigger a
                InputEvent.from_tuple((EV_ABS, ABS_X, MAX_ABS // 2)),
            ],
            event_reader,
        )
        kb_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )

        self.assertEqual(kb_history.count((EV_KEY, a, 1)), 1)
        self.assertNotIn((EV_KEY, a, 0), kb_history)
        self.assertNotIn((EV_KEY, b, 1), kb_history)

        await self.send_events(
            [
                # 80%, trigger b
                InputEvent.from_tuple((EV_ABS, ABS_X, int(MAX_ABS * 0.8))),
                InputEvent.from_tuple((EV_ABS, ABS_X, MAX_ABS // 2)),  # 50%, release b
            ],
            event_reader,
        )
        kb_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        self.assertEqual(kb_history.count((EV_KEY, a, 1)), 1)
        self.assertEqual(kb_history.count((EV_KEY, b, 1)), 1)
        self.assertEqual(kb_history.count((EV_KEY, b, 0)), 1)
        self.assertNotIn((EV_KEY, a, 0), kb_history)

        # 0% release a
        await event_reader.handle(InputEvent.from_tuple((EV_ABS, ABS_X, 0)))
        kb_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        fw_history = convert_to_internal_events(self.forward_uinput.write_history)
        self.assertEqual(kb_history.count((EV_KEY, a, 0)), 1)
        self.assertEqual(len(fw_history), 0)

    async def test_rel_trigger_threshold(self):
        """Test that different activation points for rel_to_btn work correctly."""

        m1 = get_key_mapping(
            EventCombination((EV_REL, REL_X, 5)),
            output_symbol="a",
        )  # at 30% map to a
        m2 = get_key_mapping(
            EventCombination((EV_REL, REL_X, 15)),
            output_symbol="b",
        )  # at 70% map to b
        release_timeout = 0.2  # give some time to do assertions before the release
        m1.release_timeout = release_timeout
        m2.release_timeout = release_timeout
        preset = Preset()
        preset.add(m1)
        preset.add(m2)

        a = system_mapping.get("a")
        b = system_mapping.get("b")

        event_reader = self.get_event_reader(preset, InputDevice("/dev/input/event11"))

        await self.send_events(
            [
                InputEvent.from_tuple((EV_REL, REL_X, -5)),  # forward
                InputEvent.from_tuple((EV_REL, REL_X, 0)),  # forward
                InputEvent.from_tuple((EV_REL, REL_X, 3)),  # forward
                InputEvent.from_tuple((EV_REL, REL_X, 10)),  # trigger a
            ],
            event_reader,
        )
        await asyncio.sleep(release_timeout * 1.5)  # release a
        kb_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )

        self.assertEqual(kb_history.count((EV_KEY, a, 1)), 1)
        self.assertEqual(kb_history.count((EV_KEY, a, 0)), 1)
        self.assertNotIn((EV_KEY, b, 1), kb_history)

        await self.send_events(
            [
                InputEvent.from_tuple((EV_REL, REL_X, 10)),  # trigger a
                InputEvent.from_tuple((EV_REL, REL_X, 20)),  # trigger b
                InputEvent.from_tuple((EV_REL, REL_X, 10)),  # release b
            ],
            event_reader,
        )
        kb_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        self.assertEqual(kb_history.count((EV_KEY, a, 1)), 2)
        self.assertEqual(kb_history.count((EV_KEY, b, 1)), 1)
        self.assertEqual(kb_history.count((EV_KEY, b, 0)), 1)
        self.assertEqual(kb_history.count((EV_KEY, a, 0)), 1)

        await asyncio.sleep(release_timeout * 1.5)  # release a
        kb_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        fw_history = convert_to_internal_events(self.forward_uinput.write_history)
        self.assertEqual(kb_history.count((EV_KEY, a, 0)), 2)
        self.assertEqual(
            fw_history,
            [(EV_REL, REL_X, -5), (EV_REL, REL_X, 0), (EV_REL, REL_X, 3)],
        )

    async def test_combination(self):
        """Test if combinations map to keys properly."""

        a = system_mapping.get("a")
        b = system_mapping.get("b")
        c = system_mapping.get("c")

        preset = Preset()
        m1 = get_key_mapping(EventCombination((EV_ABS, ABS_X, 1)), output_symbol="a")
        m2 = get_key_mapping(
            EventCombination(((EV_ABS, ABS_X, 1), (EV_KEY, BTN_A, 1))),
            output_symbol="b",
        )
        m3 = get_key_mapping(
            EventCombination(
                ((EV_ABS, ABS_X, 1), (EV_KEY, BTN_A, 1), (EV_KEY, BTN_B, 1)),
            ),
            output_symbol="c",
        )

        preset.add(m1)
        preset.add(m2)
        preset.add(m3)
        event_reader = self.get_event_reader(preset, InputDevice("/dev/input/event30"))

        await self.send_events(
            [
                # forwarded
                InputEvent.from_tuple((EV_KEY, BTN_A, 1)),
                # triggers b, releases BTN_A, ABS_X
                InputEvent.from_tuple((EV_ABS, ABS_X, 1234)),
                # triggers c, releases BTN_A, ABS_X, BTN_B
                InputEvent.from_tuple((EV_KEY, BTN_B, 1)),
            ],
            event_reader,
        )
        kb_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        fw_history = convert_to_internal_events(self.forward_uinput.write_history)

        self.assertNotIn((1, a, 1), kb_history)
        self.assertEqual(kb_history.count((1, c, 1)), 1)
        self.assertEqual(kb_history.count((1, b, 1)), 1)

        self.assertEqual(fw_history.count((EV_KEY, BTN_A, 1)), 1)
        self.assertIn((EV_KEY, BTN_A, 0), fw_history)
        self.assertNotIn((EV_ABS, ABS_X, 1234), fw_history)
        self.assertNotIn((EV_KEY, BTN_B, 1), fw_history)

        await self.send_events(
            [InputEvent.from_tuple((EV_ABS, ABS_X, 0))],
            event_reader,
        )  # release b and c)
        kb_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        self.assertNotIn((1, a, 1), kb_history)
        self.assertNotIn((1, a, 0), kb_history)
        self.assertEqual(kb_history.count((1, c, 0)), 1)
        self.assertEqual(kb_history.count((1, b, 0)), 1)

    async def test_ignore_hold(self):
        # hold as in event-value 2, not in macro-hold.
        # linux will generate events with value 2 after input-remapper injected
        # the key-press, so input-remapper doesn't need to forward them. That
        # would cause duplicate events of those values otherwise.
        key = (EV_KEY, KEY_A)
        ev_1 = (*key, 1)
        ev_2 = (*key, 2)
        ev_3 = (*key, 0)

        preset = Preset()
        preset.add(get_key_mapping(EventCombination(ev_1), output_symbol="a"))
        a = system_mapping.get("a")

        event_reader = self.get_event_reader(preset, InputDevice("/dev/input/event30"))
        await self.send_events(
            [
                InputEvent.from_tuple(ev_1),
                InputEvent.from_tuple(ev_2),
                InputEvent.from_tuple(ev_3),
            ],
            event_reader,
        )

        kb_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        fw_history = convert_to_internal_events(self.forward_uinput.write_history)
        self.assertEqual(len(kb_history), 2)
        self.assertEqual(len(fw_history), 0)
        self.assertNotIn((1, a, 2), kb_history)

    async def test_ignore_disabled(self):
        ev_1 = (EV_ABS, ABS_HAT0Y, 1)
        ev_2 = (EV_ABS, ABS_HAT0Y, 0)

        ev_3 = (EV_ABS, ABS_HAT0X, 1)  # disabled
        ev_4 = (EV_ABS, ABS_HAT0X, 0)

        ev_5 = (EV_KEY, KEY_A, 1)
        ev_6 = (EV_KEY, KEY_A, 0)

        combi_1 = EventCombination((ev_5, ev_3))
        combi_2 = EventCombination((ev_3, ev_5))

        preset = Preset()
        preset.add(get_key_mapping(EventCombination(ev_1), output_symbol="a"))
        preset.add(get_key_mapping(EventCombination(ev_3), output_symbol="disable"))
        preset.add(get_key_mapping(combi_1, output_symbol="b"))
        preset.add(get_key_mapping(combi_2, output_symbol="c"))

        a = system_mapping.get("a")
        b = system_mapping.get("b")
        c = system_mapping.get("c")

        event_reader = self.get_event_reader(preset, InputDevice("/dev/input/event30"))

        """Single keys"""
        await self.send_events(
            [
                InputEvent.from_tuple(ev_1),  # press a
                InputEvent.from_tuple(ev_3),  # disabled
                InputEvent.from_tuple(ev_2),  # release a
                InputEvent.from_tuple(ev_4),  # disabled
            ],
            event_reader,
        )
        kb_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        fw_history = convert_to_internal_events(self.forward_uinput.write_history)
        self.assertIn((1, a, 1), kb_history)
        self.assertIn((1, a, 0), kb_history)
        self.assertEqual(len(kb_history), 2)
        self.assertEqual(len(fw_history), 0)

        """A combination that ends in a disabled key"""
        # ev_5 should be forwarded and the combination triggered
        await self.send_events(combi_1, event_reader)
        kb_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        fw_history = convert_to_internal_events(self.forward_uinput.write_history)
        self.assertIn((1, b, 1), kb_history)
        self.assertEqual(len(kb_history), 3)
        self.assertEqual(fw_history.count(ev_3), 0)
        self.assertEqual(fw_history.count(ev_5), 1)
        self.assertTrue(fw_history.count((*ev_5[0:2], 0)) >= 1)

        # release what the combination maps to
        await self.send_events(
            [
                InputEvent.from_tuple((*ev_3[0:2], 0)),
                InputEvent.from_tuple((*ev_5[0:2], 0)),
            ],
            event_reader,
        )
        kb_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        fw_history = convert_to_internal_events(self.forward_uinput.write_history)
        self.assertIn((1, b, 0), kb_history)
        self.assertEqual(len(kb_history), 4)
        self.assertEqual(fw_history.count(ev_3), 0)
        self.assertTrue(fw_history.count((*ev_5[0:2], 0)) >= 1)

        """A combination that starts with a disabled key"""
        # only the combination should get triggered
        await self.send_events(combi_2, event_reader)
        kb_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        fw_history = convert_to_internal_events(self.forward_uinput.write_history)
        self.assertIn((1, c, 1), kb_history)
        self.assertEqual(len(kb_history), 5)
        self.assertEqual(fw_history.count(ev_3), 0)
        self.assertEqual(fw_history.count(ev_5), 1)
        self.assertTrue(fw_history.count((*ev_5[0:2], 0)) >= 1)

        # release what the combination maps to
        await self.send_events(
            [
                InputEvent.from_tuple((*ev_3[0:2], 0)),
                InputEvent.from_tuple((*ev_5[0:2], 0)),
            ],
            event_reader,
        )
        kb_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        fw_history = convert_to_internal_events(self.forward_uinput.write_history)
        for event in kb_history:
            print(event.event_tuple)
        self.assertIn((1, c, 0), kb_history)
        self.assertEqual(len(kb_history), 6)
        self.assertEqual(fw_history.count(ev_3), 0)
        self.assertTrue(fw_history.count((*ev_5[0:2], 0)) >= 1)

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
        preset.add(get_key_mapping(EventCombination(down_1), output_symbol="h(k(a))"))
        preset.add(
            get_key_mapping(EventCombination((down_1, down_2)), output_symbol="b")
        )

        event_reader = self.get_event_reader(preset, InputDevice("/dev/input/event30"))
        # macro starts
        await self.send_events([InputEvent.from_tuple(down_1)], event_reader)
        await asyncio.sleep(0.05)
        kb_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        fw_history = convert_to_internal_events(self.forward_uinput.write_history)
        self.assertEqual(len(fw_history), 0)
        self.assertGreater(len(kb_history), 1)
        self.assertNotIn((1, b, 1), kb_history)
        self.assertIn((1, a, 1), kb_history)
        self.assertIn((1, a, 0), kb_history)

        # combination triggered
        await self.send_events([InputEvent.from_tuple(down_2)], event_reader)
        await asyncio.sleep(0)
        kb_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        self.assertEqual(kb_history[-1], (EV_KEY, b, 1))

        len_a = len(global_uinputs.get_uinput("keyboard").write_history)
        await asyncio.sleep(0.05)
        len_b = len(global_uinputs.get_uinput("keyboard").write_history)
        # still running
        self.assertGreater(len_b, len_a)

        # release
        await self.send_events([InputEvent.from_tuple(up_1)], event_reader)
        kb_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        self.assertEqual(kb_history[-1], (EV_KEY, b, 0))
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
        btn_down = InputEvent.from_tuple((1, 276, 1))
        btn_up = InputEvent.from_tuple((1, 276, 0))
        combination = EventCombination(((1, 276, 1), (2, 8, -1)))

        system_mapping.clear()
        system_mapping._set("a", 30)
        a = 30

        preset = Preset()
        m = get_key_mapping(combination, output_symbol="a")
        m.release_timeout = 0.1  # a higher release timeout to give time for assertions
        preset.add(m)

        event_reader = self.get_event_reader(preset, InputDevice("/dev/input/event11"))

        await self.send_events([btn_down], event_reader)
        fw_history = convert_to_internal_events(self.forward_uinput.write_history)
        self.assertEqual(fw_history[0], btn_down)

        await self.send_events([scroll], event_reader)
        # "maps to 30"
        kb_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        self.assertEqual(kb_history[0], (1, a, 1))

        await self.send_events([scroll] * 5, event_reader)

        # nothing new since all of them were duplicate key downs
        kb_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        self.assertEqual(len(kb_history), 1)

        await self.send_events([btn_up], event_reader)
        # releasing the combination
        kb_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        self.assertEqual(kb_history[1], (1, a, 0))

        # more scroll events
        # it should be ignored as duplicate key-down
        await self.send_events([scroll] * 5, event_reader)
        fw_history = convert_to_internal_events(self.forward_uinput.write_history)
        self.assertEqual(fw_history.count(scroll), 5)

        await self.send_events([scroll_release], event_reader)
        fw_history = convert_to_internal_events(self.forward_uinput.write_history)
        self.assertEqual(fw_history[-1], scroll_release)

    async def test_can_not_map(self):
        """Inject events to wrong or invalid uinput."""
        ev_1 = (EV_KEY, KEY_A, 1)
        ev_2 = (EV_KEY, KEY_B, 1)
        ev_3 = (EV_KEY, KEY_C, 1)

        ev_4 = (EV_KEY, KEY_A, 0)
        ev_5 = (EV_KEY, KEY_B, 0)
        ev_6 = (EV_KEY, KEY_C, 0)

        preset = Preset()
        m1 = Mapping(
            event_combination=EventCombination(ev_2),
            target_uinput="keyboard",
            output_type=EV_KEY,
            output_code=BTN_TL,
        )
        m2 = Mapping(
            event_combination=EventCombination(ev_3),
            target_uinput="keyboard",
            output_type=EV_KEY,
            output_code=KEY_A,
        )
        preset.add(m1)
        preset.add(m2)

        event_reader = self.get_event_reader(preset, InputDevice("/dev/input/event11"))
        # send key-down and up
        await self.send_events(
            [
                InputEvent.from_tuple(ev_1),
                InputEvent.from_tuple(ev_2),
                InputEvent.from_tuple(ev_3),
                InputEvent.from_tuple(ev_4),
                InputEvent.from_tuple(ev_5),
                InputEvent.from_tuple(ev_6),
            ],
            event_reader,
        )

        kb_history = convert_to_internal_events(
            global_uinputs.get_uinput("keyboard").write_history
        )
        fw_history = convert_to_internal_events(self.forward_uinput.write_history)

        self.assertEqual(len(fw_history), 4)
        self.assertEqual(len(kb_history), 2)
        self.assertIn(ev_1, fw_history)
        self.assertIn(ev_2, fw_history)
        self.assertIn(ev_4, fw_history)
        self.assertIn(ev_5, fw_history)
        self.assertNotIn(ev_3, fw_history)
        self.assertNotIn(ev_6, fw_history)

        self.assertIn((EV_KEY, KEY_A, 1), kb_history)
        self.assertIn((EV_KEY, KEY_A, 0), kb_history)

    async def test_switch_axis(self):
        """Test a mapping for an axis that can be switched on or off."""

        rate = 60  # rate [Hz] at which events are produced
        gain = 0.5  # halve the speed of the rel axis
        speed = 1
        preset = Preset()

        # left x to mouse x if left y is above 10%
        combination = EventCombination(((EV_ABS, ABS_X, 0), (EV_ABS, ABS_Y, 10)))
        cfg = {
            "event_combination": combination.json_str(),
            "target_uinput": "mouse",
            "output_type": EV_REL,
            "output_code": REL_X,
            "rate": rate,
            "gain": gain,
            "deadzone": 0,
            "rel_speed": speed,
        }
        m1 = Mapping(**cfg)
        preset.add(m1)

        # set input x-axis to 100%
        x = MAX_ABS
        event_reader = self.get_event_reader(
            preset, InputDevice("/dev/input/event30")
        )  # gamepad Fixture

        await event_reader.handle(InputEvent.from_tuple((EV_ABS, ABS_X, x)))
        await asyncio.sleep(0.2)  # wait a bit more for nothing to sum up
        m_history = convert_to_internal_events(
            global_uinputs.get_uinput("mouse").write_history
        )
        fw_history = convert_to_internal_events(self.forward_uinput.write_history)
        self.assertEqual(len(m_history), 0)
        self.assertEqual(len(fw_history), 1)
        self.assertEqual(fw_history[0], (EV_ABS, ABS_X, x))

        # move the y-Axis above 10%
        await self.send_events(
            (
                InputEvent.from_tuple((EV_ABS, ABS_Y, x * 0.05)),
                InputEvent.from_tuple((EV_ABS, ABS_Y, x * 0.11)),
                InputEvent.from_tuple((EV_ABS, ABS_Y, x * 0.5)),
            ),
            event_reader,
        )
        # wait a bit more for it to sum up
        sleep = 0.5
        await asyncio.sleep(sleep)
        # send some more x events
        await self.send_events(
            (
                InputEvent.from_tuple((EV_ABS, ABS_X, x)),
                InputEvent.from_tuple((EV_ABS, ABS_X, x * 0.9)),
            ),
            event_reader,
        )
        # stop it
        await event_reader.handle(
            InputEvent.from_tuple((EV_ABS, ABS_Y, MAX_ABS * 0.05))
        )

        await asyncio.sleep(0.2)  # wait a bit more for nothing to sum up
        history = convert_to_internal_events(
            global_uinputs.get_uinput("mouse").write_history
        )
        if history[0].type == EV_ABS:
            raise AssertionError(
                "The injector probably just forwarded them unchanged"
                # possibly in addition to writing mouse events
            )

        # each axis writes speed*gain*rate*sleep=1*0.5*60 events
        self.assertGreater(len(history), speed * gain * rate * sleep * 0.9)
        self.assertLess(len(history), speed * gain * rate * sleep * 1.1)

        # does not contain anything else
        count_x = history.count((EV_REL, REL_X, 1))
        self.assertEqual(len(history), count_x)


if __name__ == "__main__":
    unittest.main()
