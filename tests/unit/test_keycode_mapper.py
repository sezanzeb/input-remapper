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


import unittest
import asyncio
import time

from evdev.ecodes import (
    EV_KEY,
    EV_ABS,
    KEY_A,
    KEY_B,
    KEY_C,
    BTN_TL,
    ABS_HAT0X,
    ABS_HAT0Y,
    ABS_HAT1X,
    ABS_HAT1Y,
    ABS_Y,
)

from inputremapper.injection.mapping_handlers.keycode_mapper import (
    active_macros,
    KeycodeMapper,
    unreleased,
    subsets,
)
from inputremapper.configs.system_mapping import system_mapping
from inputremapper.injection.macros.parse import parse
from inputremapper.injection.context import Context
from inputremapper.utils import RELEASE, PRESS
from inputremapper.configs.global_config import global_config, BUTTONS
from inputremapper.configs.preset import Preset
from inputremapper.configs.system_mapping import DISABLE_CODE
from inputremapper.injection.global_uinputs import global_uinputs

from tests.test import (
    new_event,
    UInput,
    uinput_write_history,
    quick_cleanup,
    InputDevice,
    MAX_ABS,
    MIN_ABS,
)


def wait(func, timeout=1.0):
    """Wait for func to return True."""
    iterations = 0
    sleepytime = 0.1
    while not func():
        time.sleep(sleepytime)
        iterations += 1
        if iterations * sleepytime > timeout:
            raise Exception("Timeout")


def calculate_event_number(holdtime, before, after):
    """
    Parameters
    ----------
    holdtime : int
        in ms, how long was the key held down
    before : int
        how many extra k() calls are executed before h()
    after : int
        how many extra k() calls are executed after h()
    """
    keystroke_sleep = global_config.get("macros.keystroke_sleep_ms", 10)
    # down and up: two sleeps per k
    # one initial k(a):
    events = before * 2
    holdtime -= keystroke_sleep * 2
    # hold events
    events += (holdtime / (keystroke_sleep * 2)) * 2
    # one trailing k(c)
    events += after * 2
    return events


class TestKeycodeMapper(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mapping = Preset()
        self.context = Context(self.mapping)
        self.source = InputDevice("/dev/input/event11")
        self.history = []

    def tearDown(self):
        # make sure all macros are stopped by tests
        self.history = []

        for macro in active_macros.values():
            if macro.is_holding():
                macro.release_trigger()
            asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.01))
            self.assertFalse(macro.is_holding())
            self.assertFalse(macro.running)

        quick_cleanup()

    def setup_keycode_mapper(self, keycodes, macro_mapping):
        """Setup a default keycode mapper than can be used for most tests."""
        system_mapping.clear()
        for key, code in keycodes.items():
            system_mapping._set(key, code)

        # parse requires an intact system_mapping!
        self.context.macros = {
            key: (parse(code, self.context), "keyboard")
            for key, code in macro_mapping.items()
        }

        uinput = UInput()
        self.context.uinput = uinput

        keycode_mapper = KeycodeMapper(self.context, self.source, UInput())
        keycode_mapper.macro_write = self.create_handler

        return keycode_mapper

    def create_handler(self, _):
        # to reduce the likelihood of race conditions of macros that for some reason
        # are still running after the test, make sure they don't access the history
        # of the next test.
        history = self.history
        return lambda *args: history.append(args)

    async def test_subsets(self):
        a = subsets(((1,), (2,), (3,)))
        self.assertIn(((1,), (2,)), a)
        self.assertIn(((2,), (3,)), a)
        self.assertIn(((1,), (3,)), a)
        self.assertIn(((1,), (2,), (3,)), a)
        self.assertEqual(len(a), 4)

        b = subsets(((1,), (2,)))
        self.assertIn(((1,), (2,)), b)
        self.assertEqual(len(b), 1)

        c = subsets(((1,),))
        self.assertEqual(len(c), 0)

    async def test_d_pad(self):
        ev_1 = (EV_ABS, ABS_HAT0X, 1)
        ev_2 = (EV_ABS, ABS_HAT0X, -1)
        ev_3 = (EV_ABS, ABS_HAT0X, 0)

        ev_4 = (EV_ABS, ABS_HAT0Y, 1)
        ev_5 = (EV_ABS, ABS_HAT0Y, -1)
        ev_6 = (EV_ABS, ABS_HAT0Y, 0)

        uinput = UInput()
        self.context.uinput = uinput
        self.context.key_to_code = {
            (ev_1,): (51, "keyboard"),
            (ev_2,): (52, "keyboard"),
            (ev_4,): (54, "keyboard"),
            (ev_5,): (55, "keyboard"),
        }

        keycode_mapper = KeycodeMapper(self.context, self.source, uinput)

        # a bunch of d-pad key down events at once
        await keycode_mapper.notify(new_event(*ev_1))
        await keycode_mapper.notify(new_event(*ev_4))
        self.assertEqual(len(unreleased), 2)

        self.assertEqual(
            unreleased.get(ev_1[:2]).target,
            (EV_KEY, *self.context.key_to_code[(ev_1,)]),
        )
        self.assertEqual(unreleased.get(ev_1[:2]).input_event_tuple, ev_1)
        self.assertEqual(
            unreleased.get(ev_1[:2]).triggered_key, (ev_1,)
        )  # as seen in key_to_code

        self.assertEqual(
            unreleased.get(ev_4[:2]).target,
            (EV_KEY, *self.context.key_to_code[(ev_4,)]),
            ev_4,
        )
        self.assertEqual(unreleased.get(ev_4[:2]).input_event_tuple, ev_4)
        self.assertEqual(unreleased.get(ev_4[:2]).triggered_key, (ev_4,))

        # release all of them
        await keycode_mapper.notify(new_event(*ev_3))
        await keycode_mapper.notify(new_event(*ev_6))
        self.assertEqual(len(unreleased), 0)

        # repeat with other values
        await keycode_mapper.notify(new_event(*ev_2))
        await keycode_mapper.notify(new_event(*ev_5))
        self.assertEqual(len(unreleased), 2)
        self.assertEqual(
            unreleased.get(ev_2[:2]).target,
            (EV_KEY, *self.context.key_to_code[(ev_2,)]),
        )
        self.assertEqual(unreleased.get(ev_2[:2]).input_event_tuple, ev_2)
        self.assertEqual(
            unreleased.get(ev_5[:2]).target,
            (EV_KEY, *self.context.key_to_code[(ev_5,)]),
        )
        self.assertEqual(unreleased.get(ev_5[:2]).input_event_tuple, ev_5)

        # release all of them again
        await keycode_mapper.notify(new_event(*ev_3))
        await keycode_mapper.notify(new_event(*ev_6))
        self.assertEqual(len(unreleased), 0)

        self.assertEqual(len(uinput_write_history), 8)

        self.assertEqual(uinput_write_history[0].t, (EV_KEY, 51, 1))
        self.assertEqual(uinput_write_history[1].t, (EV_KEY, 54, 1))

        self.assertEqual(uinput_write_history[2].t, (EV_KEY, 51, 0))
        self.assertEqual(uinput_write_history[3].t, (EV_KEY, 54, 0))

        self.assertEqual(uinput_write_history[4].t, (EV_KEY, 52, 1))
        self.assertEqual(uinput_write_history[5].t, (EV_KEY, 55, 1))

        self.assertEqual(uinput_write_history[6].t, (EV_KEY, 52, 0))
        self.assertEqual(uinput_write_history[7].t, (EV_KEY, 55, 0))

    async def test_not_forward(self):
        down = (EV_KEY, 91, 1)
        up = (EV_KEY, 91, 0)
        uinput = global_uinputs.devices["keyboard"]

        keycode_mapper = KeycodeMapper(self.context, self.source, uinput)

        keycode_mapper.handle_keycode(new_event(*down), PRESS, forward=False)
        self.assertEqual(unreleased[(EV_KEY, 91)].input_event_tuple, down)
        self.assertEqual(unreleased[(EV_KEY, 91)].target, (*down[:2], None))
        self.assertEqual(len(unreleased), 1)
        self.assertEqual(uinput.write_count, 0)

        keycode_mapper.handle_keycode(new_event(*up), RELEASE, forward=False)
        self.assertEqual(len(unreleased), 0)
        self.assertEqual(uinput.write_count, 0)

    async def test_release_joystick_button(self):
        # with the left joystick mapped as button, it will release the mapped
        # key when it goes back to close to its resting position
        ev_1 = (3, 0, MAX_ABS // 10)  # release
        ev_3 = (3, 0, MIN_ABS)  # press

        uinput = UInput()

        _key_to_code = {((3, 0, -1),): (73, "keyboard")}

        self.mapping.set("gamepad.joystick.left_purpose", BUTTONS)

        # something with gamepad capabilities
        source = InputDevice("/dev/input/event30")

        self.context.uinput = uinput
        self.context.key_to_code = _key_to_code
        keycode_mapper = KeycodeMapper(self.context, source, uinput)

        await keycode_mapper.notify(new_event(*ev_3))
        await keycode_mapper.notify(new_event(*ev_1))

        # array of 3-tuples
        self.history = [a.t for a in uinput_write_history]

        self.assertIn((EV_KEY, 73, 1), self.history)
        self.assertEqual(self.history.count((EV_KEY, 73, 1)), 1)

        self.assertIn((EV_KEY, 73, 0), self.history)
        self.assertEqual(self.history.count((EV_KEY, 73, 0)), 1)

    async def test_dont_filter_unmapped(self):
        # if an event is not used at all, it should be written but not
        # furthermore modified. For example wheel events
        # keep reporting events of the same value without a release inbetween,
        # they should be forwarded.

        down = (EV_KEY, 91, 1)
        up = (EV_KEY, 91, 0)
        uinput = global_uinputs.devices["keyboard"]
        forward_to = UInput()

        keycode_mapper = KeycodeMapper(self.context, self.source, forward_to)

        for _ in range(10):
            # don't filter duplicate events if not mapped
            await keycode_mapper.notify(new_event(*down))

        self.assertEqual(unreleased[(EV_KEY, 91)].input_event_tuple, down)
        self.assertEqual(unreleased[(EV_KEY, 91)].target, (*down[:2], None))
        self.assertEqual(len(unreleased), 1)
        self.assertEqual(forward_to.write_count, 10)
        self.assertEqual(uinput.write_count, 0)

        await keycode_mapper.notify(new_event(*up))
        self.assertEqual(len(unreleased), 0)
        self.assertEqual(forward_to.write_count, 11)
        self.assertEqual(uinput.write_count, 0)

    async def test_filter_combi_mapped_duplicate_down(self):
        # the opposite of the other test, but don't map the key directly
        # but rather as the trigger for a combination
        down_1 = (EV_KEY, 91, 1)
        down_2 = (EV_KEY, 92, 1)
        up_1 = (EV_KEY, 91, 0)
        up_2 = (EV_KEY, 92, 0)
        # forwarded and mapped event will end up at the same place
        forward = global_uinputs.devices["keyboard"]

        output = 71

        key_to_code = {(down_1, down_2): (71, "keyboard")}

        self.context.key_to_code = key_to_code
        keycode_mapper = KeycodeMapper(self.context, self.source, forward)

        await keycode_mapper.notify(new_event(*down_1))
        for _ in range(10):
            await keycode_mapper.notify(new_event(*down_2))

        # all duplicate down events should have been ignored
        self.assertEqual(len(unreleased), 2)
        self.assertEqual(forward.write_count, 2)
        self.assertEqual(uinput_write_history[0].t, down_1)
        self.assertEqual(uinput_write_history[1].t, (EV_KEY, output, 1))

        await keycode_mapper.notify(new_event(*up_1))
        await keycode_mapper.notify(new_event(*up_2))
        self.assertEqual(len(unreleased), 0)
        self.assertEqual(forward.write_count, 4)
        self.assertEqual(uinput_write_history[2].t, up_1)
        self.assertEqual(uinput_write_history[3].t, (EV_KEY, output, 0))

    async def test_d_pad_combination(self):
        ev_1 = (EV_ABS, ABS_HAT0X, 1)
        ev_2 = (EV_ABS, ABS_HAT0Y, -1)

        ev_3 = (EV_ABS, ABS_HAT0X, 0)
        ev_4 = (EV_ABS, ABS_HAT0Y, 0)

        _key_to_code = {
            (ev_1, ev_2): (51, "keyboard"),
            (ev_2,): (52, "keyboard"),
        }

        uinput = UInput()

        self.context.uinput = uinput
        self.context.key_to_code = _key_to_code
        keycode_mapper = KeycodeMapper(self.context, self.source, uinput)

        # a bunch of d-pad key down events at once
        await keycode_mapper.notify(new_event(*ev_1))
        await keycode_mapper.notify(new_event(*ev_2))
        # (what_will_be_released, what_caused_the_key_down)
        self.assertEqual(unreleased.get(ev_1[:2]).target, (EV_ABS, ABS_HAT0X, None))
        self.assertEqual(unreleased.get(ev_1[:2]).input_event_tuple, ev_1)
        self.assertEqual(unreleased.get(ev_2[:2]).target, (EV_KEY, 51, "keyboard"))
        self.assertEqual(unreleased.get(ev_2[:2]).input_event_tuple, ev_2)
        self.assertEqual(len(unreleased), 2)

        # ev_1 is unmapped and the other is the triggered combination
        self.assertEqual(len(uinput_write_history), 2)
        self.assertEqual(uinput_write_history[0].t, ev_1)
        self.assertEqual(uinput_write_history[1].t, (EV_KEY, 51, 1))

        # release all of them
        await keycode_mapper.notify(new_event(*ev_3))
        await keycode_mapper.notify(new_event(*ev_4))
        self.assertEqual(len(unreleased), 0)

        self.assertEqual(len(uinput_write_history), 4)
        self.assertEqual(uinput_write_history[2].t, ev_3)
        self.assertEqual(uinput_write_history[3].t, (EV_KEY, 51, 0))

    async def test_notify(self):
        code_2 = 2
        # this also makes sure that the keycode_mapper doesn't get confused
        # when input and output codes are the same (because it at some point
        # screwed it up because of that)
        _key_to_code = {
            ((EV_KEY, 1, 1),): (101, "keyboard"),
            ((EV_KEY, code_2, 1),): (code_2, "keyboard"),
        }

        uinput_mapped = global_uinputs.devices["keyboard"]
        uinput_forwarded = UInput()

        self.context.key_to_code = _key_to_code
        keycode_mapper = KeycodeMapper(self.context, self.source, uinput_forwarded)

        await keycode_mapper.notify(new_event(EV_KEY, 1, 1))
        await keycode_mapper.notify(new_event(EV_KEY, 3, 1))
        await keycode_mapper.notify(new_event(EV_KEY, code_2, 1))
        await keycode_mapper.notify(new_event(EV_KEY, code_2, 0))

        self.assertEqual(len(uinput_write_history), 4)
        self.assertEqual(uinput_mapped.write_history[0].t, (EV_KEY, 101, 1))
        self.assertEqual(uinput_mapped.write_history[1].t, (EV_KEY, code_2, 1))
        self.assertEqual(uinput_mapped.write_history[2].t, (EV_KEY, code_2, 0))

        self.assertEqual(uinput_forwarded.write_history[0].t, (EV_KEY, 3, 1))

    async def test_combination_keycode(self):
        combination = ((EV_KEY, 1, 1), (EV_KEY, 2, 1))
        _key_to_code = {combination: (101, "keyboard")}

        uinput = UInput()

        self.context.uinput = uinput
        self.context.key_to_code = _key_to_code
        keycode_mapper = KeycodeMapper(self.context, self.source, uinput)

        await keycode_mapper.notify(new_event(*combination[0]))
        await keycode_mapper.notify(new_event(*combination[1]))

        self.assertEqual(len(uinput_write_history), 2)
        # the first event is written and then the triggered combination
        self.assertEqual(uinput_write_history[0].t, (EV_KEY, 1, 1))
        self.assertEqual(uinput_write_history[1].t, (EV_KEY, 101, 1))

        # release them
        await keycode_mapper.notify(new_event(*combination[0][:2], 0))
        await keycode_mapper.notify(new_event(*combination[1][:2], 0))
        # the first key writes its release event. The second key is hidden
        # behind the executed combination. The result of the combination is
        # also released, because it acts like a key.
        self.assertEqual(len(uinput_write_history), 4)
        self.assertEqual(uinput_write_history[2].t, (EV_KEY, 1, 0))
        self.assertEqual(uinput_write_history[3].t, (EV_KEY, 101, 0))

        # press them in the wrong order (the wrong key at the end, the order
        # of all other keys won't matter). no combination should be triggered
        await keycode_mapper.notify(new_event(*combination[1]))
        await keycode_mapper.notify(new_event(*combination[0]))
        self.assertEqual(len(uinput_write_history), 6)
        self.assertEqual(uinput_write_history[4].t, (EV_KEY, 2, 1))
        self.assertEqual(uinput_write_history[5].t, (EV_KEY, 1, 1))

    async def test_combination_keycode_2(self):
        combination_1 = (
            (EV_KEY, 1, 1),
            (EV_ABS, ABS_Y, MIN_ABS),
            (EV_KEY, 3, 1),
            (EV_KEY, 4, 1),
        )
        combination_2 = (
            # should not be triggered, combination_1 should be prioritized
            # when all of its keys are down
            (EV_KEY, 2, 1),
            (EV_KEY, 3, 1),
            (EV_KEY, 4, 1),
        )

        down_5 = (EV_KEY, 5, 1)
        up_5 = (EV_KEY, 5, 0)
        up_4 = (EV_KEY, 4, 0)

        def sign_value(key):
            return key[0], key[1], key[2] / abs(key[2])

        _key_to_code = {
            # key_to_code is supposed to only contain values classified into PRESS,
            # PRESS_NEGATIVE and RELEASE
            tuple([sign_value(a) for a in combination_1]): (101, "keyboard"),
            combination_2: (102, "keyboard"),
            (down_5,): (103, "keyboard"),
        }

        uinput = UInput()

        source = InputDevice("/dev/input/event30")

        # ABS_Y is part of the combination, which only works if the joystick
        # is configured as D-Pad
        self.mapping.set("gamepad.joystick.left_purpose", BUTTONS)
        self.context.uinput = uinput
        self.context.key_to_code = _key_to_code
        keycode_mapper = KeycodeMapper(self.context, source, uinput)
        self.assertIsNotNone(keycode_mapper._abs_range)

        # 10 and 11: insert some more arbitrary key-down events,
        # they should not break the combinations
        await keycode_mapper.notify(new_event(EV_KEY, 10, 1))
        await keycode_mapper.notify(new_event(*combination_1[0]))
        await keycode_mapper.notify(new_event(*combination_1[1]))
        await keycode_mapper.notify(new_event(*combination_1[2]))
        await keycode_mapper.notify(new_event(EV_KEY, 11, 1))
        await keycode_mapper.notify(new_event(*combination_1[3]))
        # combination_1 should have been triggered now

        self.assertEqual(len(uinput_write_history), 6)
        # the first events are written and then the triggered combination,
        # while the triggering event is the only one that is omitted
        self.assertEqual(uinput_write_history[1].t, combination_1[0])
        self.assertEqual(uinput_write_history[2].t, combination_1[1])
        self.assertEqual(uinput_write_history[3].t, combination_1[2])
        self.assertEqual(uinput_write_history[5].t, (EV_KEY, 101, 1))

        # while the combination is down, another unrelated key can be used
        await keycode_mapper.notify(new_event(*down_5))
        # the keycode_mapper searches for subsets of the current held-down
        # keys to activate combinations, down_5 should not trigger them
        # again.
        self.assertEqual(len(uinput_write_history), 7)
        self.assertEqual(uinput_write_history[6].t, (EV_KEY, 103, 1))

        # release the combination by releasing the last key, and release
        # the unrelated key
        await keycode_mapper.notify(new_event(*up_4))
        await keycode_mapper.notify(new_event(*up_5))
        self.assertEqual(len(uinput_write_history), 9)

        self.assertEqual(uinput_write_history[7].t, (EV_KEY, 101, 0))
        self.assertEqual(uinput_write_history[8].t, (EV_KEY, 103, 0))

    async def test_macro_writes_to_global_uinput(self):
        macro_mapping = {
            ((EV_KEY, 1, 1),): (parse("k(a)", self.context), "keyboard"),
        }

        self.context.macros = macro_mapping
        forward_to = UInput()
        keycode_mapper = KeycodeMapper(self.context, self.source, forward_to)

        await keycode_mapper.notify(new_event(EV_KEY, 1, 1))

        sleeptime = global_config.get("macros.keystroke_sleep_ms", 10) * 12
        await asyncio.sleep(sleeptime / 1000 + 0.1)

        self.assertEqual(
            global_uinputs.devices["keyboard"].write_count, 2
        )  # down and up
        self.assertEqual(forward_to.write_count, 0)

        await keycode_mapper.notify(new_event(EV_KEY, 2, 1))
        self.assertEqual(forward_to.write_count, 1)

    async def test_notify_macro(self):
        code_a, code_b = 100, 101
        keycode_mapper = self.setup_keycode_mapper(
            {"a": code_a, "b": code_b},
            {
                ((EV_KEY, 1, 1),): "k(a)",
                ((EV_KEY, 2, 1),): "r(5, k(b))",
            },
        )

        await keycode_mapper.notify(new_event(EV_KEY, 1, 1))
        await keycode_mapper.notify(new_event(EV_KEY, 2, 1))

        sleeptime = global_config.get("macros.keystroke_sleep_ms", 10) * 12

        # let the mainloop run for some time so that the macro does its stuff
        await asyncio.sleep(sleeptime / 1000 + 0.1)

        # 6 keycodes written, with down and up events
        self.assertEqual(len(self.history), 12)
        self.assertIn((EV_KEY, code_a, 1), self.history)
        self.assertIn((EV_KEY, code_a, 0), self.history)
        self.assertIn((EV_KEY, code_b, 1), self.history)
        self.assertIn((EV_KEY, code_b, 0), self.history)

        # releasing stuff
        self.assertIn((EV_KEY, 1), unreleased)
        self.assertIn((EV_KEY, 2), unreleased)
        await keycode_mapper.notify(new_event(EV_KEY, 1, 0))
        await keycode_mapper.notify(new_event(EV_KEY, 2, 0))
        self.assertNotIn((EV_KEY, 1), unreleased)
        self.assertNotIn((EV_KEY, 2), unreleased)
        await asyncio.sleep(0.1)
        self.assertEqual(len(self.history), 12)

    async def test_if_single(self):
        code_a, code_b = 100, 101
        keycode_mapper = self.setup_keycode_mapper(
            {"a": code_a, "b": code_b}, {((EV_KEY, 1, 1),): "if_single(k(a), k(b))"}
        )

        """triggers then"""

        await keycode_mapper.notify(new_event(EV_KEY, 1, 1))  # start the macro
        await asyncio.sleep(0.05)

        self.assertTrue(active_macros[(EV_KEY, 1)].running)

        await keycode_mapper.notify(new_event(EV_KEY, 1, 0))
        await asyncio.sleep(0.05)

        self.assertFalse(active_macros[(EV_KEY, 1)].running)

        self.assertIn((EV_KEY, code_a, 1), self.history)
        self.assertIn((EV_KEY, code_a, 0), self.history)
        self.assertNotIn((EV_KEY, code_b, 1), self.history)
        self.assertNotIn((EV_KEY, code_b, 0), self.history)

        """triggers else"""

        self.history.clear()

        await keycode_mapper.notify(new_event(EV_KEY, 1, 1))  # start the macro
        await asyncio.sleep(0.05)

        self.assertTrue(active_macros[(EV_KEY, 1)].running)

        await keycode_mapper.notify(new_event(EV_KEY, 2, 1))
        await asyncio.sleep(0.05)

        self.assertFalse(active_macros[(EV_KEY, 1)].running)

        self.assertNotIn((EV_KEY, code_a, 1), self.history)
        self.assertNotIn((EV_KEY, code_a, 0), self.history)
        self.assertIn((EV_KEY, code_b, 1), self.history)
        self.assertIn((EV_KEY, code_b, 0), self.history)

    async def test_hold(self):
        code_a, code_b, code_c = 100, 101, 102
        keycode_mapper = self.setup_keycode_mapper(
            {"a": code_a, "b": code_b, "c": code_c},
            {((EV_KEY, 1, 1),): "k(a).h(k(b)).k(c)"},
        )

        """start macro"""

        await keycode_mapper.notify(new_event(EV_KEY, 1, 1))

        # let the mainloop run for some time so that the macro does its stuff
        sleeptime = 500
        keystroke_sleep = global_config.get("macros.keystroke_sleep_ms", 10)
        await asyncio.sleep(sleeptime / 1000)

        self.assertTrue(active_macros[(EV_KEY, 1)].is_holding())
        self.assertTrue(active_macros[(EV_KEY, 1)].running)

        """stop macro"""

        await keycode_mapper.notify(new_event(EV_KEY, 1, 0))

        await asyncio.sleep(keystroke_sleep * 10 / 1000)

        events = calculate_event_number(sleeptime, 1, 1)

        self.assertGreater(len(self.history), events * 0.9)
        self.assertLess(len(self.history), events * 1.1)

        self.assertIn((EV_KEY, code_a, 1), self.history)
        self.assertIn((EV_KEY, code_a, 0), self.history)
        self.assertIn((EV_KEY, code_b, 1), self.history)
        self.assertIn((EV_KEY, code_b, 0), self.history)
        self.assertIn((EV_KEY, code_c, 1), self.history)
        self.assertIn((EV_KEY, code_c, 0), self.history)
        self.assertGreater(self.history.count((EV_KEY, code_b, 1)), 1)
        self.assertGreater(self.history.count((EV_KEY, code_b, 0)), 1)

        # it's stopped and won't write stuff anymore
        count_before = len(self.history)
        await asyncio.sleep(0.2)
        count_after = len(self.history)
        self.assertEqual(count_before, count_after)

        self.assertFalse(active_macros[(EV_KEY, 1)].is_holding())
        self.assertFalse(active_macros[(EV_KEY, 1)].running)

    async def test_hold_2(self):
        # test irregular input patterns
        code_a, code_b, code_c, code_d = 100, 101, 102, 103
        keycode_mapper = self.setup_keycode_mapper(
            {"a": code_a, "b": code_b, "c": code_c, "d": code_d},
            {
                ((EV_KEY, 1, 1),): "h(k(b))",
                ((EV_KEY, 2, 1),): "k(c).r(1, r(1, r(1, h(k(a))))).k(d)",
                ((EV_KEY, 3, 1),): "h(k(b))",
            },
        )

        """start macro 2"""

        await keycode_mapper.notify(new_event(EV_KEY, 2, 1))

        await asyncio.sleep(0.1)
        # starting code_c written
        self.assertEqual(self.history.count((EV_KEY, code_c, 1)), 1)
        self.assertEqual(self.history.count((EV_KEY, code_c, 0)), 1)

        # spam garbage events
        for _ in range(5):
            await keycode_mapper.notify(new_event(EV_KEY, 1, 1))
            await keycode_mapper.notify(new_event(EV_KEY, 3, 1))
            await asyncio.sleep(0.05)
            self.assertTrue(active_macros[(EV_KEY, 1)].is_holding())
            self.assertTrue(active_macros[(EV_KEY, 1)].running)
            self.assertTrue(active_macros[(EV_KEY, 2)].is_holding())
            self.assertTrue(active_macros[(EV_KEY, 2)].running)
            self.assertTrue(active_macros[(EV_KEY, 3)].is_holding())
            self.assertTrue(active_macros[(EV_KEY, 3)].running)

        # there should only be one code_c in the events, because no key
        # up event was ever done so the hold just continued
        self.assertEqual(self.history.count((EV_KEY, code_c, 1)), 1)
        self.assertEqual(self.history.count((EV_KEY, code_c, 0)), 1)
        # without an key up event on 2, it won't write code_d
        self.assertNotIn((code_d, 1), self.history)
        self.assertNotIn((code_d, 0), self.history)

        # stop macro 2
        await keycode_mapper.notify(new_event(EV_KEY, 2, 0))
        await asyncio.sleep(0.1)

        # it stopped and didn't restart, so the count stays at 1
        self.assertEqual(self.history.count((EV_KEY, code_c, 1)), 1)
        self.assertEqual(self.history.count((EV_KEY, code_c, 0)), 1)
        # and the trailing d was written
        self.assertEqual(self.history.count((EV_KEY, code_d, 1)), 1)
        self.assertEqual(self.history.count((EV_KEY, code_d, 0)), 1)

        # it's stopped and won't write stuff anymore
        count_before = self.history.count((EV_KEY, code_a, 1))
        self.assertGreater(count_before, 1)
        await asyncio.sleep(0.1)
        count_after = self.history.count((EV_KEY, code_a, 1))
        self.assertEqual(count_before, count_after)

        """restart macro 2"""

        self.history.clear()

        await keycode_mapper.notify(new_event(EV_KEY, 2, 1))
        await asyncio.sleep(0.1)
        self.assertEqual(self.history.count((EV_KEY, code_c, 1)), 1)
        self.assertEqual(self.history.count((EV_KEY, code_c, 0)), 1)

        # spam garbage events again, this time key-up events on all other
        # macros
        for _ in range(5):
            await keycode_mapper.notify(new_event(EV_KEY, 1, 0))
            await keycode_mapper.notify(new_event(EV_KEY, 3, 0))
            await asyncio.sleep(0.05)
            self.assertFalse(active_macros[(EV_KEY, 1)].is_holding())
            self.assertFalse(active_macros[(EV_KEY, 1)].running)
            self.assertTrue(active_macros[(EV_KEY, 2)].is_holding())
            self.assertTrue(active_macros[(EV_KEY, 2)].running)
            self.assertFalse(active_macros[(EV_KEY, 3)].is_holding())
            self.assertFalse(active_macros[(EV_KEY, 3)].running)

        # stop macro 2
        await keycode_mapper.notify(new_event(EV_KEY, 2, 0))
        await asyncio.sleep(0.1)
        # was started only once
        self.assertEqual(self.history.count((EV_KEY, code_c, 1)), 1)
        self.assertEqual(self.history.count((EV_KEY, code_c, 0)), 1)
        # and the trailing d was also written only once
        self.assertEqual(self.history.count((EV_KEY, code_d, 1)), 1)
        self.assertEqual(self.history.count((EV_KEY, code_d, 0)), 1)

        # stop all macros
        await keycode_mapper.notify(new_event(EV_KEY, 1, 0))
        await keycode_mapper.notify(new_event(EV_KEY, 3, 0))
        await asyncio.sleep(0.1)

        # it's stopped and won't write stuff anymore
        count_before = len(self.history)
        await asyncio.sleep(0.1)
        count_after = len(self.history)
        self.assertEqual(count_before, count_after)

        self.assertFalse(active_macros[(EV_KEY, 1)].is_holding())
        self.assertFalse(active_macros[(EV_KEY, 1)].running)
        self.assertFalse(active_macros[(EV_KEY, 2)].is_holding())
        self.assertFalse(active_macros[(EV_KEY, 2)].running)
        self.assertFalse(active_macros[(EV_KEY, 3)].is_holding())
        self.assertFalse(active_macros[(EV_KEY, 3)].running)

    async def test_hold_3(self):
        # test irregular input patterns
        code_a, code_b, code_c = 100, 101, 102
        keycode_mapper = self.setup_keycode_mapper(
            {"a": code_a, "b": code_b, "c": code_c},
            {((EV_KEY, 1, 1),): "k(a).h(k(b)).k(c)"},
        )

        await keycode_mapper.notify(new_event(EV_KEY, 1, 1))

        await asyncio.sleep(0.1)
        for _ in range(5):
            self.assertTrue(active_macros[(EV_KEY, 1)].is_holding())
            self.assertTrue(active_macros[(EV_KEY, 1)].running)
            await keycode_mapper.notify(new_event(EV_KEY, 1, 1))
            await asyncio.sleep(0.05)

        # duplicate key down events don't do anything
        self.assertEqual(self.history.count((EV_KEY, code_a, 1)), 1)
        self.assertEqual(self.history.count((EV_KEY, code_a, 0)), 1)
        self.assertEqual(self.history.count((EV_KEY, code_c, 1)), 0)
        self.assertEqual(self.history.count((EV_KEY, code_c, 0)), 0)

        # stop
        await keycode_mapper.notify(new_event(EV_KEY, 1, 0))
        await asyncio.sleep(0.1)
        self.assertEqual(self.history.count((EV_KEY, code_a, 1)), 1)
        self.assertEqual(self.history.count((EV_KEY, code_a, 0)), 1)
        self.assertEqual(self.history.count((EV_KEY, code_c, 1)), 1)
        self.assertEqual(self.history.count((EV_KEY, code_c, 0)), 1)
        self.assertFalse(active_macros[(EV_KEY, 1)].is_holding())
        self.assertFalse(active_macros[(EV_KEY, 1)].running)

        # it's stopped and won't write stuff anymore
        count_before = len(self.history)
        await asyncio.sleep(0.1)
        count_after = len(self.history)
        self.assertEqual(count_before, count_after)

    async def test_hold_two(self):
        # holding two macros at the same time,
        # the first one is triggered by a combination
        key_0 = (EV_KEY, 10)
        key_1 = (EV_KEY, 11)
        key_2 = (EV_ABS, ABS_HAT0X)
        down_0 = (*key_0, 1)
        down_1 = (*key_1, 1)
        down_2 = (*key_2, -1)
        up_0 = (*key_0, 0)
        up_1 = (*key_1, 0)
        up_2 = (*key_2, 0)

        code_1, code_2, code_3, code_a, code_b, code_c = 100, 101, 102, 103, 104, 105
        keycode_mapper = self.setup_keycode_mapper(
            {1: code_1, 2: code_2, 3: code_3, "a": code_a, "b": code_b, "c": code_c},
            {
                (down_0, down_1): "k(1).h(k(2)).k(3)",
                (down_2,): "k(a).h(k(b)).k(c)",
            },
        )

        # key up won't do anything
        await keycode_mapper.notify(new_event(*up_0))
        await keycode_mapper.notify(new_event(*up_1))
        await keycode_mapper.notify(new_event(*up_2))
        await asyncio.sleep(0.1)
        self.assertEqual(len(active_macros), 0)

        """start macros"""

        uinput_2 = UInput()
        self.context.uinput = uinput_2

        keycode_mapper = KeycodeMapper(self.context, self.source, uinput_2)

        keycode_mapper.macro_write = self.create_handler

        await keycode_mapper.notify(new_event(*down_0))
        self.assertEqual(uinput_2.write_count, 1)
        await keycode_mapper.notify(new_event(*down_1))
        await keycode_mapper.notify(new_event(*down_2))
        self.assertEqual(uinput_2.write_count, 1)

        # let the mainloop run for some time so that the macro does its stuff
        sleeptime = 500
        keystroke_sleep = global_config.get("macros.keystroke_sleep_ms", 10)
        await asyncio.sleep(sleeptime / 1000)

        # test that two macros are really running at the same time
        self.assertEqual(len(active_macros), 2)
        self.assertTrue(active_macros[key_1].is_holding())
        self.assertTrue(active_macros[key_1].running)
        self.assertTrue(active_macros[key_2].is_holding())
        self.assertTrue(active_macros[key_2].running)

        self.assertIn(down_0[:2], unreleased)
        self.assertIn(down_1[:2], unreleased)
        self.assertIn(down_2[:2], unreleased)

        """stop macros"""

        keycode_mapper = KeycodeMapper(self.context, self.source, None)

        # releasing the last key of a combination releases the whole macro
        await keycode_mapper.notify(new_event(*up_1))
        await keycode_mapper.notify(new_event(*up_2))

        self.assertIn(down_0[:2], unreleased)
        self.assertNotIn(down_1[:2], unreleased)
        self.assertNotIn(down_2[:2], unreleased)

        await asyncio.sleep(keystroke_sleep * 10 / 1000)

        self.assertFalse(active_macros[key_1].is_holding())
        self.assertFalse(active_macros[key_1].running)
        self.assertFalse(active_macros[key_2].is_holding())
        self.assertFalse(active_macros[key_2].running)

        events = calculate_event_number(sleeptime, 1, 1) * 2

        self.assertGreater(len(self.history), events * 0.9)
        self.assertLess(len(self.history), events * 1.1)

        self.assertIn((EV_KEY, code_a, 1), self.history)
        self.assertIn((EV_KEY, code_a, 0), self.history)
        self.assertIn((EV_KEY, code_b, 1), self.history)
        self.assertIn((EV_KEY, code_b, 0), self.history)
        self.assertIn((EV_KEY, code_c, 1), self.history)
        self.assertIn((EV_KEY, code_c, 0), self.history)
        self.assertIn((EV_KEY, code_1, 1), self.history)
        self.assertIn((EV_KEY, code_1, 0), self.history)
        self.assertIn((EV_KEY, code_2, 1), self.history)
        self.assertIn((EV_KEY, code_2, 0), self.history)
        self.assertIn((EV_KEY, code_3, 1), self.history)
        self.assertIn((EV_KEY, code_3, 0), self.history)
        self.assertGreater(self.history.count((EV_KEY, code_b, 1)), 1)
        self.assertGreater(self.history.count((EV_KEY, code_b, 0)), 1)
        self.assertGreater(self.history.count((EV_KEY, code_2, 1)), 1)
        self.assertGreater(self.history.count((EV_KEY, code_2, 0)), 1)

        # it's stopped and won't write stuff anymore
        count_before = len(self.history)
        await asyncio.sleep(0.2)
        count_after = len(self.history)
        self.assertEqual(count_before, count_after)

    async def test_filter_trigger_spam(self):
        # test_filter_duplicates
        trigger = (EV_KEY, BTN_TL)

        _key_to_code = {
            ((*trigger, 1),): (51, "keyboard"),
            ((*trigger, -1),): (52, "keyboard"),
        }

        uinput = UInput()

        self.context.uinput = uinput
        self.context.key_to_code = _key_to_code
        keycode_mapper = KeycodeMapper(self.context, self.source, uinput)

        """positive"""

        for _ in range(1, 20):
            await keycode_mapper.notify(new_event(*trigger, 1))
            self.assertIn(trigger, unreleased)

        await keycode_mapper.notify(new_event(*trigger, 0))
        self.assertNotIn(trigger, unreleased)

        self.assertEqual(len(uinput_write_history), 2)

        """negative"""

        for _ in range(1, 20):
            await keycode_mapper.notify(new_event(*trigger, -1))
            self.assertIn(trigger, unreleased)

        await keycode_mapper.notify(new_event(*trigger, 0))
        self.assertNotIn(trigger, unreleased)

        self.assertEqual(len(uinput_write_history), 4)
        self.assertEqual(uinput_write_history[0].t, (EV_KEY, 51, 1))
        self.assertEqual(uinput_write_history[1].t, (EV_KEY, 51, 0))
        self.assertEqual(uinput_write_history[2].t, (EV_KEY, 52, 1))
        self.assertEqual(uinput_write_history[3].t, (EV_KEY, 52, 0))

    async def test_ignore_hold(self):
        # hold as in event-value 2, not in macro-hold.
        # linux will generate events with value 2 after input-remapper injected
        # the key-press, so input-remapper doesn't need to forward them. That
        # would cause duplicate events of those values otherwise.
        key = (EV_KEY, KEY_A)
        ev_1 = (*key, 1)
        ev_2 = (*key, 2)
        ev_3 = (*key, 0)

        _key_to_code = {
            ((*key, 1),): (21, "keyboard"),
        }

        uinput = UInput()

        self.context.uinput = uinput
        self.context.key_to_code = _key_to_code
        keycode_mapper = KeycodeMapper(self.context, self.source, uinput)

        await keycode_mapper.notify(new_event(*ev_1))

        for _ in range(10):
            await keycode_mapper.notify(new_event(*ev_2))

        self.assertIn(key, unreleased)
        await keycode_mapper.notify(new_event(*ev_3))
        self.assertNotIn(key, unreleased)

        self.assertEqual(len(uinput_write_history), 2)
        self.assertEqual(uinput_write_history[0].t, (EV_KEY, 21, 1))
        self.assertEqual(uinput_write_history[1].t, (EV_KEY, 21, 0))

    async def test_ignore_disabled(self):
        ev_1 = (EV_ABS, ABS_HAT0Y, 1)
        ev_2 = (EV_ABS, ABS_HAT0Y, 0)

        ev_3 = (EV_ABS, ABS_HAT0X, 1)  # disabled
        ev_4 = (EV_ABS, ABS_HAT0X, 0)

        ev_5 = (EV_KEY, KEY_A, 1)
        ev_6 = (EV_KEY, KEY_A, 0)

        combi_1 = (ev_5, ev_3)
        combi_2 = (ev_3, ev_5)

        _key_to_code = {
            (ev_1,): (61, "keyboard"),
            (ev_3,): (DISABLE_CODE, "keyboard"),
            combi_1: (62, "keyboard"),
            combi_2: (63, "keyboard"),
        }

        forward_to = UInput()

        self.context.key_to_code = _key_to_code
        keycode_mapper = KeycodeMapper(self.context, self.source, forward_to)

        def expect_writecounts(uinput_count, forwarded_count):
            self.assertEqual(
                global_uinputs.devices["keyboard"].write_count, uinput_count
            )
            self.assertEqual(forward_to.write_count, forwarded_count)

        """single keys"""

        # down
        await keycode_mapper.notify(new_event(*ev_1))
        await keycode_mapper.notify(new_event(*ev_3))
        self.assertIn(ev_1[:2], unreleased)
        self.assertIn(ev_3[:2], unreleased)
        expect_writecounts(1, 0)
        # up
        await keycode_mapper.notify(new_event(*ev_2))
        await keycode_mapper.notify(new_event(*ev_4))
        expect_writecounts(2, 0)
        self.assertNotIn(ev_1[:2], unreleased)
        self.assertNotIn(ev_3[:2], unreleased)

        self.assertEqual(len(uinput_write_history), 2)
        self.assertEqual(uinput_write_history[0].t, (EV_KEY, 61, 1))
        self.assertEqual(uinput_write_history[1].t, (EV_KEY, 61, 0))

        """a combination that ends in a disabled key"""

        # ev_5 should be forwarded and the combination triggered
        await keycode_mapper.notify(new_event(*combi_1[0]))  # ev_5
        await keycode_mapper.notify(new_event(*combi_1[1]))  # ev_3
        expect_writecounts(3, 1)
        self.assertEqual(len(uinput_write_history), 4)
        self.assertEqual(uinput_write_history[2].t, (EV_KEY, KEY_A, 1))
        self.assertEqual(uinput_write_history[3].t, (EV_KEY, 62, 1))
        self.assertIn(combi_1[0][:2], unreleased)
        self.assertIn(combi_1[1][:2], unreleased)
        # since this event did not trigger anything, key is None
        self.assertEqual(unreleased[combi_1[0][:2]].triggered_key, None)
        # that one triggered something from _key_to_code, so the key is that
        self.assertEqual(unreleased[combi_1[1][:2]].triggered_key, combi_1)

        # release the last key of the combi first, it should
        # release what the combination maps to
        event = new_event(combi_1[1][0], combi_1[1][1], 0)
        await keycode_mapper.notify(event)
        expect_writecounts(4, 1)
        self.assertEqual(len(uinput_write_history), 5)
        self.assertEqual(uinput_write_history[-1].t, (EV_KEY, 62, 0))
        self.assertIn(combi_1[0][:2], unreleased)
        self.assertNotIn(combi_1[1][:2], unreleased)

        event = new_event(combi_1[0][0], combi_1[0][1], 0)
        await keycode_mapper.notify(event)
        expect_writecounts(4, 2)
        self.assertEqual(len(uinput_write_history), 6)
        self.assertEqual(uinput_write_history[-1].t, (EV_KEY, KEY_A, 0))
        self.assertNotIn(combi_1[0][:2], unreleased)
        self.assertNotIn(combi_1[1][:2], unreleased)

        """a combination that starts with a disabled key"""

        # only the combination should get triggered
        await keycode_mapper.notify(new_event(*combi_2[0]))
        await keycode_mapper.notify(new_event(*combi_2[1]))
        expect_writecounts(5, 2)
        self.assertEqual(len(uinput_write_history), 7)
        self.assertEqual(uinput_write_history[-1].t, (EV_KEY, 63, 1))

        # release the last key of the combi first, it should
        # release what the combination maps to
        event = new_event(combi_2[1][0], combi_2[1][1], 0)
        await keycode_mapper.notify(event)
        self.assertEqual(len(uinput_write_history), 8)
        self.assertEqual(uinput_write_history[-1].t, (EV_KEY, 63, 0))
        expect_writecounts(6, 2)

        # the first key of combi_2 is disabled, so it won't write another
        # key-up event
        event = new_event(combi_2[0][0], combi_2[0][1], 0)
        await keycode_mapper.notify(event)
        self.assertEqual(len(uinput_write_history), 8)
        expect_writecounts(6, 2)

    async def test_combination_keycode_macro_mix(self):
        # ev_1 triggers macro, ev_1 + ev_2 triggers key while the macro is
        # still running
        down_1 = (EV_ABS, ABS_HAT1X, 1)
        down_2 = (EV_ABS, ABS_HAT1Y, -1)
        up_1 = (EV_ABS, ABS_HAT1X, 0)
        up_2 = (EV_ABS, ABS_HAT1Y, 0)

        keycode_mapper = self.setup_keycode_mapper({"a": 92}, {(down_1,): "h(k(a))"})
        _key_to_code = {(down_1, down_2): (91, "keyboard")}
        self.context.key_to_code = _key_to_code

        # macro starts
        await keycode_mapper.notify(new_event(*down_1))
        await asyncio.sleep(0.05)
        self.assertEqual(len(uinput_write_history), 0)
        self.assertGreater(len(self.history), 1)
        self.assertIn(down_1[:2], unreleased)
        self.assertIn((EV_KEY, 92, 1), self.history)

        # combination triggered
        await keycode_mapper.notify(new_event(*down_2))
        self.assertIn(down_1[:2], unreleased)
        self.assertIn(down_2[:2], unreleased)
        self.assertEqual(uinput_write_history[0].t, (EV_KEY, 91, 1))

        len_a = len(self.history)
        await asyncio.sleep(0.05)
        len_b = len(self.history)
        # still running
        self.assertGreater(len_b, len_a)

        # release
        await keycode_mapper.notify(new_event(*up_1))
        self.assertNotIn(down_1[:2], unreleased)
        self.assertIn(down_2[:2], unreleased)
        await asyncio.sleep(0.05)
        len_c = len(self.history)
        await asyncio.sleep(0.05)
        len_d = len(self.history)
        # not running anymore
        self.assertEqual(len_c, len_d)

        await keycode_mapper.notify(new_event(*up_2))
        self.assertEqual(uinput_write_history[1].t, (EV_KEY, 91, 0))
        self.assertEqual(len(uinput_write_history), 2)
        self.assertNotIn(down_1[:2], unreleased)
        self.assertNotIn(down_2[:2], unreleased)

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

        scroll = (2, 8, -1)
        scroll_release = (2, 8, 0)
        btn_down = (1, 276, 1)
        btn_up = (1, 276, 0)
        combination = ((1, 276, 1), (2, 8, -1))

        system_mapping.clear()
        system_mapping._set("a", 30)
        k2c = {combination: (30, "keyboard")}

        uinput = UInput()

        self.context.uinput = uinput
        self.context.key_to_code = k2c
        keycode_mapper = KeycodeMapper(self.context, self.source, uinput)

        await keycode_mapper.notify(new_event(*btn_down))
        # "forwarding"
        self.assertEqual(uinput_write_history[0].t, btn_down)

        await keycode_mapper.notify(new_event(*scroll))
        # "maps to 30"
        self.assertEqual(uinput_write_history[1].t, (1, 30, 1))

        for _ in range(5):
            # keep scrolling
            # "duplicate key down"
            await keycode_mapper.notify(new_event(*scroll))

        # nothing new since all of them were duplicate key downs
        self.assertEqual(len(uinput_write_history), 2)

        await keycode_mapper.notify(new_event(*btn_up))
        # "forwarding release"
        self.assertEqual(uinput_write_history[2].t, btn_up)

        # one more scroll event. since the combination is still not released,
        # it should be ignored as duplicate key-down
        self.assertEqual(len(uinput_write_history), 3)
        # "forwarding" (should be "duplicate key down")
        await keycode_mapper.notify(new_event(*scroll))
        self.assertEqual(len(uinput_write_history), 3)

        # the failure to release the mapped key
        # forward=False is what the debouncer uses, because a
        # "scroll release" doesn't actually exist so it is not actually
        # written if it doesn't release any mapping
        keycode_mapper.handle_keycode(
            new_event(*scroll_release), RELEASE, forward=False
        )

        # 30 should be released
        self.assertEqual(uinput_write_history[3].t, (1, 30, 0))
        self.assertEqual(len(uinput_write_history), 4)

    async def test_debounce_1(self):
        tick_time = 1 / 60
        self.history = []

        keycode_mapper = KeycodeMapper(self.context, self.source)
        keycode_mapper.debounce(1234, self.history.append, (1,), 10)
        asyncio.ensure_future(keycode_mapper.run())  # run alongside the test
        await asyncio.sleep(6 * tick_time)
        self.assertEqual(len(self.history), 0)
        await asyncio.sleep(6 * tick_time)
        self.assertEqual(len(self.history), 1)
        # won't get called a second time
        await asyncio.sleep(12 * tick_time)
        self.assertEqual(len(self.history), 1)
        self.assertEqual(self.history[0], 1)

    async def test_debounce_2(self):
        tick_time = 1 / 60
        self.history = []

        keycode_mapper = KeycodeMapper(self.context, self.source)
        keycode_mapper.debounce(1234, self.history.append, ("first",), 10)
        asyncio.ensure_future(keycode_mapper.run())  # run alongside the test
        await asyncio.sleep(6 * tick_time)
        self.assertEqual(len(self.history), 0)

        # replaces
        keycode_mapper.debounce(1234, self.history.append, ("second",), 20)
        await asyncio.sleep(5 * tick_time)
        self.assertEqual(len(self.history), 0)
        await asyncio.sleep(17 * tick_time)
        self.assertEqual(len(self.history), 1)
        self.assertEqual(self.history[0], "second")
        # won't get called a second time
        await asyncio.sleep(22 * tick_time)
        self.assertEqual(len(self.history), 1)
        self.assertEqual(self.history[0], "second")

    async def test_debounce_3(self):
        tick_time = 1 / 60
        self.history = []

        keycode_mapper = KeycodeMapper(self.context, self.source)
        keycode_mapper.debounce(1234, self.history.append, (1,), 10)
        keycode_mapper.debounce(5678, self.history.append, (2,), 20)
        asyncio.ensure_future(keycode_mapper.run())  # run alongside the test
        await asyncio.sleep(12 * tick_time)
        self.assertEqual(len(self.history), 1)
        await asyncio.sleep(12 * tick_time)
        self.assertEqual(len(self.history), 2)
        await asyncio.sleep(22 * tick_time)
        self.assertEqual(len(self.history), 2)
        self.assertEqual(self.history[0], 1)
        self.assertEqual(self.history[1], 2)

    async def test_can_not_map(self):
        """inject events to wrong or invalid uinput"""
        ev_1 = (EV_KEY, KEY_A, 1)
        ev_2 = (EV_KEY, KEY_B, 1)
        ev_3 = (EV_KEY, KEY_C, 1)

        ev_4 = (EV_KEY, KEY_A, 0)
        ev_5 = (EV_KEY, KEY_B, 0)
        ev_6 = (EV_KEY, KEY_C, 0)

        self.context.key_to_code = {
            (ev_1,): (51, "foo"),  # invalid
            (ev_2,): (BTN_TL, "keyboard"),  # invalid
            (ev_3,): (KEY_A, "keyboard"),  # valid
        }

        keyboard = global_uinputs.get_uinput("keyboard")
        forward = UInput()
        keycode_mapper = KeycodeMapper(self.context, self.source, forward)

        # send key-down
        await keycode_mapper.notify(new_event(*ev_1))
        await keycode_mapper.notify(new_event(*ev_2))
        await keycode_mapper.notify(new_event(*ev_3))
        self.assertEqual(len(unreleased), 3)
        # send key-up
        await keycode_mapper.notify(new_event(*ev_4))
        await keycode_mapper.notify(new_event(*ev_5))
        await keycode_mapper.notify(new_event(*ev_6))

        # all key down and key up events get forwarded
        self.assertEqual(forward.write_count, 4)
        self.assertEqual(keyboard.write_count, 2)
        forward_history = [event.t for event in forward.write_history]
        self.assertIn(ev_1, forward_history)
        self.assertIn(ev_2, forward_history)
        self.assertIn(ev_4, forward_history)
        self.assertIn(ev_5, forward_history)
        self.assertNotIn(ev_3, forward_history)
        self.assertNotIn(ev_6, forward_history)

        keyboard_history = [event.t for event in keyboard.write_history]
        self.assertIn((EV_KEY, KEY_A, 1), keyboard_history)
        self.assertIn((EV_KEY, KEY_A, 0), keyboard_history)


if __name__ == "__main__":
    unittest.main()
