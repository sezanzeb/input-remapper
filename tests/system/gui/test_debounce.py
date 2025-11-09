#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2025 sezanzeb <b8x45ygc9@mozmail.com>
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

import time
import unittest

import gi


gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GtkSource", "4")
gi.require_version("GLib", "2.0")

from inputremapper.gui.utils import gtk_iteration, debounce, debounce_manager

from tests.lib.test_setup import test_setup


@test_setup
class TestDebounce(unittest.TestCase):
    def test_debounce(self):
        calls = 0

        class A:
            @debounce(20)
            def foo(self):
                nonlocal calls
                calls += 1

        # two methods with the same name don't confuse debounce
        class B:
            @debounce(20)
            def foo(self):
                nonlocal calls
                calls += 1

        a = A()
        b = B()

        self.assertEqual(calls, 0)

        a.foo()
        gtk_iteration()
        self.assertEqual(calls, 0)

        b.foo()
        gtk_iteration()
        self.assertEqual(calls, 0)

        time.sleep(0.021)
        gtk_iteration()
        self.assertEqual(calls, 2)

        a.foo()
        b.foo()
        a.foo()
        b.foo()
        gtk_iteration()
        self.assertEqual(calls, 2)

        time.sleep(0.021)
        gtk_iteration()
        self.assertEqual(calls, 4)

    def test_run_all_now(self):
        calls = 0

        class A:
            @debounce(20)
            def foo(self):
                nonlocal calls
                calls += 1

        a = A()
        a.foo()
        gtk_iteration()
        self.assertEqual(calls, 0)

        debounce_manager.run_all_now()
        self.assertEqual(calls, 1)

        # waiting for some time will not call it again
        time.sleep(0.021)
        gtk_iteration()
        self.assertEqual(calls, 1)

    def test_stop_all(self):
        calls = 0

        class A:
            @debounce(20)
            def foo(self):
                nonlocal calls
                calls += 1

        a = A()
        a.foo()
        gtk_iteration()
        self.assertEqual(calls, 0)

        debounce_manager.stop_all()

        # waiting for some time will not call it
        time.sleep(0.021)
        gtk_iteration()
        self.assertEqual(calls, 0)

    def test_stop(self):
        calls = 0

        class A:
            @debounce(20)
            def foo(self):
                nonlocal calls
                calls += 1

        a = A()
        a.foo()
        gtk_iteration()
        self.assertEqual(calls, 0)

        debounce_manager.stop(a, a.foo)

        # waiting for some time will not call it
        time.sleep(0.021)
        gtk_iteration()
        self.assertEqual(calls, 0)


if __name__ == "__main__":
    unittest.main()
