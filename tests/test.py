#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2020 sezanzeb <proxima@hip70890b.de>
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

import evdev
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GLib', '2.0')


assert not os.getcwd().endswith('tests')


def is_service_running():
    """Check if the daemon is running."""
    try:
        subprocess.check_output(['pgrep', '-f', 'key-mapper-service'])
        return True
    except subprocess.CalledProcessError:
        return False


if is_service_running():
    # let tests control daemon existance
    raise Exception('Expected the service not to be running already.')


# make sure the "tests" module visible
sys.path.append(os.getcwd())

# give tests some time to test stuff while the process
# is still running
EVENT_READ_TIMEOUT = 0.01

MAX_ABS = 2 ** 15


tmp = '/tmp/key-mapper-test'
uinput_write_history = []
# for tests that makes the injector create its processes
uinput_write_history_pipe = multiprocessing.Pipe()
pending_events = {}

# key-mapper is only interested in devices that have EV_KEY, add some
# random other stuff to test that they are ignored.
phys_1 = 'usb-0000:03:00.0-1/input2'
info_1 = 'bus: 0001, vendor 0001, product 0001, version 0001'

fixtures = {
    # device 1
    '/dev/input/event11': {
        'capabilities': {evdev.ecodes.EV_KEY: [], evdev.ecodes.EV_REL: []},
        'phys': f'{phys_1}/input2',
        'info': info_1,
        'name': 'device 1 foo'
    },
    '/dev/input/event10': {
        'capabilities': {evdev.ecodes.EV_KEY: list(evdev.ecodes.keys.keys())},
        'phys': f'{phys_1}/input3',
        'info': info_1,
        'name': 'device 1'
    },
    '/dev/input/event13': {
        'capabilities': {evdev.ecodes.EV_KEY: [], evdev.ecodes.EV_SYN: []},
        'phys': f'{phys_1}/input1',
        'info': info_1,
        'name': 'device 1'
    },
    '/dev/input/event14': {
        'capabilities': {evdev.ecodes.EV_SYN: []},
        'phys': f'{phys_1}/input0',
        'info': info_1,
        'name': 'device 1 qux'
    },

    # device 2
    '/dev/input/event20': {
        'capabilities': {evdev.ecodes.EV_KEY: list(evdev.ecodes.keys.keys())},
        'phys': 'usb-0000:03:00.0-2/input1',
        'info': 'bus: 0002, vendor 0001, product 0002, version 0001',
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
        'info': 'bus: 0003, vendor 0001, product 0003, version 0001',
        'name': 'gamepad'
    },

    # device that is completely ignored
    '/dev/input/event31': {
        'capabilities': {evdev.ecodes.EV_SYN: []},
        'phys': 'usb-0000:03:00.0-4/input1',
        'info': 'bus: 0004, vendor 0001, product 0004, version 0001',
        'name': 'Power Button'
    },

    # key-mapper devices are not displayed in the ui, some instance
    # of key-mapper started injecting apparently.
    '/dev/input/event40': {
        'capabilities': {evdev.ecodes.EV_KEY: list(evdev.ecodes.keys.keys())},
        'phys': 'key-mapper/input1',
        'info': 'bus: 0005, vendor 0001, product 0005, version 0001',
        'name': 'key-mapper device 2'
    },
}


def get_events():
    """Get all events written by the injector."""
    return uinput_write_history


def push_event(device, event):
    """Emit a fake event for a device.

    Parameters
    ----------
    device : string
        For example 'device 1'
    event : InputEvent
    """
    if pending_events.get(device) is None:
        pending_events[device] = []
    pending_events[device].append(event)


class InputEvent:
    """Event to put into the injector for tests.

    fakes evdev.InputEvent
    """
    def __init__(self, type, code, value, timestamp=None):
        """
        Paramaters
        ----------
        type : int
            one of evdev.ecodes.EV_*
        code : int
            keyboard event code as known to linux. E.g. 2 for the '1' button
        value : int
            1 for down, 0 for up, 2 for hold
        """
        self.type = type
        self.code = code
        self.value = value

        # tuple shorthand
        self.t = (type, code, value)

        if timestamp is None:
            timestamp = time.time()

        self.sec = int(timestamp)
        self.usec = timestamp % 1 * 1000000


def patch_paths():
    from keymapper import paths
    paths.CONFIG_PATH = '/tmp/key-mapper-test'


def patch_select():
    # goes hand in hand with patch_evdev, which makes InputDevices return
    # their names for `.fd`.
    # rlist contains device names therefore, so select.select returns the
    # name of the device for which events are pending.
    import select

    def new_select(rlist, *args):
        ret = []
        for thing in rlist:
            if hasattr(thing, 'poll') and thing.poll():
                # the reader receives msgs through pipes. If there is one
                # ready, provide the pipe
                ret.append(thing)
                continue

            if len(pending_events.get(thing, [])) > 0:
                ret.append(thing)

        return [ret, [], []]

    select.select = new_select


class InputDevice:
    # expose as existing attribute, otherwise the patch for
    # evdev < 1.0.0 will crash the test
    path = None

    def __init__(self, path):
        if path not in fixtures:
            raise FileNotFoundError()

        self.path = path
        self.phys = fixtures[path]['phys']
        self.info = fixtures[path]['info']
        self.name = fixtures[path]['name']
        self.fd = self.name

    def absinfo(self, *args):
        raise Exception('Ubuntus version of evdev doesn\'t support .absinfo')

    def grab(self):
        pass

    def read(self):
        ret = pending_events.get(self.name, [])
        if ret is not None:
            # consume all of them
            pending_events[self.name] = []

        return ret

    def read_one(self):
        if pending_events.get(self.name) is None:
            return None

        if len(pending_events[self.name]) == 0:
            return None

        event = pending_events[self.name].pop(0)
        return event

    def read_loop(self):
        """Read all prepared events at once."""
        if pending_events.get(self.name) is None:
            return

        while len(pending_events[self.name]) > 0:
            yield pending_events[self.name].pop(0)
            time.sleep(EVENT_READ_TIMEOUT)

    async def async_read_loop(self):
        """Read all prepared events at once."""
        if pending_events.get(self.name) is None:
            return

        while len(pending_events[self.name]) > 0:
            yield pending_events[self.name].pop(0)
            await asyncio.sleep(0.01)

    def capabilities(self, absinfo=True):
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


class UInput:
    def __init__(self, *args, **kwargs):
        self.fd = 0
        self.write_count = 0
        self.device = InputDevice('/dev/input/event40')
        pass

    def capabilities(self, *args, **kwargs):
        return []

    def write(self, type, code, value):
        self.write_count += 1
        event = InputEvent(type, code, value)
        uinput_write_history.append(event)
        uinput_write_history_pipe[1].send(event)

    def syn(self):
        pass


def patch_evdev():
    def list_devices():
        return fixtures.keys()

    evdev.list_devices = list_devices
    evdev.InputDevice = InputDevice
    evdev.UInput = UInput


def patch_unsaved():
    # don't block tests
    from keymapper.gtk import unsaved
    unsaved.unsaved_changes_dialog = lambda: unsaved.CONTINUE


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
patch_unsaved()
patch_select()

from keymapper.logger import update_verbosity
from keymapper.dev.injector import KeycodeInjector
from keymapper.config import config
from keymapper.dev.reader import keycode_reader
from keymapper.getdevices import refresh_devices
from keymapper.state import system_mapping, custom_mapping
from keymapper.dev.keycode_mapper import active_macros, unreleased

# no need for a high number in tests
KeycodeInjector.regrab_timeout = 0.15


_fixture_copy = copy.deepcopy(fixtures)


def cleanup():
    """Reset the applications state."""
    keycode_reader.stop_reading()
    keycode_reader.clear()
    keycode_reader.newest_event = None
    keycode_reader._unreleased = {}

    for task in asyncio.Task.all_tasks():
        task.cancel()

    os.system('pkill -f key-mapper-service')
    if os.path.exists(tmp):
        shutil.rmtree(tmp)

    config.clear_config()
    config.save_config()

    system_mapping.populate()
    custom_mapping.empty()
    custom_mapping.clear_config()

    clear_write_history()

    for key in list(active_macros.keys()):
        del active_macros[key]
    for key in list(unreleased.keys()):
        del unreleased[key]

    for key in list(pending_events.keys()):
        del pending_events[key]

    for path in list(fixtures.keys()):
        if path not in _fixture_copy:
            del fixtures[path]
    for path in list(_fixture_copy.keys()):
        if path not in fixtures:
            fixtures[path] = _fixture_copy[path]

    refresh_devices()


def main():
    update_verbosity(True)

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
