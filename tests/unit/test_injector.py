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
from pydantic import ValidationError

from inputremapper.configs.mapping import Mapping
from tests.test import (
    new_event,
    push_events,
    fixtures,
    EVENT_READ_TIMEOUT,
    uinput_write_history_pipe,
    MAX_ABS,
    quick_cleanup,
    read_write_history_pipe,
    InputDevice,
    uinputs,
    keyboard_keys,
    MIN_ABS,
    get_key_mapping,
)

import unittest
from unittest import mock
import time

import evdev
from evdev.ecodes import (
    EV_REL,
    EV_KEY,
    EV_ABS,
    ABS_HAT0X,
    KEY_A,
    REL_X,
    REL_Y,
    REL_WHEEL,
    REL_HWHEEL,
    BTN_A,
    ABS_X,
    ABS_Y,
    ABS_Z,
    ABS_RZ,
    ABS_VOLUME,
    KEY_C,
)

from inputremapper.injection.injector import (
    Injector,
    is_in_capabilities,
    STARTING,
    RUNNING,
    STOPPED,
    NO_GRAB,
    UNKNOWN,
    get_udev_name,
)
from inputremapper.injection.numlock import is_numlock_on
from inputremapper.configs.system_mapping import (
    system_mapping,
    DISABLE_CODE,
    DISABLE_NAME,
)
from inputremapper.gui.active_preset import active_preset
from inputremapper.configs.preset import Preset
from inputremapper.configs.global_config import global_config, NONE, MOUSE, WHEEL
from inputremapper.event_combination import EventCombination
from inputremapper.injection.macros.parse import parse
from inputremapper.injection.context import Context
from inputremapper.groups import groups, classify, GAMEPAD


def wait_for_uinput_write():
    start = time.time()
    if not uinput_write_history_pipe[0].poll(timeout=10):
        raise AssertionError("No event written within 10 seconds")
    return float(time.time() - start)


class TestInjector(unittest.IsolatedAsyncioTestCase):
    new_gamepad_path = "/dev/input/event100"

    @classmethod
    def setUpClass(cls):
        cls.injector = None
        cls.grab = evdev.InputDevice.grab
        quick_cleanup()

    def setUp(self):
        self.failed = 0
        self.make_it_fail = 2

        def grab_fail_twice(_):
            if self.failed < self.make_it_fail:
                self.failed += 1
                raise OSError()

        evdev.InputDevice.grab = grab_fail_twice

    def tearDown(self):
        if self.injector is not None:
            self.injector.stop_injecting()
            self.assertEqual(self.injector.get_state(), STOPPED)
            self.injector = None
        evdev.InputDevice.grab = self.grab

        quick_cleanup()

    def test_grab(self):
        # path is from the fixtures
        path = "/dev/input/event10"
        preset = Preset()
        preset.add(get_key_mapping(EventCombination([EV_KEY, 10, 1]), "keyboard", "a"))

        self.injector = Injector(groups.find(key="Foo Device 2"), preset)
        # this test needs to pass around all other constraints of
        # _grab_device
        self.injector.context = Context(preset)
        device = self.injector._grab_device(path)
        gamepad = classify(device) == GAMEPAD
        self.assertFalse(gamepad)
        self.assertEqual(self.failed, 2)
        # success on the third try
        self.assertEqual(device.name, fixtures[path]["name"])

    def test_fail_grab(self):
        self.make_it_fail = 999
        preset = Preset()
        preset.add(get_key_mapping(EventCombination([EV_KEY, 10, 1]), "keyboard", "a"))

        self.injector = Injector(groups.find(key="Foo Device 2"), preset)
        path = "/dev/input/event10"
        self.injector.context = Context(preset)
        device = self.injector._grab_device(path)
        self.assertIsNone(device)
        self.assertGreaterEqual(self.failed, 1)

        self.assertEqual(self.injector.get_state(), UNKNOWN)
        self.injector.start()
        self.assertEqual(self.injector.get_state(), STARTING)
        # since none can be grabbed, the process will terminate. But that
        # actually takes quite some time.
        time.sleep(self.injector.regrab_timeout * 12)
        self.assertFalse(self.injector.is_alive())
        self.assertEqual(self.injector.get_state(), NO_GRAB)

    def test_grab_device_1(self):
        preset = Preset()
        preset.add(get_key_mapping(EventCombination([EV_ABS, ABS_HAT0X, 1]), "keyboard", "a"))
        self.injector = Injector(groups.find(name="gamepad"), preset)
        self.injector.context = Context(preset)

        _grab_device = self.injector._grab_device
        # doesn't have the required capability
        self.assertIsNone(_grab_device("/dev/input/event10"))
        # according to the fixtures, /dev/input/event30 can do ABS_HAT0X
        self.assertIsNotNone(_grab_device("/dev/input/event30"))
        # this doesn't exist
        self.assertIsNone(_grab_device("/dev/input/event1234"))

    def test_forward_gamepad_events(self):
        # forward abs joystick events
        preset = Preset()
        self.injector = Injector(groups.find(name="gamepad"), preset)
        self.injector.context = Context(preset)

        path = "/dev/input/event30"
        device = self.injector._grab_device(path)
        self.assertIsNone(device)  # no capability is used, so it won't grab

        preset.add(get_key_mapping(EventCombination([EV_KEY, BTN_A, 1]), "keyboard", "a"))
        device = self.injector._grab_device(path)
        self.assertIsNotNone(device)
        gamepad = classify(device) == GAMEPAD
        self.assertTrue(gamepad)

    def test_skip_unused_device(self):
        # skips a device because its capabilities are not used in the preset
        preset = Preset()
        preset.add(get_key_mapping(EventCombination([EV_KEY, 10, 1]), "keyboard", "a"))
        self.injector = Injector(groups.find(key="Foo Device 2"), preset)
        self.injector.context = Context(preset)
        path = "/dev/input/event11"
        device = self.injector._grab_device(path)
        self.assertIsNone(device)
        self.assertEqual(self.failed, 0)

    def test_skip_unknown_device(self):
        preset = Preset()
        preset.add(get_key_mapping(EventCombination([EV_KEY, 10, 1]), "keyboard", "a"))

        # skips a device because its capabilities are not used in the preset
        self.injector = Injector(groups.find(key="Foo Device 2"), preset)
        self.injector.context = Context(preset)
        path = "/dev/input/event11"
        device = self.injector._grab_device(path)

        # skips the device alltogether, so no grab attempts fail
        self.assertEqual(self.failed, 0)
        self.assertIsNone(device)

    def test_abs_to_rel(self):
        # TODO move to test_event_pipeline
        # maps gamepad joystick events to mouse events

        rate = 60  # rate [Hz] at which events are produced
        gain = 0.5  # halve the speed of the rel axis
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

        }
        m1 = Mapping(**cfg)
        preset.add(m1)
        # left y to mouse y
        cfg["event_combination"] = ",".join((str(EV_ABS), str(ABS_Y), "0"))
        cfg["output_code"] = REL_Y
        m2 = Mapping(**cfg)
        preset.add(m2)

        # set input axis to 1
        x = 1
        y = 1

        self.injector = Injector(groups.find(name="gamepad"), preset)
        self.injector.start()

        push_events(
            "gamepad",
            [
                new_event(EV_ABS, ABS_X, x),
                new_event(EV_ABS, ABS_Y, y),
                new_event(EV_ABS, ABS_X, -x),
                new_event(EV_ABS, ABS_Y, -y),
            ],
        )

        # wait for the injector to start sending, at most 1s
        uinput_write_history_pipe[0].poll(1)

        # wait a bit more for it to sum up
        sleep = 0.5
        time.sleep(sleep)

        # convert the write history to some easier to manage list
        history = read_write_history_pipe()

        if history[0][0] == EV_ABS:
            raise AssertionError(
                "The injector probably just forwarded them unchanged"
                # possibly in addition to writing mouse events
            )

        # movement is written at 60hz it moves input_value*rate pixels per event
        # move 1px. take it times 2 for both x and y events.
        self.assertGreater(len(history), rate * sleep * 0.9 * gain)
        self.assertLess(len(history), rate * sleep * 1.1 * gain)

        # those may be in arbitrary order
        count_x = history.count((EV_REL, REL_X, -1))
        count_y = history.count((EV_REL, REL_Y, -1))
        self.assertGreater(count_x, 1)
        self.assertGreater(count_y, 1)
        # only those two types of events were written
        self.assertEqual(len(history), count_x + count_y)

    def test_forward_abs(self):
        # TODO move to test_event_pipeline
        push_events(
            "gamepad",
            [
                # should forward them unmodified
                new_event(EV_ABS, ABS_X, 10),
                new_event(EV_ABS, ABS_Y, 20),
                new_event(EV_ABS, ABS_X, -30),
                new_event(EV_ABS, ABS_Y, -40),
                new_event(EV_KEY, BTN_A, 1),
                new_event(EV_KEY, BTN_A, 0),
            ]
            * 2,
        )

        preset = Preset()
        # BTN_A -> 77
        preset.add(get_key_mapping(EventCombination([1, BTN_A, 1]), "keyboard", "b"))
        system_mapping._set("b", 77)
        self.injector = Injector(groups.find(name="gamepad"), preset)
        self.injector.start()

        # wait for the injector to start sending, at most 1s
        uinput_write_history_pipe[0].poll(1)
        time.sleep(0.2)

        # convert the write history to some easier to manage list
        history = read_write_history_pipe()

        self.assertEqual(history.count((EV_ABS, ABS_X, 10)), 2)
        self.assertEqual(history.count((EV_ABS, ABS_Y, 20)), 2)
        self.assertEqual(history.count((EV_ABS, ABS_X, -30)), 2)
        self.assertEqual(history.count((EV_ABS, ABS_Y, -40)), 2)
        self.assertEqual(history.count((EV_KEY, 77, 1)), 2)
        self.assertEqual(history.count((EV_KEY, 77, 0)), 2)

    def test_get_udev_name(self):
        self.injector = Injector(groups.find(key="Foo Device 2"), active_preset)
        suffix = "mapped"
        prefix = "input-remapper"
        expected = f'{prefix} {"a" * (80 - len(suffix) - len(prefix) - 2)} {suffix}'
        self.assertEqual(len(expected), 80)
        self.assertEqual(get_udev_name("a" * 100, suffix), expected)

        self.injector.device = "abcd"
        self.assertEqual(
            get_udev_name("abcd", "forwarded"),
            "input-remapper abcd forwarded",
        )

    @mock.patch("evdev.InputDevice.ungrab")
    def test_capabilities_and_uinput_presence(self, ungrab_patch):
        preset = Preset()
        m1 = get_key_mapping(EventCombination([EV_KEY, KEY_A, 1]), "keyboard", "c")
        m2 = get_key_mapping(EventCombination([EV_REL, REL_HWHEEL, 1]), "keyboard", "key(b)")
        preset.add(m1)
        preset.add(m2)
        self.injector = Injector(groups.find(key="Foo Device 2"), preset)
        self.injector.stop_injecting()
        self.injector.run()

        self.assertEqual(self.injector.context.preset.get_mapping(EventCombination([EV_KEY, KEY_A, 1])), m1)
        self.assertEqual(self.injector.context.preset.get_mapping(EventCombination([EV_REL, REL_HWHEEL, 1])), m2)

        self.assertListEqual(
            sorted(uinputs.keys()),
            sorted(
                [
                    # reading and preventing original events from reaching the
                    # display server
                    "input-remapper Foo Device foo forwarded",
                    "input-remapper Foo Device forwarded",
                ]
            ),
        )

        forwarded_foo = uinputs.get("input-remapper Foo Device foo forwarded")
        forwarded = uinputs.get("input-remapper Foo Device forwarded")
        self.assertIsNotNone(forwarded_foo)
        self.assertIsNotNone(forwarded)

        # copies capabilities for all other forwarded devices
        self.assertIn(EV_REL, forwarded_foo.capabilities())
        self.assertIn(EV_KEY, forwarded.capabilities())
        self.assertEqual(sorted(forwarded.capabilities()[EV_KEY]), keyboard_keys)

        self.assertEqual(ungrab_patch.call_count, 2)

    def test_injector(self):
        numlock_before = is_numlock_on()

        # stuff the preset outputs
        system_mapping.clear()
        code_a = 100
        code_q = 101
        code_w = 102
        system_mapping._set("a", code_a)
        system_mapping._set("key_q", code_q)
        system_mapping._set("w", code_w)

        preset = Preset()
        preset.add(get_key_mapping(EventCombination((EV_KEY, 8, 1), (EV_KEY, 9, 1)), "keyboard", "k(KEY_Q).k(w)"))
        preset.add(get_key_mapping(EventCombination([EV_ABS, ABS_HAT0X, -1]), "keyboard", "a"))
        # one mapping that is unknown in the system_mapping on purpose
        input_b = 10
        with self.assertRaises(ValidationError):
            preset.add(get_key_mapping(EventCombination([EV_KEY, input_b, 1]), "keyboard", "b"))

        push_events(
            "gamepad",
            [
                # should execute a macro...
                new_event(EV_KEY, 8, 1),  # forwarded
                new_event(EV_KEY, 9, 1),  # triggers macro
                new_event(EV_KEY, 8, 0),  # releases macro
                new_event(EV_KEY, 9, 0),  # forwarded
                # gamepad stuff. trigger a combination
                new_event(EV_ABS, ABS_HAT0X, -1),
                new_event(EV_ABS, ABS_HAT0X, 0),
                # just pass those over without modifying
                new_event(EV_KEY, 10, 1),
                new_event(EV_KEY, 10, 0),
                new_event(3124, 3564, 6542),
            ],
        )

        self.injector = Injector(groups.find(name="gamepad"), preset)
        self.assertEqual(self.injector.get_state(), UNKNOWN)
        self.injector.start()
        self.assertEqual(self.injector.get_state(), STARTING)

        uinput_write_history_pipe[0].poll(timeout=1)
        self.assertEqual(self.injector.get_state(), RUNNING)
        time.sleep(EVENT_READ_TIMEOUT * 10)

        # sending anything arbitrary does not stop the process
        # (is_alive checked later after some time)
        self.injector._msg_pipe[1].send(1234)

        # convert the write history to some easier to manage list
        history = read_write_history_pipe()

        # 1 event before the combination was triggered
        # 2 events for releasing the combination trigger (by combination handler)
        # 4 events for the macro
        # 1 release of the event that didn't release the macro
        # 2 for mapped keys
        # 3 for forwarded events
        self.assertEqual(len(history), 13)

        # the first bit is ordered properly
        self.assertEqual(history[0], (EV_KEY, 8, 1))  # forwarded
        del history[0]
        self.assertIn((EV_KEY, 8, 0), history[0:2])  # released by combination handler
        self.assertIn((EV_KEY, 9, 0), history[0:2])  # released by combination handler
        del history[0]
        del history[0]

        # since the macro takes a little bit of time to execute, its
        # keystrokes are all over the place.
        # just check if they are there and if so, remove them from the list.
        # the macro itself
        self.assertIn((EV_KEY, code_q, 1), history)
        self.assertIn((EV_KEY, code_q, 0), history)
        self.assertIn((EV_KEY, code_w, 1), history)
        self.assertIn((EV_KEY, code_w, 0), history)
        index_q_1 = history.index((EV_KEY, code_q, 1))
        index_q_0 = history.index((EV_KEY, code_q, 0))
        index_w_1 = history.index((EV_KEY, code_w, 1))
        index_w_0 = history.index((EV_KEY, code_w, 0))
        self.assertGreater(index_q_0, index_q_1)
        self.assertGreater(index_w_1, index_q_0)
        self.assertGreater(index_w_0, index_w_1)
        del history[index_w_0]
        del history[index_w_1]
        del history[index_q_0]
        del history[index_q_1]

        # the rest should be in order now.
        # first the released combination key which did not release the macro.
        # the combination key which released the macro won't appear here.
        self.assertEqual(history[0], (EV_KEY, 9, 0))
        # value should be 1, even if the input event was -1.
        # Injected keycodes should always be either 0 or 1
        self.assertEqual(history[1], (EV_KEY, code_a, 1))
        self.assertEqual(history[2], (EV_KEY, code_a, 0))
        self.assertEqual(history[3], (EV_KEY, input_b, 1))
        self.assertEqual(history[4], (EV_KEY, input_b, 0))
        self.assertEqual(history[5], (3124, 3564, 6542))

        time.sleep(0.1)
        self.assertTrue(self.injector.is_alive())

        numlock_after = is_numlock_on()
        self.assertEqual(numlock_before, numlock_after)
        self.assertEqual(self.injector.get_state(), RUNNING)

    def test_any_event_as_button(self):
        # as long as there is an event handler and a mapping we should be able to map anything to a button

        w_down = (EV_ABS, ABS_Y, -12345)  # value needs to be lower than 10% below center of axis (absinfo)
        w_up = (EV_ABS, ABS_Y, 0)

        s_down = (EV_ABS, ABS_Y, 12345)
        s_up = (EV_ABS, ABS_Y, 0)

        d_down = (EV_REL, REL_X, 100)
        d_up = (EV_REL, REL_X, 0)

        a_down = (EV_REL, REL_X, -100)
        a_up = (EV_REL, REL_X, 0)

        # first change the system mapping because Mapping will validate against it
        system_mapping.clear()
        code_w = 71
        code_d = 74
        code_a = 75
        code_s = 76
        system_mapping._set("w", code_w)
        system_mapping._set("d", code_d)
        system_mapping._set("a", code_a)
        system_mapping._set("s", code_s)

        preset = Preset()
        preset.add(get_key_mapping(EventCombination([*w_down[:2], -10]), "keyboard", "w"))
        preset.add(get_key_mapping(EventCombination([*d_down[:2], 10]), "keyboard", "k(d)"))
        preset.add(get_key_mapping(EventCombination([*s_down[:2], 10]), "keyboard", "s"))
        preset.add(get_key_mapping(EventCombination([*a_down[:2], -10]), "keyboard", "a"))

        def do_stuff():
            if self.injector is not None:
                # discard the previous injector
                self.injector.stop_injecting()
                time.sleep(0.1)
                while uinput_write_history_pipe[0].poll():
                    uinput_write_history_pipe[0].recv()

            push_events(
                "gamepad",
                [
                    new_event(*w_down),
                    new_event(*d_down),
                    new_event(*s_down),
                    new_event(*a_down),
                    new_event(*w_up),
                    new_event(*d_up),
                    new_event(*s_up),
                    new_event(*a_up),
                ],
            )

            self.injector = Injector(groups.find(name="gamepad"), preset)

            # the injector will otherwise skip the device because
            # the capabilities don't contain EV_TYPE
            input = InputDevice("/dev/input/event30")
            self.injector._grab_device = lambda *args: input

            self.injector.start()
            uinput_write_history_pipe[0].poll(timeout=1)
            time.sleep(EVENT_READ_TIMEOUT * 10)
            return read_write_history_pipe()

        """no"""

        history = do_stuff()
        self.assertEqual(history.count((EV_KEY, code_w, 1)), 1)
        self.assertEqual(history.count((EV_KEY, code_d, 1)), 1)
        self.assertEqual(history.count((EV_KEY, code_a, 1)), 1)
        self.assertEqual(history.count((EV_KEY, code_s, 1)), 1)
        self.assertEqual(history.count((EV_KEY, code_w, 0)), 1)
        self.assertEqual(history.count((EV_KEY, code_d, 0)), 1)
        self.assertEqual(history.count((EV_KEY, code_a, 0)), 1)
        self.assertEqual(history.count((EV_KEY, code_s, 0)), 1)

    def test_rel_to_btn(self):
        # todo move to somewhere more sensible
        # buttons mapped rel axis are automatically released if no new rel event arrives

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

        preset = Preset()
        preset.add(get_key_mapping(EventCombination(hw_right), "keyboard", "k(b)"))
        preset.add(get_key_mapping(EventCombination(w_up), "keyboard", "c"))

        group_key = "Foo Device 2"
        push_events(
            group_key,
            [new_event(*w_up)] * 10
            + [new_event(*hw_right), new_event(*w_up)] * 5
            + [new_event(*hw_left)],
        )

        group = groups.find(key=group_key)
        self.injector = Injector(group, preset)

        device = InputDevice("/dev/input/event11")
        # make sure this test uses a device that has the needed capabilities
        # for the injector to grab it
        self.assertIn(EV_REL, device.capabilities())
        self.assertIn(REL_WHEEL, device.capabilities()[EV_REL])
        self.assertIn(REL_HWHEEL, device.capabilities()[EV_REL])
        self.assertIn(device.path, group.paths)

        self.injector.start()

        # wait for the first injected key down event
        uinput_write_history_pipe[0].poll(timeout=1)
        self.assertTrue(uinput_write_history_pipe[0].poll())
        event = uinput_write_history_pipe[0].recv()
        self.assertEqual(event.t, (EV_KEY, code_c, 1))

        # in 5 more read-loop ticks, nothing new should have happened.
        # add a bit of a head-start of one EVENT_READ_TIMEOUT to avoid race-conditions
        # in tests
        self.assertFalse(
            uinput_write_history_pipe[0].poll(timeout=EVENT_READ_TIMEOUT * 6)
        )

        # 5 more and it should be within the second phase in which
        # the horizontal wheel is used. add some tolerance
        self.assertAlmostEqual(
            wait_for_uinput_write(), EVENT_READ_TIMEOUT * 5, delta=EVENT_READ_TIMEOUT
        )
        event = uinput_write_history_pipe[0].recv()
        self.assertEqual(event.t, (EV_KEY, code_b, 1))

        time.sleep(EVENT_READ_TIMEOUT * 10 + 5 / 60)
        # after 21 read-loop ticks all events should be consumed, wait for
        # at least 3 (lets use 5 so that the test passes even if it lags)
        # ticks so that the debouncers are triggered.
        # Key-up events for both wheel events should be written now that no
        # new key-down event arrived.
        events = read_write_history_pipe()
        self.assertEqual(events.count((EV_KEY, code_b, 0)), 1)
        self.assertEqual(events.count((EV_KEY, code_c, 0)), 1)
        self.assertEqual(events.count(hw_left), 1)  # the unmapped wheel

        # the unmapped wheel won't get a debounced release command, it's
        # forwarded as is
        self.assertNotIn((EV_REL, REL_HWHEEL, 0), events)

        self.assertEqual(len(events), 3)

    def test_is_in_capabilities(self):
        key = EventCombination([1, 2, 1])
        capabilities = {1: [9, 2, 5]}
        self.assertTrue(is_in_capabilities(key, capabilities))

        key = EventCombination((1, 2, 1), (1, 3, 1))
        capabilities = {1: [9, 2, 5]}
        # only one of the codes of the combination is required.
        # The goal is to make combinations= across those sub-devices possible,
        # that make up one hardware device
        self.assertTrue(is_in_capabilities(key, capabilities))

        key = EventCombination((1, 2, 1), (1, 5, 1))
        capabilities = {1: [9, 2, 5]}
        self.assertTrue(is_in_capabilities(key, capabilities))


class TestModifyCapabilities(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        quick_cleanup()

    def setUp(self):
        class FakeDevice:
            def __init__(self):
                self._capabilities = {
                    evdev.ecodes.EV_SYN: [1, 2, 3],
                    evdev.ecodes.EV_FF: [1, 2, 3],
                    EV_ABS: [
                        (
                            1,
                            evdev.AbsInfo(
                                value=None,
                                min=None,
                                max=1234,
                                fuzz=None,
                                flat=None,
                                resolution=None,
                            ),
                        ),
                        (
                            2,
                            evdev.AbsInfo(
                                value=None,
                                min=50,
                                max=2345,
                                fuzz=None,
                                flat=None,
                                resolution=None,
                            ),
                        ),
                        3,
                    ],
                }

            def capabilities(self, absinfo=False):
                assert absinfo is True
                return self._capabilities

        preset = Preset()
        preset.add(get_key_mapping(EventCombination([EV_KEY, 80, 1]), "keyboard", "a"))
        preset.add(get_key_mapping(EventCombination([EV_KEY, 81, 1]), "keyboard", DISABLE_NAME))

        macro_code = "r(2, m(sHiFt_l, r(2, k(1).k(2))))"
        macro = parse(macro_code, preset)

        preset.add(get_key_mapping(EventCombination([EV_KEY, 60, 111]), "keyboard", macro_code))

        # going to be ignored, because EV_REL cannot be mapped, that's
        # mouse movements.
        preset.add(get_key_mapping(EventCombination([EV_REL, 1234, 3]), "keyboard", "b"))

        self.a = system_mapping.get("a")
        self.shift_l = system_mapping.get("ShIfT_L")
        self.one = system_mapping.get(1)
        self.two = system_mapping.get("2")
        self.left = system_mapping.get("BtN_lEfT")
        self.fake_device = FakeDevice()
        self.preset = preset
        self.macro = macro

    def check_keys(self, capabilities):
        """No matter the configuration, EV_KEY will be mapped to EV_KEY."""
        self.assertIn(EV_KEY, capabilities)
        keys = capabilities[EV_KEY]
        self.assertIn(self.a, keys)
        self.assertIn(self.one, keys)
        self.assertIn(self.two, keys)
        self.assertIn(self.shift_l, keys)
        self.assertNotIn(DISABLE_CODE, keys)

    def tearDown(self):
        quick_cleanup()

    def test_copy_capabilities(self):
        self.preset.add(
            get_key_mapping(EventCombination([EV_KEY, 60, 1]), "keyboard", self.macro.code)
        )

        # I don't know what ABS_VOLUME is, for now I would like to just always
        # remove it until somebody complains, since its presence broke stuff
        self.injector = Injector(None, self.preset)
        self.fake_device._capabilities = {
            EV_ABS: [ABS_VOLUME, (ABS_X, evdev.AbsInfo(0, 0, 500, 0, 0, 0))],
            EV_KEY: [1, 2, 3],
            EV_REL: [11, 12, 13],
            evdev.ecodes.EV_SYN: [1],
            evdev.ecodes.EV_FF: [2],
        }

        capabilities = self.injector._copy_capabilities(self.fake_device)
        self.assertNotIn(ABS_VOLUME, capabilities[EV_ABS])
        self.assertNotIn(evdev.ecodes.EV_SYN, capabilities)
        self.assertNotIn(evdev.ecodes.EV_FF, capabilities)
        self.assertListEqual(capabilities[EV_KEY], [1, 2, 3])
        self.assertListEqual(capabilities[EV_REL], [11, 12, 13])
        self.assertEqual(capabilities[EV_ABS][0][1].max, 500)


if __name__ == "__main__":
    unittest.main()
