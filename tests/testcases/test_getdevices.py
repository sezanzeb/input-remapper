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


import unittest
from unittest import mock

import evdev

from keymapper.getdevices import _GetDevices, get_devices, classify, \
    refresh_devices, GAMEPAD, MOUSE, UNKNOWN, GRAPHICS_TABLET, TOUCHPAD, \
    KEYBOARD

from tests.test import cleanup, fixtures


class FakePipe:
    devices = None

    def send(self, devices):
        self.devices = devices


class TestGetDevices(unittest.TestCase):
    def tearDown(self):
        cleanup()

    def test_get_devices(self):
        pipe = FakePipe()
        _GetDevices(pipe).run()
        self.assertDictEqual(pipe.devices, {
            'device 1': {
                'paths': [
                    '/dev/input/event11',
                    '/dev/input/event10',
                    '/dev/input/event13'
                ],
                'devices': [
                    'device 1 foo',
                    'device 1',
                    'device 1'
                ],
                'type': MOUSE
            },
            'device 2': {
                'paths': ['/dev/input/event20'],
                'devices': ['device 2'],
                'type': KEYBOARD
            },
            'gamepad': {
                'paths': ['/dev/input/event30'],
                'devices': ['gamepad'],
                'type': GAMEPAD
            },
            'key-mapper device 2': {
                'paths': ['/dev/input/event40'],
                'devices': ['key-mapper device 2'],
                'type': KEYBOARD
            },
        })
        self.assertDictEqual(pipe.devices, get_devices(include_keymapper=True))

    def test_get_devices_2(self):
        self.assertDictEqual(get_devices(), {
            'device 1': {
                'paths': [
                    '/dev/input/event11',
                    '/dev/input/event10',
                    '/dev/input/event13'
                ],
                'devices': [
                    'device 1 foo',
                    'device 1',
                    'device 1'
                ],
                'type': MOUSE
            },
            'device 2': {
                'paths': ['/dev/input/event20'],
                'devices': ['device 2'],
                'type': KEYBOARD
            },
            'gamepad': {
                'paths': ['/dev/input/event30'],
                'devices': ['gamepad'],
                'type': GAMEPAD
            },
        })

    def test_skip_camera(self):
        def list_devices():
            return ['/foo/bar', '/dev/input/event30']

        fixtures['/foo/bar'] = {
            'name': 'camera', 'phys': 'abcd1',
            'info': evdev.DeviceInfo(1, 2, 3, 4),
            'capabilities': {
                evdev.ecodes.EV_KEY: [
                    evdev.ecodes.KEY_CAMERA
                ]
            }
        }

        with mock.patch('evdev.list_devices', list_devices):
            refresh_devices()
            self.assertNotIn('camera', get_devices())
            self.assertIn('gamepad', get_devices())

    def test_device_with_only_ev_abs(self):
        def list_devices():
            return ['/foo/bar', '/dev/input/event30']

        # could be anything, a lot of devices have ABS_X capabilities,
        # so it is not treated as gamepad joystick and since it also
        # doesn't have key capabilities, there is nothing to map.
        fixtures['/foo/bar'] = {
            'name': 'qux', 'phys': 'abcd2',
            'info': evdev.DeviceInfo(1, 2, 3, 4),
            'capabilities': {
                evdev.ecodes.EV_ABS: [
                    evdev.ecodes.ABS_X
                ]
            }
        }

        with mock.patch('evdev.list_devices', list_devices):
            refresh_devices()
            self.assertIn('gamepad', get_devices())
            self.assertNotIn('qux', get_devices())

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

        """gamepads"""

        self.assertEqual(classify(FakeDevice({
            EV_ABS: [evdev.ecodes.ABS_X, evdev.ecodes.ABS_Y],
            EV_KEY: [evdev.ecodes.BTN_A]
        })), GAMEPAD)

        """mice"""

        self.assertEqual(classify(FakeDevice({
            EV_REL: [evdev.ecodes.REL_X, evdev.ecodes.REL_Y],
            EV_KEY: [evdev.ecodes.BTN_LEFT]
        })), MOUSE)

        """keyboard"""

        self.assertEqual(classify(FakeDevice({
            EV_KEY: [evdev.ecodes.KEY_A]
        })), KEYBOARD)

        """touchpads"""

        self.assertEqual(classify(FakeDevice({
            EV_KEY: [evdev.ecodes.KEY_A],
            EV_ABS: [evdev.ecodes.ABS_MT_POSITION_X]
        })), TOUCHPAD)

        """weird combos"""

        self.assertEqual(classify(FakeDevice({
            EV_ABS: [evdev.ecodes.ABS_X, evdev.ecodes.ABS_Y],
            EV_KEY: [evdev.ecodes.BTN_A],
            EV_REL: [evdev.ecodes.REL_X]
        })), UNKNOWN)

        self.assertEqual(classify(FakeDevice({
            EV_ABS: [evdev.ecodes.ABS_X, evdev.ecodes.ABS_Y],
            EV_KEY: [evdev.ecodes.KEY_1]
        })), UNKNOWN)

        self.assertEqual(classify(FakeDevice({
            EV_ABS: [evdev.ecodes.ABS_X],
            EV_KEY: [evdev.ecodes.BTN_A]
        })), UNKNOWN)

        self.assertEqual(classify(FakeDevice({
            EV_KEY: [evdev.ecodes.BTN_A]
        })), UNKNOWN)

        self.assertEqual(classify(FakeDevice({
            EV_ABS: [evdev.ecodes.ABS_X]
        })), UNKNOWN)


if __name__ == "__main__":
    unittest.main()
