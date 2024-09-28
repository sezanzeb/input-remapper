#!/usr/bin/python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2023 sezanzeb <proxima@sezanzeb.de>
#
# This file is part of input-remapper.
#
# input-remapper is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# input-remapper is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with input-remapper.  If not, see <https://www.gnu.org/licenses/>.


from tests.lib.cleanup import quick_cleanup

import unittest

from inputremapper.injection.numlock import is_numlock_on, set_numlock, ensure_numlock
from tests.new_test import setup_tests


@setup_tests
class TestNumlock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        quick_cleanup()

    def tearDown(self):
        quick_cleanup()

    def test_numlock(self):
        before = is_numlock_on()

        set_numlock(not before)  # should change
        self.assertEqual(not before, is_numlock_on())

        @ensure_numlock
        def wrapped_1():
            set_numlock(not is_numlock_on())

        @ensure_numlock
        def wrapped_2():
            pass

        # should not change
        wrapped_1()
        self.assertEqual(not before, is_numlock_on())
        wrapped_2()
        self.assertEqual(not before, is_numlock_on())

        # toggle one more time to restore the previous configuration
        set_numlock(before)
        self.assertEqual(before, is_numlock_on())


if __name__ == "__main__":
    unittest.main()
