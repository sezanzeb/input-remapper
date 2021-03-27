#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@sezanzeb.de>
#
# This file is part of key-mapper.
#
# key-mapper is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# key-mapper is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with key-mapper.  If not, see <https://www.gnu.org/licenses/>.


"""Sets up key-mapper for the tests and runs them."""


import os
import sys
import shutil
import time
import copy
import unittest
import subprocess
import multiprocessing
import asyncio
import psutil
from pickle import UnpicklingError

import evdev
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GLib', '2.0')


assert not os.getcwd().endswith('tests')


os.environ['UNITTEST'] = '1'


def is_service_running():
    """Check if the daemon is running."""
    try:
        subprocess.check_output(['pgrep', '-f', 'key-mapper-service'])
        return True
    except subprocess.CalledProcessError:
        return False


def join_children():
    """Wait for child processes to exit. Stop them if it takes too long."""
    this = psutil.Process(os.getpid())

    i = 0
    time.sleep(EVENT_READ_TIMEOUT)
    children = this.children(recursive=True)
    while len([c for c in children if c.status() != 'zombie']) > 0:
        for child in children:
            if i > 10:
                child.kill()
                print(
                    f'\033[90m'  # color
                    f'Killed pid {child.pid} because it didn\'t finish in time'
                    '\033[0m'  # end style
                )

        children = this.children(recursive=True)
        time.sleep(EVENT_READ_TIMEOUT)
        i += 1


if is_service_running():
    # let tests control daemon existance
    raise Exception('Expected the service not to be running already.')


# make sure the "tests" module visible
sys.path.append(os.getcwd())

# give tests some time to test stuff while the process
# is still running
EVENT_READ_TIMEOUT = 0.01

# based on experience how much time passes at most until
# the helper starts receiving previously pushed events after a
# call to start_reading
START_READING_DELAY = 0.05

MAX_ABS = 2 ** 15


tmp = '/tmp/key-mapper-test'
uinput_write_history = []
# for tests that makes the injector create its processes
uinput_write_history_pipe = multiprocessing.Pipe()
pending_events = {}


if os.path.exists(tmp):
    shutil.rmtree(tmp)


def read_write_history_pipe():
    """convert the write history from the pipe to some easier to manage list"""
    history = []
    while uinput_write_history_pipe[0].poll():
        event = uinput_write_history_pipe[0].recv()
        history.append((event.type, event.code, event.value))
    return history


# key-mapper is only interested in devices that have EV_KEY, add some
# random other stuff to test that they are ignored.
phys_1 = 'usb-0000:03:00.0-1/input2'
info_1 = evdev.device.DeviceInfo(1, 1, 1, 1)

keyboard_keys = sorted(evdev.ecodes.keys.keys())[:255]

fixtures = {
    # device 1
    '/dev/input/event11': {
        'capabilities': {
            evdev.ecodes.EV_KEY: [
                evdev.ecodes.BTN_LEFT
            ],
            evdev.ecodes.EV_REL: [
                evdev.ecodes.REL_X,
                evdev.ecodes.REL_Y,
                evdev.ecodes.REL_WHEEL,
                evdev.ecodes.REL_HWHEEL
            ]
        },
        'phys': f'{phys_1}/input2',
        'info': info_1,
        'name': 'device 1 foo',
        'group': 'device 1'
    },
    '/dev/input/event10': {
        'capabilities': {evdev.ecodes.EV_KEY: keyboard_keys},
        'phys': f'{phys_1}/input3',
        'info': info_1,
        'name': 'device 1',
        'group': 'device 1'
    },
    '/dev/input/event13': {
        'capabilities': {evdev.ecodes.EV_KEY: [], evdev.ecodes.EV_SYN: []},
        'phys': f'{phys_1}/input1',
        'info': info_1,
        'name': 'device 1',
        'group': 'device 1'
    },
    '/dev/input/event14': {
        'capabilities': {evdev.ecodes.EV_SYN: []},
        'phys': f'{phys_1}/input0',
        'info': info_1,
        'name': 'device 1 qux',
        'group': 'device 1'
    },

    # device 2
    '/dev/input/event20': {
        'capabilities': {evdev.ecodes.EV_KEY: keyboard_keys},
        'phys': 'usb-0000:03:00.0-2/input1',
        'info': evdev.device.DeviceInfo(2, 1, 2, 1),
        'name': 'device 2'
    },

    '/dev/input/event30': {
        'capabilities': {
            evdev.ecodes.EV_SYN: [],
            evdev.ecodes.EV_ABS: [
                evdev.ecodes.ABS_X,
                evdev.ecodes.ABS_Y,
                evdev.ecodes.ABS_RX,
                evdev.ecodes.ABS_RY,
                evdev.ecodes.ABS_HAT0X
            ],
            evdev.ecodes.EV_KEY: [
                evdev.ecodes.BTN_A
            ]
        },
        'phys': 'usb-0000:03:00.0-3/input1',
        'info': evdev.device.DeviceInfo(3, 1, 3, 1),
        'name': 'gamepad'
    },

    # device that is completely ignored
    '/dev/input/event31': {
        'capabilities': {evdev.ecodes.EV_SYN: []},
        'phys': 'usb-0000:03:00.0-4/input1',
        'info': evdev.device.DeviceInfo(4, 1, 4, 1),
        'name': 'Power Button'
    },

    # key-mapper devices are not displayed in the ui, some instance
    # of key-mapper started injecting apparently.
    '/dev/input/event40': {
        'capabilities': {evdev.ecodes.EV_KEY: keyboard_keys},
        'phys': 'key-mapper/input1',
        'info': evdev.device.DeviceInfo(5, 1, 5, 1),
        'name': 'key-mapper device 2'
    },
}


def setup_pipe(device):
    """Create a pipe that can be used to send events to the helper,
    which in turn will be sent to the reader
    """
    if pending_events.get(device) is None:
        pending_events[device] = multiprocessing.Pipe()


# make sure those pipes exist before any process (the helper) gets forked,
# so that events can be pushed after the fork.
for fixture in fixtures.values():
    if 'group' in fixture:
        setup_pipe(fixture['group'])


def get_events():
    """Get all events written by the injector."""
    return uinput_write_history


def push_event(device, event):
    """Make a device act like it is reading events from evdev.

    push_event is like hitting a key on a keyboard for stuff that reads from
    evdev.InputDevice (which is patched in test.py to work that way)

    Parameters
    ----------
    device : string
        For example 'device 1'
    event : InputEvent
    """
    setup_pipe(device)
    pending_events[device][0].send(event)


def push_events(device, events):
    """Push multiple events"""
    for event in events:
        push_event(device, event)


def new_event(type, code, value, timestamp=None, offset=0):
    """Create a new input_event."""
    if timestamp is None:
        timestamp = time.time() + offset

    sec = int(timestamp)
    usec = timestamp % 1 * 1000000
    event = evdev.InputEvent(sec, usec, type, code, value)
    return event


def patch_paths():
    from keymapper import paths
    paths.CONFIG_PATH = '/tmp/key-mapper-test'


class InputDevice:
    # expose as existing attribute, otherwise the patch for
    # evdev < 1.0.0 will crash the test
    path = None

    def __init__(self, path):
        if path != 'justdoit' and path not in fixtures:
            raise FileNotFoundError()

        self.path = path
        fixture = fixtures.get(path, {})
        self.phys = fixture.get('phys', 'unset')
        self.info = fixture.get('info', evdev.device.DeviceInfo(None, None, None, None))
        self.name = fixture.get('name', 'unset')

        # properties that exists for test purposes and are not part of
        # the original object
        self.group = fixture.get('group', self.name)

        # ensure a pipe exists to make this object act like
        # it is reading events from a device
        setup_pipe(self.group)

        self.fd = pending_events[self.group][1].fileno()

    def fileno(self):
        """Compatibility to select.select."""
        return self.fd

    def log(self, key, msg):
        print(
            f'\033[90m'  # color
            f'{msg} "{self.name}" "{self.path}" {key}'
            '\033[0m'  # end style
        )

    def absinfo(self, *args):
        raise Exception('Ubuntus version of evdev doesn\'t support .absinfo')

    def grab(self):
        pass

    async def async_read_loop(self):
        if pending_events.get(self.group) is None:
            self.log('no events to read', self.group)
            return

        # consume all of them
        while pending_events[self.group][1].poll():
            result = pending_events[self.group][1].recv()
            self.log(result, 'async_read_loop')
            yield result
            await asyncio.sleep(0.01)

        # doesn't loop endlessly in order to run tests for the injector in
        # the main process

    def read(self):
        # the patched fake InputDevice objects read anything pending from
        # that group.
        # To be realistic it would have to check if the provided
        # element is in its capabilities.
        if self.group not in pending_events:
            self.log('no events to read', self.group)
            return

        # consume all of them
        while pending_events[self.group][1].poll():
            event = pending_events[self.group][1].recv()
            self.log(event, 'read')
            yield event
            time.sleep(EVENT_READ_TIMEOUT)

    def read_loop(self):
        """Endless loop that yields events."""
        while True:
            event = pending_events[self.group][1].recv()
            if event is not None:
                self.log(event, 'read_loop')
                yield event
            time.sleep(EVENT_READ_TIMEOUT)

    def read_one(self):
        """Read one event or none if nothing available."""
        if pending_events.get(self.group) is None:
            return None

        if len(pending_events[self.group]) == 0:
            return None

        time.sleep(EVENT_READ_TIMEOUT)
        try:
            event = pending_events[self.group][1].recv()
        except UnpicklingError as error:
            # failed in tests sometimes
            print(error)
            return None

        self.log(event, 'read_one')
        return event

    def capabilities(self, absinfo=True, verbose=False):
        result = copy.deepcopy(fixtures[self.path]['capabilities'])

        if absinfo and evdev.ecodes.EV_ABS in result:
            absinfo_obj = evdev.AbsInfo(
                value=None, min=None, fuzz=None, flat=None,
                resolution=None, max=MAX_ABS
            )
            result[evdev.ecodes.EV_ABS] = [
                (stuff, absinfo_obj) for stuff in result[evdev.ecodes.EV_ABS]
            ]

        return result


uinputs = {}


class UInput:
    def __init__(self, events=None, name='unnamed', *args, **kwargs):
        self.fd = 0
        self.write_count = 0
        self.device = InputDevice('justdoit')
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
        print(
            f'\033[90m'  # color
            f'{(type, code, value)} written'
            '\033[0m'  # end style
        )

    def syn(self):
        pass


class InputEvent(evdev.InputEvent):
    def __init__(self, sec, usec, type, code, value):
        self.t = (type, code, value)
        super().__init__(sec, usec, type, code, value)

    def copy(self):
        return InputEvent(
            self.sec,
            self.usec,
            self.type,
            self.code,
            self.value
        )


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
        f'InputEvent{(self.type, self.code, self.value)}'
    )


def patch_os_system():
    """Avoid running pkexec."""
    original_system = os.system

    def system(command):
        if 'pkexec' in command:
            # because it
            # - will open a window for user input
            # - has no knowledge of the fixtures and patches
            raise Exception('Write patches to avoid running pkexec stuff')
        return original_system(command)

    os.system = system


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

from keymapper.logger import update_verbosity

update_verbosity(True)

from keymapper.injection.injector import Injector
from keymapper.config import config
from keymapper.gui.reader import reader
from keymapper.getdevices import refresh_devices
from keymapper.state import system_mapping, custom_mapping
from keymapper.paths import get_config_path
from keymapper.injection.keycode_mapper import active_macros, unreleased

# no need for a high number in tests
Injector.regrab_timeout = 0.15


_fixture_copy = copy.deepcopy(fixtures)
environ_copy = copy.deepcopy(os.environ)


def send_event_to_reader(event):
    """Act like the helper and send input events to the reader."""
    reader._results._unread.append({
        'type': 'event',
        'message': (
            event.sec, event.usec,
            event.type, event.code, event.value
        )
    })


def quick_cleanup(log=True):
    """Reset the applications state."""
    if log:
        print('quick cleanup')

    for key in list(pending_events.keys()):
        while pending_events[key][1].poll():
            pending_events[key][1].recv()

    try:
        reader.terminate()
    except (BrokenPipeError, OSError):
        pass

    if asyncio.get_event_loop().is_running():
        for task in asyncio.all_tasks():
            task.cancel()

    if os.path.exists(tmp):
        shutil.rmtree(tmp)

    config.path = os.path.join(get_config_path(), 'config.json')
    config.clear_config()
    config.save_config()

    system_mapping.populate()
    custom_mapping.empty()
    custom_mapping.clear_config()
    custom_mapping.changed = False

    clear_write_history()

    for name in list(uinputs.keys()):
        del uinputs[name]

    for key in list(active_macros.keys()):
        del active_macros[key]
    for key in list(unreleased.keys()):
        del unreleased[key]

    for path in list(fixtures.keys()):
        if path not in _fixture_copy:
            del fixtures[path]
    for path in list(_fixture_copy.keys()):
        if path not in fixtures:
            fixtures[path] = _fixture_copy[path]

    os.environ.update(environ_copy)
    for key in list(os.environ.keys()):
        if key not in environ_copy:
            del os.environ[key]

    join_children()

    reader.clear()

    for _, pipe in pending_events.values():
        assert not pipe.poll()


def cleanup():
    """Reset the applications state.

    Using this is slower, usually quick_cleanup() is sufficient.
    """
    print('cleanup')

    os.system('pkill -f key-mapper-service')
    os.system('pkill -f key-mapper-control')
    time.sleep(0.05)

    quick_cleanup(log=False)
    refresh_devices()


def spy(obj, name):
    """Keep track of arguments and callcount.

    Get a list of the call history that keeps getting updated.
    """
    original_func = obj.__getattribute__(name)
    history = []

    def new_func(*args, **kwargs):
        history.append((args, kwargs))
        original_func(*args, **kwargs)

    obj.__setattr__(name, new_func)

    return history


def main():
    cleanup()

    modules = sys.argv[1:]
    # discoverer is really convenient, but it can't find a specific test
    # in all of the available tests like unittest.main() does...,
    # so provide both options.
    if len(modules) > 0:
        # for example
        # `tests/test.py test_integration.TestIntegration.test_can_start`
        # or `tests/test.py test_integration test_daemon`
        testsuite = unittest.defaultTestLoader.loadTestsFromNames(
            [f'testcases.{module}' for module in modules]
        )
    else:
        # run all tests by default
        testsuite = unittest.defaultTestLoader.discover(
            'testcases', pattern='*.py'
        )

    # add a newline to each "qux (foo.bar)..." output before each test,
    # because the first log will be on the same line otherwise
    original_start_test = unittest.TextTestResult.startTest

    def start_test(self, test):
        original_start_test(self, test)
        print()

    unittest.TextTestResult.startTest = start_test
    unittest.TextTestRunner(verbosity=2).run(testsuite)


if __name__ == "__main__":
    main()
