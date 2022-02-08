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


"""Sets up inputremapper for the tests and runs them."""
import os
import sys
import tempfile

# the working directory should be the project root
assert not os.getcwd().endswith("tests")
assert not os.getcwd().endswith("unit")
assert not os.getcwd().endswith("integration")

# make sure the "tests" module visible
sys.path.append(os.getcwd())
if __name__ == "__main__":
    # import this file to itself to make sure is not run twice and all global variables end up in sys.modules
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
# the helper starts receiving previously pushed events after a
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
pending_events = {}


def read_write_history_pipe():
    """convert the write history from the pipe to some easier to manage list"""
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

fixtures = {
    "/dev/input/event1": {
        "capabilities": {
            evdev.ecodes.EV_KEY: [evdev.ecodes.KEY_A],
        },
        "phys": "usb-0000:03:00.0-0/input1",
        "info": info_foo,
        "name": "Foo Device",
    },
    # Another "Foo Device", which will get an incremented key.
    # If possible write tests using this one, because name != key here and
    # that would be important to test as well. Otherwise the tests can't
    # see if the groups correct attribute is used in functions and paths.
    "/dev/input/event11": {
        "capabilities": {
            evdev.ecodes.EV_KEY: [evdev.ecodes.BTN_LEFT],
            evdev.ecodes.EV_REL: [
                evdev.ecodes.REL_X,
                evdev.ecodes.REL_Y,
                evdev.ecodes.REL_WHEEL,
                evdev.ecodes.REL_HWHEEL,
            ],
        },
        "phys": f"{phys_foo}/input2",
        "info": info_foo,
        "name": "Foo Device foo",
        "group_key": "Foo Device 2",  # expected key
    },
    "/dev/input/event10": {
        "capabilities": {evdev.ecodes.EV_KEY: keyboard_keys},
        "phys": f"{phys_foo}/input3",
        "info": info_foo,
        "name": "Foo Device",
        "group_key": "Foo Device 2",
    },
    "/dev/input/event13": {
        "capabilities": {evdev.ecodes.EV_KEY: [], evdev.ecodes.EV_SYN: []},
        "phys": f"{phys_foo}/input1",
        "info": info_foo,
        "name": "Foo Device",
        "group_key": "Foo Device 2",
    },
    "/dev/input/event14": {
        "capabilities": {evdev.ecodes.EV_SYN: []},
        "phys": f"{phys_foo}/input0",
        "info": info_foo,
        "name": "Foo Device qux",
        "group_key": "Foo Device 2",
    },
    # Bar Device
    "/dev/input/event20": {
        "capabilities": {evdev.ecodes.EV_KEY: keyboard_keys},
        "phys": "usb-0000:03:00.0-2/input1",
        "info": evdev.device.DeviceInfo(2, 1, 2, 1),
        "name": "Bar Device",
    },
    "/dev/input/event30": {
        "capabilities": {
            evdev.ecodes.EV_SYN: [],
            evdev.ecodes.EV_ABS: [
                evdev.ecodes.ABS_X,
                evdev.ecodes.ABS_Y,
                evdev.ecodes.ABS_RX,
                evdev.ecodes.ABS_RY,
                evdev.ecodes.ABS_Z,
                evdev.ecodes.ABS_RZ,
                evdev.ecodes.ABS_HAT0X,
            ],
            evdev.ecodes.EV_KEY: [evdev.ecodes.BTN_A],
        },
        "phys": "",  # this is empty sometimes
        "info": evdev.device.DeviceInfo(3, 1, 3, 1),
        "name": "gamepad",
    },
    # device that is completely ignored
    "/dev/input/event31": {
        "capabilities": {evdev.ecodes.EV_SYN: []},
        "phys": "usb-0000:03:00.0-4/input1",
        "info": evdev.device.DeviceInfo(4, 1, 4, 1),
        "name": "Power Button",
    },
    # input-remapper devices are not displayed in the ui, some instance
    # of input-remapper started injecting apparently.
    "/dev/input/event40": {
        "capabilities": {evdev.ecodes.EV_KEY: keyboard_keys},
        "phys": "input-remapper/input1",
        "info": evdev.device.DeviceInfo(5, 1, 5, 1),
        "name": "input-remapper Bar Device",
    },
    # denylisted
    "/dev/input/event51": {
        "capabilities": {evdev.ecodes.EV_KEY: keyboard_keys},
        "phys": "usb-0000:03:00.0-5/input1",
        "info": evdev.device.DeviceInfo(6, 1, 6, 1),
        "name": "YuBiCofooYuBiKeYbar",
    },
}


def setup_pipe(group_key):
    """Create a pipe that can be used to send events to the helper,
    which in turn will be sent to the reader
    """
    if pending_events.get(group_key) is None:
        pending_events[group_key] = multiprocessing.Pipe()


# make sure those pipes exist before any process (the helper) gets forked,
# so that events can be pushed after the fork.
for fixture in fixtures.values():
    if "group_key" in fixture:
        setup_pipe(fixture["group_key"])


def get_events():
    """Get all events written by the injector."""
    return uinput_write_history


def push_event(group_key, event):
    """Make a device act like it is reading events from evdev.

    push_event is like hitting a key on a keyboard for stuff that reads from
    evdev.InputDevice (which is patched in test.py to work that way)

    Parameters
    ----------
    group_key : string
        For example 'Foo Device'
    event : InputEvent
    """
    setup_pipe(group_key)
    pending_events[group_key][0].send(event)


def push_events(group_key, events):
    """Push multiple events"""
    for event in events:
        push_event(group_key, event)


def new_event(type, code, value, timestamp=None, offset=0):
    """Create a new input_event."""
    if timestamp is None:
        timestamp = time.time() + offset

    sec = int(timestamp)
    usec = timestamp % 1 * 1000000
    event = InputEvent(sec, usec, type, code, value)
    return event


def patch_paths():
    from inputremapper.configs import paths

    paths.CONFIG_PATH = tmp


class InputDevice:
    # expose as existing attribute, otherwise the patch for
    # evdev < 1.0.0 will crash the test
    path = None

    def __init__(self, path):
        if path != "justdoit" and path not in fixtures:
            raise FileNotFoundError()

        self.path = path
        fixture = fixtures.get(path, {})
        self.phys = fixture.get("phys", "unset")
        self.info = fixture.get("info", evdev.device.DeviceInfo(None, None, None, None))
        self.name = fixture.get("name", "unset")

        # this property exists only for test purposes and is not part of
        # the original evdev.InputDevice class
        self.group_key = fixture.get("group_key", self.name)

        # ensure a pipe exists to make this object act like
        # it is reading events from a device
        setup_pipe(self.group_key)

        self.fd = pending_events[self.group_key][1].fileno()

    def push_events(self, events):
        push_events(self.group_key, events)

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
        if pending_events.get(self.group_key) is None:
            self.log("no events to read", self.group_key)
            return

        # consume all of them
        while pending_events[self.group_key][1].poll():
            result = pending_events[self.group_key][1].recv()
            self.log(result, "async_read_loop")
            yield result
            await asyncio.sleep(0.01)

        # doesn't loop endlessly in order to run tests for the injector in
        # the main process

    def read(self):
        # the patched fake InputDevice objects read anything pending from
        # that group.
        # To be realistic it would have to check if the provided
        # element is in its capabilities.
        if self.group_key not in pending_events:
            self.log("no events to read", self.group_key)
            return

        # consume all of them
        while pending_events[self.group_key][1].poll():
            event = pending_events[self.group_key][1].recv()
            self.log(event, "read")
            yield event
            time.sleep(EVENT_READ_TIMEOUT)

    def read_loop(self):
        """Endless loop that yields events."""
        while True:
            event = pending_events[self.group_key][1].recv()
            if event is not None:
                self.log(event, "read_loop")
                yield event
            time.sleep(EVENT_READ_TIMEOUT)

    def read_one(self):
        """Read one event or none if nothing available."""
        if pending_events.get(self.group_key) is None:
            return None

        if len(pending_events[self.group_key]) == 0:
            return None

        time.sleep(EVENT_READ_TIMEOUT)
        try:
            event = pending_events[self.group_key][1].recv()
        except (UnpicklingError, EOFError):
            # failed in tests sometimes
            return None

        self.log(event, "read_one")
        return event

    def capabilities(self, absinfo=True, verbose=False):
        result = copy.deepcopy(fixtures[self.path]["capabilities"])

        if absinfo and evdev.ecodes.EV_ABS in result:
            absinfo_obj = evdev.AbsInfo(
                value=None,
                min=MIN_ABS,
                fuzz=None,
                flat=None,
                resolution=None,
                max=MAX_ABS,
            )
            result[evdev.ecodes.EV_ABS] = [
                (stuff, absinfo_obj) for stuff in result[evdev.ecodes.EV_ABS]
            ]

        return result


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

    def capabilities(self, *args, **kwargs):
        return self.events

    def write(self, type, code, value):
        self.write_count += 1
        event = new_event(type, code, value)
        uinput_write_history.append(event)
        uinput_write_history_pipe[1].send(event)
        self.write_history.append(event)
        logger.info("%s written", (type, code, value))

    def syn(self):
        pass


class InputEvent(evdev.InputEvent):
    def __init__(self, sec, usec, type, code, value):
        self.t = (type, code, value)
        super().__init__(sec, usec, type, code, value)

    def copy(self):
        return InputEvent(self.sec, self.usec, self.type, self.code, self.value)


def patch_evdev():
    def list_devices():
        return fixtures.keys()

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
    """xmodmap -pke should always return a fixed set of symbols.

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


# quickly fake some stuff before any other file gets a chance to import
# the original versions
patch_paths()
patch_evdev()
patch_events()
patch_os_system()
patch_check_output()

from inputremapper.logger import update_verbosity

update_verbosity(True)

from inputremapper.injection.injector import Injector
from inputremapper.configs.global_config import global_config
from inputremapper.gui.reader import reader
from inputremapper.groups import groups
from inputremapper.configs.system_mapping import system_mapping
from inputremapper.gui.active_preset import active_preset
from inputremapper.configs.paths import get_config_path
from inputremapper.injection.macros.macro import macro_variables
from inputremapper.injection.consumers.keycode_mapper import active_macros, unreleased
from inputremapper.injection.global_uinputs import global_uinputs

# no need for a high number in tests
Injector.regrab_timeout = 0.05


_fixture_copy = copy.deepcopy(fixtures)
environ_copy = copy.deepcopy(os.environ)


def send_event_to_reader(event):
    """Act like the helper and send input events to the reader."""
    reader._results._unread.append(
        {
            "type": "event",
            "message": (event.sec, event.usec, event.type, event.code, event.value),
        }
    )


def quick_cleanup(log=True):
    """Reset the applications state."""
    if log:
        print("quick cleanup")

    for device in list(pending_events.keys()):
        try:
            while pending_events[device][1].poll():
                pending_events[device][1].recv()
        except (UnpicklingError, EOFError):
            pass

        # setup new pipes for the next test
        pending_events[device] = None
        setup_pipe(device)

    try:
        reader.terminate()
    except (BrokenPipeError, OSError):
        pass

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

    active_preset.empty()
    active_preset.clear_config()
    active_preset.set_has_unsaved_changes(False)

    clear_write_history()

    for name in list(uinputs.keys()):
        del uinputs[name]

    for device in list(active_macros.keys()):
        del active_macros[device]
    for device in list(unreleased.keys()):
        del unreleased[device]

    for path in list(fixtures.keys()):
        if path not in _fixture_copy:
            del fixtures[path]
    for path in list(_fixture_copy.keys()):
        fixtures[path] = copy.deepcopy(_fixture_copy[path])

    os.environ.update(environ_copy)
    for device in list(os.environ.keys()):
        if device not in environ_copy:
            del os.environ[device]

    reader.clear()

    for _, pipe in pending_events.values():
        assert not pipe.poll()

    assert macro_variables.is_alive(1)
    for uinput in global_uinputs.devices.values():
        uinput.write_count = 0
        uinput.write_history = []


def cleanup():
    """Reset the applications state.

    Using this is slower, usually quick_cleanup() is sufficient.
    """
    print("cleanup")

    os.system("pkill -f input-remapper-service")
    os.system("pkill -f input-remapper-control")
    time.sleep(0.05)

    quick_cleanup(log=False)
    groups.refresh()
    with patch.object(sys, "argv", ["input-remapper-service"]):
        global_uinputs.prepare()


def spy(obj, name):
    """Convenient wrapper for patch.object(..., ..., wraps=...)."""
    return patch.object(obj, name, wraps=obj.__getattribute__(name))


cleanup()


def main():
    modules = sys.argv[1:]
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
        testsuite = unittest.defaultTestLoader.discover(".", pattern="test_*.py")

    # add a newline to each "qux (foo.bar)..." output before each test,
    # because the first log will be on the same line otherwise
    original_start_test = unittest.TextTestResult.startTest

    def start_test(self, test):
        original_start_test(self, test)
        print()

    unittest.TextTestResult.startTest = start_test
    result = unittest.TextTestRunner(verbosity=2).run(testsuite)
    sys.exit(not result.wasSuccessful())
