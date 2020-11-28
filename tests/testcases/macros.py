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

from keymapper.dev.macros import Macro, k, m, r, w


class TestMacros(unittest.TestCase):
    def test_1(self):
        r(3, k('a').w(200)).run()

    def test_2(self):
        r(2, k('a').k('-')).k('b').run()

    def test_3(self):
        w(400).m('SHIFT_L', r(2, k('a'))).w(10).k('b').run()

    def test_4(self):
        # prints nothing without .run
        k('a').r(3, k('b'))



if __name__ == "__main__":
    unittest.main()
