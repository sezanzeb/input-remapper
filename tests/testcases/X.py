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


import re
import unittest

from keymapper.cli import get_system_layout_locale


class Test(unittest.TestCase):
    def test_get_system_layout_locale(self):
        layout = get_system_layout_locale()
        self.assertGreater(len(layout), 0)
        # should be all alphanumeric
        match = re.findall(r'\w+', layout)
        self.assertEqual(len(match), 1)
        self.assertEqual(match[0], layout)


if __name__ == "__main__":
    unittest.main()
