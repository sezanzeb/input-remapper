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

from tests.test import (
    new_event,
    push_events,
    fixtures,
    EVENT_READ_TIMEOUT,
    uinput_write_history_pipe,
    quick_cleanup,
    read_write_history_pipe,
    uinputs,
    keyboard_keys,
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
    REL_HWHEEL,
    BTN_A,
    ABS_X,
    ABS_VOLUME,
)

from inputremapper.injection.injector import (
    Injector,
    is_in_capabilities,
    STARTING,
    RUNNING,
    STOPPED,
    NO_GRAB,
    UNKNOWN,
    get_udev_name, FAILED,
)
from inputremapper.injection.numlock import is_numlock_on
from inputremapper.configs.system_mapping import (
    system_mapping,
    DISABLE_CODE,
    DISABLE_NAME,
)
from inputremapper.configs.preset import Preset
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
        if self.injector is not None and self.injector.is_alive():
            self.injector.stop_injecting()
            time.sleep(0.2)
            self.assertIn(self.injector.get_state(), (STOPPED, FAILED, NO_GRAB))
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
        preset.add(
            get_key_mapping(EventCombination([EV_ABS, ABS_HAT0X, 1]), "keyboard", "a"),
        )
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

        preset.add(
            get_key_mapping(EventCombination([EV_KEY, BTN_A, 1]), "keyboard", "a"),
        )
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

    def test_get_udev_name(self):
        self.injector = Injector(groups.find(key="Foo Device 2"), Preset())
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
        m2 = get_key_mapping(
            EventCombination([EV_REL, REL_HWHEEL, 1]),
            "keyboard",
            "key(b)",
        )
        preset.add(m1)
        preset.add(m2)
        self.injector = Injector(groups.find(key="Foo Device 2"), preset)
        self.injector.stop_injecting()
        self.injector.run()

        self.assertEqual(
            self.injector.preset.get_mapping(EventCombination([EV_KEY, KEY_A, 1])),
            m1,
        )
        self.assertEqual(
            self.injector.preset.get_mapping(EventCombination([EV_REL, REL_HWHEEL, 1])),
            m2,
        )

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
        preset.add(
            get_key_mapping(
                EventCombination(((EV_KEY, 8, 1), (EV_KEY, 9, 1))),
                "keyboard",
                "k(KEY_Q).k(w)",
            )
        )
        preset.add(
            get_key_mapping(
                EventCombination([EV_ABS, ABS_HAT0X, -1]),
                "keyboard",
                "a",
            )
        )
        # one mapping that is unknown in the system_mapping on purpose
        input_b = 10
        with self.assertRaises(ValidationError):
            preset.add(
                get_key_mapping(
                    EventCombination([EV_KEY, input_b, 1]),
                    "keyboard",
                    "b",
                )
            )

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

    def test_is_in_capabilities(self):
        key = EventCombination((1, 2, 1))
        capabilities = {1: [9, 2, 5]}
        self.assertTrue(is_in_capabilities(key, capabilities))

        key = EventCombination(((1, 2, 1), (1, 3, 1)))
        capabilities = {1: [9, 2, 5]}
        # only one of the codes of the combination is required.
        # The goal is to make combinations= across those sub-devices possible,
        # that make up one hardware device
        self.assertTrue(is_in_capabilities(key, capabilities))

        key = EventCombination(((1, 2, 1), (1, 5, 1)))
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
        preset.add(
            get_key_mapping(
                EventCombination([EV_KEY, 81, 1]),
                "keyboard",
                DISABLE_NAME,
            ),
        )

        macro_code = "r(2, m(sHiFt_l, r(2, k(1).k(2))))"
        macro = parse(macro_code, preset)

        preset.add(
            get_key_mapping(
                EventCombination([EV_KEY, 60, 111]), "keyboard", macro_code
            ),
        )

        # going to be ignored, because EV_REL cannot be mapped, that's
        # mouse movements.
        preset.add(
            get_key_mapping(EventCombination([EV_REL, 1234, 3]), "keyboard", "b"),
        )

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
            get_key_mapping(
                EventCombination([EV_KEY, 60, 1]),
                "keyboard",
                self.macro.code,
            )
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
