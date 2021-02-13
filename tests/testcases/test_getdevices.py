#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@hip70890b.de>
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

import evdev

from keymapper.getdevices import _GetDevices, get_devices, is_gamepad, \
    refresh_devices

from tests.test import cleanup, fixtures


class FakePipe:
    devices = None

    def send(self, devices):
        self.devices = devices


class TestGetDevices(unittest.TestCase):
    def setUp(self):
        self.original_list_devices = evdev.list_devices

    def tearDown(self):
        evdev.list_devices = self.original_list_devices
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
                'gamepad': False
            },
            'device 2': {
                'paths': ['/dev/input/event20'],
                'devices': ['device 2'],
                'gamepad': False
            },
            'gamepad': {
                'paths': ['/dev/input/event30'],
                'devices': ['gamepad'],
                'gamepad': True
            },
            'key-mapper device 2': {
                'paths': ['/dev/input/event40'],
                'devices': ['key-mapper device 2'],
                'gamepad': False
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
                'gamepad': False
            },
            'device 2': {
                'paths': ['/dev/input/event20'],
                'devices': ['device 2'],
                'gamepad': False
            },
            'gamepad': {
                'paths': ['/dev/input/event30'],
                'devices': ['gamepad'],
                'gamepad': True
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

        evdev.list_devices = list_devices

        refresh_devices()
        self.assertNotIn('camera', get_devices())
        self.assertIn('gamepad', get_devices())

    def test_gamepad_without_ev_key(self):
        def list_devices():
            return ['/foo/bar', '/dev/input/event30']

        fixtures['/foo/bar'] = {
            'name': 'gamepad2', 'phys': 'abcd2',
            'info': evdev.DeviceInfo(1, 2, 3, 4),
            'capabilities': {
                evdev.ecodes.EV_ABS: [
                    evdev.ecodes.ABS_X
                ]
            }
        }

        evdev.list_devices = list_devices

        refresh_devices()
        self.assertIn('gamepad', get_devices())
        self.assertIn('gamepad2', get_devices())

    def test_is_gamepad(self):
        # properly detects if the device is a gamepad
        EV_ABS = evdev.ecodes.EV_ABS
        EV_KEY = evdev.ecodes.EV_KEY

        class FakeDevice:
            def __init__(self, capabilities):
                self.c = capabilities

            def capabilities(self, absinfo):
                assert not absinfo
                return self.c

        self.assertTrue(is_gamepad(FakeDevice({
            EV_ABS: [evdev.ecodes.ABS_X]
        })))
        self.assertTrue(is_gamepad(FakeDevice({
            EV_ABS: [evdev.ecodes.ABS_X, evdev.ecodes.ABS_RY],
            EV_KEY: [evdev.ecodes.KEY_A]
        })))
        self.assertFalse(is_gamepad(FakeDevice({
            EV_ABS: [evdev.ecodes.ABS_X, evdev.ecodes.ABS_MT_TRACKING_ID]
        })))
        self.assertFalse(is_gamepad(FakeDevice({
            EV_ABS: [evdev.ecodes.ABS_HAT2X]
        })))
        self.assertFalse(is_gamepad(FakeDevice({
            EV_KEY: [evdev.ecodes.ABS_X]  # intentionally ABS_X (0) on EV_KEY
        })))
        self.assertFalse(is_gamepad(FakeDevice({
            EV_ABS: [evdev.ecodes.ABS_Y],
            EV_KEY: [evdev.ecodes.BTN_TOOL_PEN]
        })))
        self.assertFalse(is_gamepad(FakeDevice({
            EV_ABS: [evdev.ecodes.ABS_X],
            EV_KEY: [evdev.ecodes.BTN_STYLUS]
        })))


if __name__ == "__main__":
    unittest.main()
