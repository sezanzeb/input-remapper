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


import os
import unittest

from keymapper.logger import update_verbosity
from keymapper.X import parse_libinput_list, parse_evtest


class TestX(unittest.TestCase):
    def check_result(self, result):
        count = 0
        for name, paths in result.items():
            self.assertIsInstance(name, str)
            self.assertIsInstance(paths, list)
            for path in paths:
                self.assertIsInstance(path, str)
                self.assertTrue(path.startswith('/dev/input/event'))
                count += 1
        self.assertGreater(count, 0)

    def test_libinput(self):
        self.check_result(parse_libinput_list())

    def test_evtest(self):
        self.check_result(parse_evtest())


if __name__ == "__main__":
    unittest.main()
