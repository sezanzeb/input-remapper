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


import sys
import time
import unittest
from keymapper.logger import update_verbosity


tmp = '/tmp/key-mapper-test'
uinput_write_history = []
fake_event_queue = []


input_device_events = {}


def push_event(device, event):
    """Emit a fake event for the device.

    Parameters
    ----------
    device : string
    event : Event
    """
    if input_device_events.get(device) is None:
        input_device_events[device] = []
    input_device_events[device].append(event)


class Event:
    """Event to put into the injector for tests."""
    def __init__(self, type, code, value):
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


def patch_paths():
    from keymapper import paths
    prefix = '/tmp/key-mapper-test/X11/'
    paths.X11_SYMBOLS = prefix + 'symbols'
    paths.CONFIG = prefix + 'symbols/key-mapper/user'
    paths.DEFAULT_SYMBOLS = prefix + 'symbols/key-mapper/user/default'
    paths.KEYCODES_PATH = prefix + 'keycodes/key-mapper'


# TODO patch for the injector or something idk?


def patch_evdev():
    import evdev
    # key-mapper is only interested in devices that have EV_KEY, add some
    # random other stuff to test that they are ignored.
    fixtures = {
        # device 1
        '/dev/input/event11': {
            'capabilities': {evdev.ecodes.EV_KEY: [], evdev.ecodes.EV_ABS: []},
            'phys': 'usb-0000:03:00.0-1/input2',
            'name': 'device 1 foo'
        },
        '/dev/input/event10': {
            'capabilities': {evdev.ecodes.EV_KEY: []},
            'phys': 'usb-0000:03:00.0-1/input3',
            'name': 'device 1'
        },
        '/dev/input/event13': {
            'capabilities': {evdev.ecodes.EV_KEY: [], evdev.ecodes.EV_SYN: []},
            'phys': 'usb-0000:03:00.0-1/input1',
            'name': 'device 1'
        },
        '/dev/input/event14': {
            'capabilities': {evdev.ecodes.EV_SYN: []},
            'phys': 'usb-0000:03:00.0-1/input0',
            'name': 'device 1 qux'
        },

        # device 2
        '/dev/input/event20': {
            'capabilities': {evdev.ecodes.EV_KEY: []},
            'phys': 'usb-0000:03:00.0-2/input1',
            'name': 'device 2'
        },

        # something that is completely ignored
        '/dev/input/event30': {
            'capabilities': {evdev.ecodes.EV_SYN: []},
            'phys': 'usb-0000:03:00.0-3/input1',
            'name': 'device 3'
        },
    }

    def list_devices():
        return fixtures.keys()

    class InputDevice:
        def __init__(self, path):
            self.path = path
            self.phys = fixtures[path]['phys']
            self.name = fixtures[path]['name']

        def grab(self):
            pass

        def read_loop(self):
            while True:
                pending_events = input_device_events.get(self.name)
                if pending_events is not None and len(pending_events) > 0:
                    yield pending_events.pop(0)
                time.sleep(0.01)

        def capabilities(self):
            return fixtures[self.path]['capabilities']

    class UInput:
        def write(self, *args):
            uinput_write_history.append(args)

        def syn(self):
            pass

    evdev.list_devices = list_devices
    evdev.InputDevice = InputDevice
    evdev.UInput = UInput


def patch_unsaved():
    # don't block tests
    from keymapper.gtk import unsaved
    unsaved.unsaved_changes_dialog = lambda: unsaved.CONTINUE


# quickly fake some stuff before any other file gets a chance to import
# the original versions
patch_paths()
patch_evdev()
patch_unsaved()


if __name__ == "__main__":
    update_verbosity(True)

    modules = sys.argv[1:]
    # discoverer is really convenient, but it can't find a specific test
    # in all of the available tests like unittest.main() does...,
    # so provide both options.
    if len(modules) > 0:
        # for example `tests/test.py integration.Integration.test_can_start`
        testsuite = unittest.defaultTestLoader.loadTestsFromNames(
            [f'testcases.{module}' for module in modules]
        )
    else:
        # run all tests by default
        testsuite = unittest.defaultTestLoader.discover(
            'testcases', pattern='*.py'
        )
    testrunner = unittest.TextTestRunner(verbosity=1).run(testsuite)
