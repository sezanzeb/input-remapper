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

import json
import os
import unittest

import evdev
from evdev.ecodes import EV_KEY, KEY_A

from inputremapper.configs.paths import PathUtils
from inputremapper.groups import (
    _FindGroups,
    groups,
    classify,
    DeviceType,
    Group,
)
from tests.lib.fixtures import fixtures, keyboard_keys
from tests.lib.test_setup import test_setup


class FakePipe:
    groups = None

    def send(self, groups):
        self.groups = groups


@test_setup
class TestGroups(unittest.TestCase):
    def test_group(self):
        group = Group(
            paths=["/dev/a", "/dev/b", "/dev/c"],
            names=["name_bar", "name_a", "name_foo"],
            types=[DeviceType.MOUSE, DeviceType.KEYBOARD, DeviceType.UNKNOWN],
            key="key",
        )
        self.assertEqual(group.name, "name_a")
        self.assertEqual(group.key, "key")
        self.assertEqual(
            group.get_preset_path("preset1234"),
            os.path.join(
                PathUtils.config_path(),
                "presets",
                group.name,
                "preset1234.json",
            ),
        )

    def test_find_groups(self):
        pipe = FakePipe()
        _FindGroups(pipe).run()
        self.assertIsInstance(pipe.groups, str)

        groups.loads(pipe.groups)
        self.maxDiff = None
        self.assertEqual(
            groups.dumps(),
            json.dumps(
                [
                    json.dumps(
                        {
                            "paths": [
                                "/dev/input/event1",
                            ],
                            "names": ["Foo Device"],
                            "types": [DeviceType.KEYBOARD],
                            "key": "Foo Device",
                        }
                    ),
                    json.dumps(
                        {
                            "paths": [
                                "/dev/input/event11",
                                "/dev/input/event10",
                                "/dev/input/event13",
                                "/dev/input/event15",
                            ],
                            "names": [
                                "Foo Device foo",
                                "Foo Device",
                                "Foo Device",
                                "Foo Device bar",
                            ],
                            "types": [
                                DeviceType.GAMEPAD,
                                DeviceType.KEYBOARD,
                                DeviceType.MOUSE,
                            ],
                            "key": "Foo Device 2",
                        }
                    ),
                    json.dumps(
                        {
                            "paths": ["/dev/input/event20"],
                            "names": ["Bar Device"],
                            "types": [DeviceType.KEYBOARD],
                            "key": "Bar Device",
                        }
                    ),
                    json.dumps(
                        {
                            "paths": ["/dev/input/event30"],
                            "names": ["gamepad"],
                            "types": [DeviceType.GAMEPAD],
                            "key": "gamepad",
                        }
                    ),
                    json.dumps(
                        {
                            "paths": ["/dev/input/event40"],
                            "names": ["input-remapper Bar Device"],
                            "types": [DeviceType.KEYBOARD],
                            "key": "input-remapper Bar Device",
                        }
                    ),
                    json.dumps(
                        {
                            "paths": ["/dev/input/event52"],
                            "names": ["Qux/[Device]?"],
                            "types": [DeviceType.KEYBOARD],
                            "key": "Qux/[Device]?",
                        }
                    ),
                ]
            ),
        )

        groups2 = json.dumps(
            [group.dumps() for group in groups.filter(include_inputremapper=True)]
        )
        self.assertEqual(pipe.groups, groups2)

    def test_list_group_names(self):
        self.assertListEqual(
            groups.list_group_names(),
            [
                "Foo Device",
                "Foo Device",
                "Bar Device",
                "gamepad",
                "Qux/[Device]?",
            ],
        )

    def test_filter(self):
        # by default no input-remapper devices are present
        filtered = groups.filter()
        keys = [group.key for group in filtered]
        self.assertIn("Foo Device 2", keys)
        self.assertNotIn("input-remapper Bar Device", keys)

    def test_skip_camera(self):
        fixtures["/foo/bar"] = {
            "name": "camera",
            "phys": "abcd1",
            "info": evdev.DeviceInfo(1, 2, 3, 4),
            "capabilities": {evdev.ecodes.EV_KEY: [evdev.ecodes.KEY_CAMERA]},
        }

        groups.refresh()
        self.assertIsNone(groups.find(name="camera"))
        self.assertIsNotNone(groups.find(name="gamepad"))

    def test_device_with_only_ev_abs(self):
        # As Input Mapper can now map axes to buttons,
        # a single EV_ABS device is valid for mapping.
        fixtures["/foo/bar"] = {
            "name": "qux",
            "phys": "abcd2",
            "info": evdev.DeviceInfo(1, 2, 3, 4),
            "capabilities": {evdev.ecodes.EV_ABS: [evdev.ecodes.ABS_X]},
        }

        groups.refresh()
        self.assertIsNotNone(groups.find(name="gamepad"))
        self.assertIsNotNone(groups.find(name="qux"))

    def test_device_with_no_capabilities(self):
        fixtures["/foo/bar"] = {
            "name": "nulcap",
            "phys": "abcd3",
            "info": evdev.DeviceInfo(1, 2, 3, 4),
            "capabilities": {},
        }

        groups.refresh()
        self.assertIsNotNone(groups.find(name="gamepad"))
        self.assertIsNone(groups.find(name="nulcap"))

    def test_duplicate_device(self):
        fixtures["/dev/input/event100"] = {
            "capabilities": {evdev.ecodes.EV_KEY: keyboard_keys},
            "phys": "usb-0000:03:00.0-3/input1",
            "info": evdev.device.DeviceInfo(2, 1, 2, 1),
            "name": "Foo Device",
        }
        groups.refresh()

        group1 = groups.find(key="Foo Device")
        group2 = groups.find(key="Foo Device 2")
        group3 = groups.find(key="Foo Device 3")

        self.assertIn("/dev/input/event1", group1.paths)
        self.assertIn("/dev/input/event10", group2.paths)
        self.assertIn("/dev/input/event100", group3.paths)

        self.assertEqual(group1.key, "Foo Device")
        self.assertEqual(group2.key, "Foo Device 2")
        self.assertEqual(group3.key, "Foo Device 3")

        self.assertEqual(group1.name, "Foo Device")
        self.assertEqual(group2.name, "Foo Device")
        self.assertEqual(group3.name, "Foo Device")

    def test_classify(self):
        # properly detects if the device is a gamepad
        EV_ABS = evdev.ecodes.EV_ABS
        EV_KEY = evdev.ecodes.EV_KEY
        EV_REL = evdev.ecodes.EV_REL

        class FakeDevice:
            def __init__(self, capabilities):
                self.c = capabilities

            def capabilities(self, absinfo):
                assert not absinfo
                return self.c

        """Gamepads"""

        self.assertEqual(
            classify(
                FakeDevice(
                    {
                        EV_ABS: [evdev.ecodes.ABS_X, evdev.ecodes.ABS_Y],
                        EV_KEY: [evdev.ecodes.BTN_A],
                    }
                )
            ),
            DeviceType.GAMEPAD,
        )

        """Mice"""

        self.assertEqual(
            classify(
                FakeDevice(
                    {
                        EV_REL: [
                            evdev.ecodes.REL_X,
                            evdev.ecodes.REL_Y,
                            evdev.ecodes.REL_WHEEL,
                        ],
                        EV_KEY: [evdev.ecodes.BTN_LEFT],
                    }
                )
            ),
            DeviceType.MOUSE,
        )

        """Keyboard"""

        self.assertEqual(
            classify(FakeDevice({EV_KEY: [evdev.ecodes.KEY_A]})), DeviceType.KEYBOARD
        )

        """Touchpads"""

        self.assertEqual(
            classify(
                FakeDevice(
                    {
                        EV_KEY: [evdev.ecodes.KEY_A],
                        EV_ABS: [evdev.ecodes.ABS_MT_POSITION_X],
                    }
                )
            ),
            DeviceType.TOUCHPAD,
        )

        """Graphics tablets"""

        self.assertEqual(
            classify(
                FakeDevice(
                    {
                        EV_ABS: [evdev.ecodes.ABS_X, evdev.ecodes.ABS_Y],
                        EV_KEY: [evdev.ecodes.BTN_STYLUS],
                    }
                )
            ),
            DeviceType.GRAPHICS_TABLET,
        )

        """Weird combos"""

        self.assertEqual(
            classify(
                FakeDevice(
                    {
                        EV_ABS: [evdev.ecodes.ABS_X, evdev.ecodes.ABS_Y],
                        EV_KEY: [evdev.ecodes.KEY_1],
                    }
                )
            ),
            DeviceType.UNKNOWN,
        )

        self.assertEqual(
            classify(
                FakeDevice({EV_ABS: [evdev.ecodes.ABS_X], EV_KEY: [evdev.ecodes.BTN_A]})
            ),
            DeviceType.UNKNOWN,
        )

        self.assertEqual(
            classify(FakeDevice({EV_KEY: [evdev.ecodes.BTN_A]})), DeviceType.UNKNOWN
        )

        self.assertEqual(
            classify(FakeDevice({EV_ABS: [evdev.ecodes.ABS_X]})), DeviceType.UNKNOWN
        )


if __name__ == "__main__":
    unittest.main()
