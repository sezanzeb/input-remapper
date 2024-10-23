#!/usr/bin/python3
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

from __future__ import annotations

import dataclasses
import json
import time
from hashlib import md5
from typing import Dict, Optional

import evdev

from inputremapper.configs.input_config import InputCombination
from inputremapper.configs.mapping import Mapping
from inputremapper.configs.paths import PathUtils
from inputremapper.configs.preset import Preset
from tests.lib.logger import logger

# input-remapper is only interested in devices that have EV_KEY, add some
# random other stuff to test that they are ignored.
phys_foo = "usb-0000:03:00.0-1/input2"
info_foo = evdev.device.DeviceInfo(1, 1, 1, 1)

keyboard_keys = sorted(evdev.ecodes.keys.keys())[:255]


@dataclasses.dataclass(frozen=True)
class Fixture:
    path: str
    capabilities: Dict = dataclasses.field(default_factory=dict)
    name: str = "unset"
    info: evdev.device.DeviceInfo = evdev.device.DeviceInfo(None, None, None, None)
    phys: str = "unset"
    group_key: Optional[str] = None

    # uniq is typically empty
    uniq: str = ""

    def __hash__(self):
        return hash(self.path)

    def get_device_hash(self):
        s = str(self.capabilities) + self.name
        device_hash = md5(s.encode()).hexdigest()
        logger.info(
            'Hash for fixture "%s" "%s": "%s"',
            self.path,
            self.name,
            device_hash,
        )
        return device_hash


class _Fixtures:
    """contains all predefined Fixtures.
    Can be extended with new Fixtures during runtime"""

    dev_input_event1 = Fixture(
        capabilities={
            evdev.ecodes.EV_KEY: [evdev.ecodes.KEY_A],
        },
        phys="usb-0000:03:00.0-0/input1",
        info=info_foo,
        name="Foo Device",
        path="/dev/input/event1",
    )
    # Another "Foo Device", which will get an incremented key.
    # If possible write tests using this one, because name != key here and
    # that would be important to test as well. Otherwise, the tests can't
    # see if the groups correct attribute is used in functions and paths.
    dev_input_event11 = Fixture(
        capabilities={
            evdev.ecodes.EV_KEY: [
                evdev.ecodes.BTN_LEFT,
                evdev.ecodes.BTN_TOOL_DOUBLETAP,
            ],
            evdev.ecodes.EV_REL: [
                evdev.ecodes.REL_X,
                evdev.ecodes.REL_Y,
                evdev.ecodes.REL_WHEEL,
                evdev.ecodes.REL_HWHEEL,
            ],
        },
        phys=f"{phys_foo}/input2",
        info=info_foo,
        name="Foo Device foo",
        group_key="Foo Device 2",  # expected key
        path="/dev/input/event11",
    )
    dev_input_event10 = Fixture(
        capabilities={evdev.ecodes.EV_KEY: keyboard_keys},
        phys=f"{phys_foo}/input3",
        info=info_foo,
        name="Foo Device",
        group_key="Foo Device 2",
        path="/dev/input/event10",
    )
    dev_input_event13 = Fixture(
        capabilities={evdev.ecodes.EV_KEY: [], evdev.ecodes.EV_SYN: []},
        phys=f"{phys_foo}/input1",
        info=info_foo,
        name="Foo Device",
        group_key="Foo Device 2",
        path="/dev/input/event13",
    )
    dev_input_event14 = Fixture(
        capabilities={evdev.ecodes.EV_SYN: []},
        phys=f"{phys_foo}/input0",
        info=info_foo,
        name="Foo Device qux",
        group_key="Foo Device 2",
        path="/dev/input/event14",
    )
    dev_input_event15 = Fixture(
        capabilities={
            evdev.ecodes.EV_SYN: [],
            evdev.ecodes.EV_ABS: [
                evdev.ecodes.ABS_X,
                evdev.ecodes.ABS_Y,
                evdev.ecodes.ABS_RX,
                evdev.ecodes.ABS_RY,
                evdev.ecodes.ABS_Z,
                evdev.ecodes.ABS_RZ,
                evdev.ecodes.ABS_HAT0X,
                evdev.ecodes.ABS_HAT0Y,
            ],
            evdev.ecodes.EV_KEY: [evdev.ecodes.BTN_A],
        },
        phys=f"{phys_foo}/input4",
        info=info_foo,
        name="Foo Device bar",
        group_key="Foo Device 2",
        path="/dev/input/event15",
    )
    # Bar Device
    dev_input_event20 = Fixture(
        capabilities={evdev.ecodes.EV_KEY: keyboard_keys},
        phys="usb-0000:03:00.0-2/input1",
        info=evdev.device.DeviceInfo(2, 1, 2, 1),
        name="Bar Device",
        path="/dev/input/event20",
    )
    dev_input_event30 = Fixture(
        capabilities={
            evdev.ecodes.EV_SYN: [],
            evdev.ecodes.EV_ABS: [
                evdev.ecodes.ABS_X,
                evdev.ecodes.ABS_Y,
                evdev.ecodes.ABS_RX,
                evdev.ecodes.ABS_RY,
                evdev.ecodes.ABS_Z,
                evdev.ecodes.ABS_RZ,
                evdev.ecodes.ABS_HAT0X,
                evdev.ecodes.ABS_HAT0Y,
            ],
            evdev.ecodes.EV_KEY: [
                evdev.ecodes.BTN_A,
                evdev.ecodes.BTN_B,
                evdev.ecodes.BTN_X,
                evdev.ecodes.BTN_Y,
            ],
        },
        phys="",  # this is empty sometimes
        info=evdev.device.DeviceInfo(3, 1, 3, 1),
        name="gamepad",
        path="/dev/input/event30",
    )
    # device that is completely ignored
    dev_input_event31 = Fixture(
        capabilities={evdev.ecodes.EV_SYN: []},
        phys="usb-0000:03:00.0-4/input1",
        info=evdev.device.DeviceInfo(4, 1, 4, 1),
        name="Power Button",
        path="/dev/input/event31",
    )
    # input-remapper devices are not displayed in the ui, some instance
    # of input-remapper started injecting, apparently.
    dev_input_event40 = Fixture(
        capabilities={evdev.ecodes.EV_KEY: keyboard_keys},
        phys="input-remapper/input1",
        info=evdev.device.DeviceInfo(5, 1, 5, 1),
        name="input-remapper Bar Device",
        path="/dev/input/event40",
    )
    # denylisted
    dev_input_event51 = Fixture(
        capabilities={evdev.ecodes.EV_KEY: keyboard_keys},
        phys="usb-0000:03:00.0-5/input1",
        info=evdev.device.DeviceInfo(6, 1, 6, 1),
        name="YuBiCofooYuBiKeYbar",
        path="/dev/input/event51",
    )
    # name requires sanitation
    dev_input_event52 = Fixture(
        capabilities={evdev.ecodes.EV_KEY: keyboard_keys},
        phys="usb-0000:03:00.0-3/input1",
        info=evdev.device.DeviceInfo(2, 1, 2, 1),
        name="Qux/[Device]?",
        path="/dev/input/event52",
    )

    def __init__(self):
        self._iter = [
            self.dev_input_event1,
            self.dev_input_event11,
            self.dev_input_event10,
            self.dev_input_event13,
            self.dev_input_event14,
            self.dev_input_event15,
            self.dev_input_event20,
            self.dev_input_event30,
            self.dev_input_event31,
            self.dev_input_event40,
            self.dev_input_event51,
            self.dev_input_event52,
        ]
        self._dynamic_fixtures = {}

    def __getitem__(self, path: str) -> Fixture:
        """get a Fixture by it's unique /dev/input/eventX path"""
        if fixture := self._dynamic_fixtures.get(path):
            return fixture
        path = self._path_to_attribute(path)

        try:
            return getattr(self, path)
        except AttributeError as e:
            raise KeyError(str(e))

    def __setitem__(self, key: str, value: [Fixture | dict]):
        if isinstance(value, Fixture):
            self._dynamic_fixtures[key] = value
        elif isinstance(value, dict):
            self._dynamic_fixtures[key] = Fixture(path=key, **value)

    def __iter__(self):
        return iter([*self._iter, *self._dynamic_fixtures.values()])

    def get_paths(self):
        """Get a list of all available device paths."""
        return list(self._dynamic_fixtures.keys())

    def reset(self):
        self._dynamic_fixtures = {}

    @staticmethod
    def _path_to_attribute(path) -> str:
        if path.startswith("/"):
            path = path[1:]
        if "/" in path:
            path = path.replace("/", "_")
        return path

    def get(self, item) -> Optional[Fixture]:
        try:
            return self[item]
        except KeyError:
            return None

    @property
    def foo_device_1_1(self):
        return self["/dev/input/event1"]

    @property
    def foo_device_2_mouse(self):
        return self["/dev/input/event11"]

    @property
    def foo_device_2_keyboard(self):
        return self["/dev/input/event10"]

    @property
    def foo_device_2_13(self):
        return self["/dev/input/event13"]

    @property
    def foo_device_2_qux(self):
        return self["/dev/input/event14"]

    @property
    def foo_device_2_gamepad(self):
        return self["/dev/input/event15"]

    @property
    def bar_device(self):
        return self["/dev/input/event20"]

    @property
    def gamepad(self):
        return self["/dev/input/event30"]

    @property
    def power_button(self):
        return self["/dev/input/event31"]

    @property
    def input_remapper_bar_device(self):
        return self["/dev/input/event40"]

    @property
    def YuBiCofooYuBiKeYbar(self):
        return self["/dev/input/event51"]

    @property
    def QuxSlashDeviceQuestionmark(self):
        return self["/dev/input/event52"]


fixtures = _Fixtures()


def new_event(type, code, value, timestamp):
    """Create a new InputEvent.

    Handy because of the annoying sec and usec arguments of the regular
    evdev.InputEvent constructor.

    Prefer using `InputEvent.key()`, `InputEvent.abs()`, `InputEvent.rel()` or just
    `InputEvent(0, 0, 1234, 2345, 3456)`.
    """
    from inputremapper.input_event import InputEvent

    if timestamp is None:
        timestamp = time.time()

    sec = int(timestamp)
    usec = timestamp % 1 * 1000000
    event = InputEvent(sec, usec, type, code, value)
    return event


def prepare_presets():
    """prepare a few presets for use in tests
    "Foo Device 2/preset3" is the newest and "Foo Device 2/preset2" is set to autoload
    """
    preset1 = Preset(PathUtils.get_preset_path("Foo Device", "preset1"))
    preset1.add(
        Mapping.from_combination(
            InputCombination.from_tuples((1, 1)),
            output_symbol="b",
        )
    )
    preset1.add(Mapping.from_combination(InputCombination.from_tuples((1, 2))))
    preset1.save()

    time.sleep(0.1)
    preset2 = Preset(PathUtils.get_preset_path("Foo Device", "preset2"))
    preset2.add(Mapping.from_combination(InputCombination.from_tuples((1, 3))))
    preset2.add(Mapping.from_combination(InputCombination.from_tuples((1, 4))))
    preset2.save()

    # make sure the timestamp of preset 3 is the newest,
    # so that it will be automatically loaded by the GUI
    time.sleep(0.1)
    preset3 = Preset(PathUtils.get_preset_path("Foo Device", "preset3"))
    preset3.add(Mapping.from_combination(InputCombination.from_tuples((1, 5))))
    preset3.save()

    with open(PathUtils.get_config_path("config.json"), "w") as file:
        json.dump({"autoload": {"Foo Device 2": "preset2"}}, file, indent=4)

    return preset1, preset2, preset3
