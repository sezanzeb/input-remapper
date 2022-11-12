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


"""Sets up inputremapper for the tests and runs them.

This module needs to be imported first in test files.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
import tempfile
import traceback
import warnings
from multiprocessing.connection import Connection
from typing import Dict, Tuple, Optional
import tracemalloc

tracemalloc.start()

# ensure nothing has loaded
if module := sys.modules.get("inputremapper"):
    imported = [m for m in module.__dict__ if not m.startswith("__")]
    raise AssertionError(
        f"the modules {imported} from inputremapper where already imported, this can "
        f"cause issues with the tests. Make sure to always import tests.test before any"
        f" inputremapper module"
    )
try:
    sys.modules.get("tests.test").main
    raise AssertionError(
        "test.py was already imported. "
        "Always use 'from tests.test import ...' "
        "not 'from test import ...' to import this"
    )
    # have fun debugging infinitely blocking tests without this
except AttributeError:
    pass


def get_project_root():
    """Find the projects root, i.e. the uppermost directory of the repo."""
    # when tests are started in pycharm via the green arrow, the working directory
    # is not the project root. Go up until it is found.
    root = os.getcwd()
    for _ in range(10):
        if "setup.py" in os.listdir(root):
            return root

        root = os.path.dirname(root)

    raise Exception("Could not find project root")


# make sure the "tests" module visible
sys.path.append(get_project_root())
if __name__ == "__main__":
    # import this file to itself to make sure is not run twice and all global
    # variables end up in sys.modules
    # https://stackoverflow.com/questions/13181559/importing-modules-main-vs-import-as-module
    import tests.test

    tests.test.main()

import shutil
import time
import copy
import unittest
import subprocess
import multiprocessing
import asyncio
import psutil
import logging
from pickle import UnpicklingError
from unittest.mock import patch

import evdev

from tests.xmodmap import xmodmap

os.environ["UNITTEST"] = "1"

logger = logging.getLogger("input-remapper-test")
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("\033[90mTest: %(message)s\033[0m"))
logger.addHandler(handler)
logger.setLevel(logging.INFO)


def is_service_running():
    """Check if the daemon is running."""
    try:
        subprocess.check_output(["pgrep", "-f", "input-remapper-service"])
        return True
    except subprocess.CalledProcessError:
        return False


def join_children():
    """Wait for child processes to exit. Stop them if it takes too long."""
    this = psutil.Process(os.getpid())

    i = 0
    time.sleep(EVENT_READ_TIMEOUT)
    children = this.children(recursive=True)
    while len([c for c in children if c.status() != "zombie"]) > 0:
        for child in children:
            if i > 10:
                child.kill()
                logger.info("Killed pid %s because it didn't finish in time", child.pid)

        children = this.children(recursive=True)
        time.sleep(EVENT_READ_TIMEOUT)
        i += 1


if is_service_running():
    # let tests control daemon existance
    raise Exception("Expected the service not to be running already.")


# give tests some time to test stuff while the process
# is still running
EVENT_READ_TIMEOUT = 0.01

# based on experience how much time passes at most until
# the reader-service starts receiving previously pushed events after a
# call to start_reading
START_READING_DELAY = 0.05

# for joysticks
MIN_ABS = -(2**15)
MAX_ABS = 2**15

# When it gets garbage collected it cleans up the temporary directory so it needs to
# stay reachable while the tests are ran.
temporary_directory = tempfile.TemporaryDirectory(prefix="input-remapper-test")
tmp = temporary_directory.name

uinput_write_history = []
# for tests that makes the injector create its processes
uinput_write_history_pipe = multiprocessing.Pipe()
pending_events: Dict[Fixture, Tuple[Connection, Connection]] = {}


def read_write_history_pipe():
    """Convert the write history from the pipe to some easier to manage list."""
    history = []
    while uinput_write_history_pipe[0].poll():
        event = uinput_write_history_pipe[0].recv()
        history.append((event.type, event.code, event.value))
    return history


# input-remapper is only interested in devices that have EV_KEY, add some
# random other stuff to test that they are ignored.
phys_foo = "usb-0000:03:00.0-1/input2"
info_foo = evdev.device.DeviceInfo(1, 1, 1, 1)

keyboard_keys = sorted(evdev.ecodes.keys.keys())[:255]


@dataclasses.dataclass(frozen=True)
class Fixture:
    capabilities: Dict = dataclasses.field(default_factory=dict)
    path: str = ""
    name: str = "unset"
    info: evdev.device.DeviceInfo = evdev.device.DeviceInfo(None, None, None, None)
    phys: str = "unset"
    group_key: Optional[str] = None

    def __hash__(self):
        return hash(self.path)


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
    # that would be important to test as well. Otherwise the tests can't
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
    # of input-remapper started injecting apparently.
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
        name="Qux/Device?",
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


def setup_pipe(fixture: Fixture):
    """Create a pipe that can be used to send events to the reader-service,
    which in turn will be sent to the reader-client
    """
    if pending_events.get(fixture) is None:
        pending_events[fixture] = multiprocessing.Pipe()


# make sure those pipes exist before any process (the reader-service) gets forked,
# so that events can be pushed after the fork.
for _fixture in fixtures:
    setup_pipe(_fixture)


def get_events():
    """Get all events written by the injector."""
    return uinput_write_history


def push_event(fixture: Fixture, event, force=False):
    """Make a device act like it is reading events from evdev.

    push_event is like hitting a key on a keyboard for stuff that reads from
    evdev.InputDevice (which is patched in test.py to work that way)

    Parameters
    ----------
    fixture : Fixture
        For example 'Foo Device'
    event : InputEvent
    force : bool don't check if the event is in fixture.capabilities
    """
    setup_pipe(fixture)
    if not force and (
        not fixture.capabilities.get(event.type)
        or event.code not in fixture.capabilities[event.type]
    ):
        raise AssertionError(f"Fixture {fixture.path} cannot send {event}")
    logger.info("Simulating %s for %s", event, fixture.path)
    pending_events[fixture][0].send(event)


def push_events(fixture: Fixture, events, force=False):
    """Push multiple events."""
    for event in events:
        push_event(fixture, event, force)


def new_event(type, code, value, timestamp=None, offset=0):
    """Create a new input_event."""
    if timestamp is None:
        timestamp = time.time() + offset

    sec = int(timestamp)
    usec = timestamp % 1 * 1000000
    event = InputEvent(sec, usec, type, code, value)
    return event


def patch_paths():
    from inputremapper import user

    user.HOME = tmp


class InputDevice:
    # expose as existing attribute, otherwise the patch for
    # evdev < 1.0.0 will crash the test
    path = None

    def __init__(self, path):
        if path != "justdoit" and not fixtures.get(path):
            raise FileNotFoundError()
        if path == "justdoit":
            self._fixture = Fixture()
        else:
            self._fixture = fixtures[path]

        self.path = path
        self.phys = self._fixture.phys
        self.info = self._fixture.info
        self.name = self._fixture.name

        # this property exists only for test purposes and is not part of
        # the original evdev.InputDevice class
        self.group_key = self._fixture.group_key or self._fixture.name

        # ensure a pipe exists to make this object act like
        # it is reading events from a device
        setup_pipe(self._fixture)

        self.fd = pending_events[self._fixture][1].fileno()

    def push_events(self, events):
        push_events(self._fixture, events)

    def fileno(self):
        """Compatibility to select.select."""
        return self.fd

    def log(self, key, msg):
        logger.info(f'%s "%s" "%s" %s', msg, self.name, self.path, key)

    def absinfo(self, *args):
        raise Exception("Ubuntus version of evdev doesn't support .absinfo")

    def grab(self):
        logger.info("grab %s %s", self.name, self.path)

    def ungrab(self):
        logger.info("ungrab %s %s", self.name, self.path)

    async def async_read_loop(self):
        logger.info("starting read loop for %s", self.path)
        new_frame = asyncio.Event()
        asyncio.get_running_loop().add_reader(self.fd, new_frame.set)
        while True:
            await new_frame.wait()
            new_frame.clear()
            if not pending_events[self._fixture][1].poll():
                # todo: why? why do we need this?
                # sometimes this happens, as if a other process calls recv on
                # the pipe
                continue

            event = pending_events[self._fixture][1].recv()
            logger.info("got %s at %s", event, self.path)
            yield event

    def read(self):
        # the patched fake InputDevice objects read anything pending from
        # that group.
        # To be realistic it would have to check if the provided
        # element is in its capabilities.
        if self.group_key not in pending_events:
            self.log("no events to read", self.group_key)
            return

        # consume all of them
        while pending_events[self._fixture][1].poll():
            event = pending_events[self._fixture][1].recv()
            self.log(event, "read")
            yield event
            time.sleep(EVENT_READ_TIMEOUT)

    def read_loop(self):
        """Endless loop that yields events."""
        while True:
            event = pending_events[self._fixture][1].recv()
            if event is not None:
                self.log(event, "read_loop")
                yield event
            time.sleep(EVENT_READ_TIMEOUT)

    def read_one(self):
        """Read one event or none if nothing available."""
        if not pending_events.get(self._fixture):
            return None

        if not pending_events[self._fixture][1].poll():
            return None

        try:
            event = pending_events[self._fixture][1].recv()
        except (UnpicklingError, EOFError):
            # failed in tests sometimes
            return None

        self.log(event, "read_one")
        return event

    def capabilities(self, absinfo=True, verbose=False):
        result = copy.deepcopy(self._fixture.capabilities)

        if absinfo and evdev.ecodes.EV_ABS in result:
            absinfo_obj = evdev.AbsInfo(
                value=None,
                min=MIN_ABS,
                fuzz=None,
                flat=None,
                resolution=None,
                max=MAX_ABS,
            )

            ev_abs = []
            for ev_code in result[evdev.ecodes.EV_ABS]:
                if ev_code in range(0x10, 0x18):  # ABS_HAT0X - ABS_HAT3Y
                    absinfo_obj = evdev.AbsInfo(
                        value=None,
                        min=-1,
                        fuzz=None,
                        flat=None,
                        resolution=None,
                        max=1,
                    )
                ev_abs.append((ev_code, absinfo_obj))

            result[evdev.ecodes.EV_ABS] = ev_abs

        return result

    def input_props(self):
        return []


uinputs = {}


class UInput:
    def __init__(self, events=None, name="unnamed", *args, **kwargs):
        self.fd = 0
        self.write_count = 0
        self.device = InputDevice("justdoit")
        self.name = name
        self.events = events
        self.write_history = []

        global uinputs
        uinputs[name] = self

    def capabilities(self, verbose=False, absinfo=True):
        if absinfo or 3 not in self.events:
            return self.events
        else:
            events = self.events.copy()
            events[3] = [code for code, _ in self.events[3]]
            return events

    def write(self, type, code, value):
        self.write_count += 1
        event = new_event(type, code, value)
        uinput_write_history.append(event)
        uinput_write_history_pipe[1].send(event)
        self.write_history.append(event)
        logger.info("%s written", (type, code, value))

    def syn(self):
        pass


# TODO inherit from input-remappers InputEvent?
#  makes convert_to_internal_events obsolete
class InputEvent(evdev.InputEvent):
    def __init__(self, sec, usec, type, code, value):
        self.t = (type, code, value)
        super().__init__(sec, usec, type, code, value)

    def copy(self):
        return InputEvent(self.sec, self.usec, self.type, self.code, self.value)


def patch_evdev():
    def list_devices():
        return [fixture_.path for fixture_ in fixtures]

    evdev.list_devices = list_devices
    evdev.InputDevice = InputDevice
    evdev.UInput = UInput
    evdev.InputEvent = InputEvent


def patch_events():
    # improve logging of stuff
    evdev.InputEvent.__str__ = lambda self: (
        f"InputEvent{(self.type, self.code, self.value)}"
    )


def patch_os_system():
    """Avoid running pkexec."""
    original_system = os.system

    def system(command):
        if "pkexec" in command:
            # because it
            # - will open a window for user input
            # - has no knowledge of the fixtures and patches
            raise Exception("Write patches to avoid running pkexec stuff")
        return original_system(command)

    os.system = system


def patch_check_output():
    """Xmodmap -pke should always return a fixed set of symbols.

    On some installations the `xmodmap` command might be missig completely,
    which would break the tests.
    """
    original_check_output = subprocess.check_output

    def check_output(command, *args, **kwargs):
        if "xmodmap" in command and "-pke" in command:
            return xmodmap
        return original_check_output(command, *args, **kwargs)

    subprocess.check_output = check_output


def clear_write_history():
    """Empty the history in preparation for the next test."""
    while len(uinput_write_history) > 0:
        uinput_write_history.pop()
    while uinput_write_history_pipe[0].poll():
        uinput_write_history_pipe[0].recv()


def warn_with_traceback(message, category, filename, lineno, file=None, line=None):

    log = file if hasattr(file, "write") else sys.stderr
    traceback.print_stack(file=log)
    log.write(warnings.formatwarning(message, category, filename, lineno, line))


def patch_warnings():
    # show traceback
    warnings.showwarning = warn_with_traceback
    warnings.simplefilter("always")


# quickly fake some stuff before any other file gets a chance to import
# the original versions
patch_paths()
patch_evdev()
patch_events()
patch_os_system()
patch_check_output()
# patch_warnings()

from inputremapper.logger import update_verbosity

update_verbosity(True)

from inputremapper.daemon import DaemonProxy
from inputremapper.input_event import InputEvent as InternalInputEvent
from inputremapper.injection.injector import Injector, InjectorState
from inputremapper.injection.macros.macro import macro_variables
from inputremapper.injection.global_uinputs import GlobalUInputs
from inputremapper.configs.global_config import global_config
from inputremapper.configs.mapping import Mapping, UIMapping
from inputremapper.groups import groups, _Groups
from inputremapper.configs.system_mapping import system_mapping
from inputremapper.gui.messages.message_broker import MessageBroker
from inputremapper.gui.reader_client import ReaderClient
from inputremapper.gui.reader_service import ReaderService
from inputremapper.configs.paths import get_config_path, get_preset_path
from inputremapper.configs.preset import Preset

from inputremapper.injection.global_uinputs import global_uinputs

# no need for a high number in tests
Injector.regrab_timeout = 0.05


environ_copy = copy.deepcopy(os.environ)


def is_running_patch():
    logger.info("is_running is patched to always return True")
    return True


setattr(ReaderService, "is_running", is_running_patch)


def convert_to_internal_events(events):
    """Convert an iterable of InputEvent to a list of inputremapper.InputEvent."""
    return [InternalInputEvent.from_event(event) for event in events]


def get_key_mapping(
    combination="99,99,99", target_uinput="keyboard", output_symbol="a"
) -> Mapping:
    """Convenient function to get a valid mapping."""
    return Mapping(
        event_combination=combination,
        target_uinput=target_uinput,
        output_symbol=output_symbol,
    )


def get_ui_mapping(
    combination="99,99,99", target_uinput="keyboard", output_symbol="a"
) -> UIMapping:
    """Convenient function to get a valid mapping."""
    return UIMapping(
        event_combination=combination,
        target_uinput=target_uinput,
        output_symbol=output_symbol,
    )


def quick_cleanup(log=True):
    """Reset the applications state."""
    if log:
        print("Quick cleanup...")

    for device in list(pending_events.keys()):
        try:
            while pending_events[device][1].poll():
                pending_events[device][1].recv()
        except (UnpicklingError, EOFError):
            pass

        # setup new pipes for the next test
        pending_events[device][1].close()
        pending_events[device][0].close()
        del pending_events[device]
        setup_pipe(device)

    try:
        if asyncio.get_event_loop().is_running():
            for task in asyncio.all_tasks():
                task.cancel()
    except RuntimeError:
        # happens when the event loop disappears for magical reasons
        # create a fresh event loop
        asyncio.set_event_loop(asyncio.new_event_loop())

    if macro_variables.process is not None and not macro_variables.process.is_alive():
        # nothing should stop the process during runtime, if it has been started by
        # the injector once
        raise AssertionError("the SharedDict manager is not running anymore")

    if macro_variables.process is not None:
        macro_variables._stop()

    join_children()

    macro_variables.start()

    if os.path.exists(tmp):
        shutil.rmtree(tmp)

    global_config.path = os.path.join(get_config_path(), "config.json")
    global_config.clear_config()
    global_config._save_config()

    system_mapping.populate()

    clear_write_history()

    for name in list(uinputs.keys()):
        del uinputs[name]

    # for device in list(active_macros.keys()):
    #    del active_macros[device]
    # for device in list(unreleased.keys()):
    #    del unreleased[device]
    fixtures.reset()
    os.environ.update(environ_copy)
    for device in list(os.environ.keys()):
        if device not in environ_copy:
            del os.environ[device]

    for _, pipe in pending_events.values():
        assert not pipe.poll()

    assert macro_variables.is_alive(1)
    for uinput in global_uinputs.devices.values():
        uinput.write_count = 0
        uinput.write_history = []

    global_uinputs.is_service = True

    if log:
        print("Quick cleanup done")


def cleanup():
    """Reset the applications state.

    Using this is slower, usually quick_cleanup() is sufficient.
    """
    print("Cleanup...")

    os.system("pkill -f input-remapper-service")
    os.system("pkill -f input-remapper-control")
    time.sleep(0.05)

    quick_cleanup(log=False)
    groups.refresh()
    with patch.object(sys, "argv", ["input-remapper-service"]):
        global_uinputs.prepare_all()

    print("Cleanup done")


def spy(obj, name):
    """Convenient wrapper for patch.object(..., ..., wraps=...)."""
    return patch.object(obj, name, wraps=obj.__getattribute__(name))


class FakeDaemonProxy:
    def __init__(self):
        self.calls = {
            "stop_injecting": [],
            "get_state": [],
            "start_injecting": [],
            "stop_all": 0,
            "set_config_dir": [],
            "autoload": 0,
            "autoload_single": [],
            "hello": [],
        }

    def stop_injecting(self, group_key: str) -> None:
        self.calls["stop_injecting"].append(group_key)

    def get_state(self, group_key: str) -> InjectorState:
        self.calls["get_state"].append(group_key)
        return InjectorState.STOPPED

    def start_injecting(self, group_key: str, preset: str) -> bool:
        self.calls["start_injecting"].append((group_key, preset))
        return True

    def stop_all(self) -> None:
        self.calls["stop_all"] += 1

    def set_config_dir(self, config_dir: str) -> None:
        self.calls["set_config_dir"].append(config_dir)

    def autoload(self) -> None:
        self.calls["autoload"] += 1

    def autoload_single(self, group_key: str) -> None:
        self.calls["autoload_single"].append(group_key)

    def hello(self, out: str) -> str:
        self.calls["hello"].append(out)
        return out


def prepare_presets():
    """prepare a few presets for use in tests
    "Foo Device 2/preset3" is the newest and "Foo Device 2/preset2" is set to autoload
    """
    preset1 = Preset(get_preset_path("Foo Device", "preset1"))
    preset1.add(get_key_mapping(combination="1,1,1", output_symbol="b"))
    preset1.add(get_key_mapping(combination="1,2,1"))
    preset1.save()

    time.sleep(0.1)
    preset2 = Preset(get_preset_path("Foo Device", "preset2"))
    preset2.add(get_key_mapping(combination="1,3,1"))
    preset2.add(get_key_mapping(combination="1,4,1"))
    preset2.save()

    # make sure the timestamp of preset 3 is the newest,
    # so that it will be automatically loaded by the GUI
    time.sleep(0.1)
    preset3 = Preset(get_preset_path("Foo Device", "preset3"))
    preset3.add(get_key_mapping(combination="1,5,1"))
    preset3.save()

    with open(get_config_path("config.json"), "w") as file:
        json.dump({"autoload": {"Foo Device 2": "preset2"}}, file, indent=4)

    global_config.load_config()

    return preset1, preset2, preset3


cleanup()


def main():
    # https://docs.python.org/3/library/argparse.html
    parser = argparse.ArgumentParser(description=__doc__)
    # repeated argument 0 or more times with modules
    parser.add_argument("modules", type=str, nargs="*")
    # start-dir value if not using modules, allows eg python tests/test.py --start-dir unit
    parser.add_argument("--start-dir", type=str, default=".")
    parsed_args = parser.parse_args()  # takes from sys.argv by default
    modules = parsed_args.modules

    # discoverer is really convenient, but it can't find a specific test
    # in all of the available tests like unittest.main() does...,
    # so provide both options.
    if len(modules) > 0:
        # for example
        # `tests/test.py integration.test_gui.TestGui.test_can_start`
        # or `tests/test.py integration.test_gui integration.test_daemon`
        testsuite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    else:
        # run all tests by default
        testsuite = unittest.defaultTestLoader.discover(
            parsed_args.start_dir, pattern="test_*.py"
        )

    # add a newline to each "qux (foo.bar)..." output before each test,
    # because the first log will be on the same line otherwise
    original_start_test = unittest.TextTestResult.startTest

    def start_test(self, test):
        original_start_test(self, test)
        print()

    unittest.TextTestResult.startTest = start_test
    result = unittest.TextTestRunner(verbosity=2).run(testsuite)
    sys.exit(not result.wasSuccessful())
