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


import time
import unittest
import asyncio

from keymapper.dev.macros import parse, _Macro
from keymapper.config import config


class TestMacros(unittest.TestCase):
    def setUp(self):
        self.result = []
        self.handler = lambda char, value: self.result.append((char, value))
        self.loop = asyncio.get_event_loop()

    def tearDown(self):
        self.result = []

    def test_0(self):
        self.loop.run_until_complete(parse('k(1)', self.handler).run())
        self.assertListEqual(self.result, [(1, 1), (1, 0)])

    def test_1(self):
        macro = 'k(1).k(a).k(3)'
        self.loop.run_until_complete(parse(macro, self.handler).run())
        self.assertListEqual(self.result, [
            (1, 1), (1, 0),
            ('a', 1), ('a', 0),
            (3, 1), (3, 0),
        ])
    
    def test_2(self):
        start = time.time()
        repeats = 20
        macro = f'r({repeats}, k(k))'
        self.loop.run_until_complete(parse(macro, self.handler).run())
        sleep_time = 2 * repeats * config.get_keystroke_sleep() / 1000
        self.assertGreater(time.time() - start, sleep_time * 0.9)
        self.assertLess(time.time() - start, sleep_time * 1.1)
        self.assertListEqual(self.result, [('k', 1), ('k', 0)] * repeats)

    def test_3(self):
        start = time.time()
        macro = 'r(3, k(m).w(100))'
        self.loop.run_until_complete(parse(macro, self.handler).run())

        keystroke_time = 6 * config.get_keystroke_sleep()
        total_time = keystroke_time + 300
        total_time /= 1000

        self.assertGreater(time.time() - start, total_time * 0.9)
        self.assertLess(time.time() - start, total_time * 1.1)
        self.assertListEqual(self.result, [
            ('m', 1), ('m', 0),
            ('m', 1), ('m', 0),
            ('m', 1), ('m', 0),
        ])

    def test_4(self):
        macro = '  r(2,\nk(\nr ).k(-\n )).k(m)  '
        self.loop.run_until_complete(parse(macro, self.handler).run())
        self.assertListEqual(self.result, [
            ('r', 1), ('r', 0),
            ('-', 1), ('-', 0),
            ('r', 1), ('r', 0),
            ('-', 1), ('-', 0),
            ('m', 1), ('m', 0),
        ])

    def test_5(self):
        start = time.time()
        macro = 'w(200).r(2,m(w,\nr(2,\tk(r))).w(10).k(k))'
        self.loop.run_until_complete(parse(macro, self.handler).run())

        num_pauses = 8 + 6 + 4
        keystroke_time = num_pauses * config.get_keystroke_sleep()
        wait_time = 220
        total_time = (keystroke_time + wait_time) / 1000

        self.assertLess(time.time() - start, total_time * 1.1)
        self.assertGreater(time.time() - start, total_time * 0.9)
        expected = [('w', 1)]
        expected += [('r', 1), ('r', 0)] * 2
        expected += [('w', 0)]
        expected += [('k', 1), ('k', 0)]
        expected *= 2
        self.assertListEqual(self.result, expected)

    def test_6(self):
        # does nothing without .run
        ret = parse('k(a).r(3, k(b))', self.handler)
        self.assertIsInstance(ret, _Macro)
        self.assertListEqual(self.result, [])


if __name__ == '__main__':
    unittest.main()
