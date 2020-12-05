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


import grp
import unittest

from keymapper.dev.permissions import can_read_devices
from keymapper.paths import USER


class TestPermissions(unittest.TestCase):
    def setUp(self):
        self.getgrnam = grp.getgrnam

    def tearDown(self):
        grp.getgrnam = self.getgrnam

    def test_cannot_access(self):
        # TODO modify test
        class Grnam:
            def __init__(self, group):
                self.gr_mem = []

        grp.getgrnam = Grnam
        self.assertFalse(can_read_devices()[0])

    def test_can_access(self):
        # TODO modify test
        class Grnam:
            def __init__(self, group):
                self.gr_mem = [USER]

        grp.getgrnam = Grnam
        self.assertTrue(can_read_devices()[0])


if __name__ == "__main__":
    unittest.main()
