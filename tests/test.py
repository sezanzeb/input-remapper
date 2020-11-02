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
import unittest

from keymapper import paths
from keymapper import X
from keymapper.logger import update_verbosity


def create_stubs():
    """Stub some linux stuff."""
    paths.SYMBOLS_PATH = '/tmp/key-mapper-test/symbols'
    paths.CONFIG_PATH = '/tmp/key-mapper-test/.config'

    def find_devices():
        return {
            'device 1': ['/dev/input/event10', '/dev/input/event11'],
            'device 2': ['/dev/input/event3']
        }

    X.find_devices = find_devices


if __name__ == "__main__":
    # make sure to do this before any other file gets a chance to do imports
    create_stubs()

    update_verbosity(True)

    modules = sys.argv[1:]
    # discoverer is really convenient, but it can't find a specific test
    # in all of the available tests like unittest.main() does...,
    # so provide both options.
    if len(modules) > 0:
        # for example `tests/test.py ConfigTest.testFirstLine`
        testsuite = unittest.defaultTestLoader.loadTestsFromNames(
            [f'testcases.{module}' for module in modules]
        )
    else:
        # run all tests by default
        testsuite = unittest.defaultTestLoader.discover(
            'testcases', pattern='*.py'
        )
    testrunner = unittest.TextTestRunner(verbosity=1).run(testsuite)
