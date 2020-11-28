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
        macro = 'k(1 2).k(a).k(3)'
        self.loop.run_until_complete(parse(macro, self.handler).run())
        self.assertListEqual(self.result, [
            ('1 2', 1), ('1 2', 0),
            ('a', 1), ('a', 0),
            (3, 1), (3, 0),
        ])
    
    def test_2(self):
        start = time.time()
        macro = 'r(1, k(k))'
        self.loop.run_until_complete(parse(macro, self.handler).run())
        self.assertLess(time.time() - start, 0.1)
        self.assertListEqual(self.result, [
            ('k', 1), ('k', 0),
        ])

    def test_3(self):
        start = time.time()
        macro = 'r(3, k(m).w(100, 200))'
        self.loop.run_until_complete(parse(macro, self.handler).run())
        self.assertGreater(time.time() - start, 0.1 * 3)
        self.assertLess(time.time() - start, 0.21 * 3)
        self.assertListEqual(self.result, [
            ('m', 1), ('m', 0),
            ('m', 1), ('m', 0),
            ('m', 1), ('m', 0),
        ])

    def test_4(self):
        macro = '  r(2,\nk(\rr ).k(-\n )).k(m)  '
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
        macro = 'w(200).r(2,m(w,\rr(2,\tk(r))).w(10).k(k))'
        self.loop.run_until_complete(parse(macro, self.handler).run())
        self.assertLess(time.time() - start, 0.23)
        self.assertGreater(time.time() - start, 0.21)
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
