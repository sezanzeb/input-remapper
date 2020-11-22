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


import unittest

from keymapper.getdevices import _GetDevicesProcess
from keymapper.config import config


class FakePipe:
    devices = None

    def send(self, devices):
        self.devices = devices


class TestGetDevices(unittest.TestCase):
    def test_get_devices(self):
        # don't actually start the process, just use the `run` function.
        # otherwise the coverage tool can't keep track.
        pipe = FakePipe()
        _GetDevicesProcess(pipe).run()
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
                ]
            },
            'device 2': {
               'paths': ['/dev/input/event20'],
               'devices': ['device 2']
            }
        })

    def test_map_movement_devices(self):
        pipe = FakePipe()
        config.set_modify_movement_devices(False)
        _GetDevicesProcess(pipe).run()
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
                ]
            },
            'device 2': {
                'paths': ['/dev/input/event20'],
                'devices': ['device 2']
            }
        })


if __name__ == "__main__":
    unittest.main()
