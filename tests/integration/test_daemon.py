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

import multiprocessing
import os
import time
import unittest

import gi

from tests.lib.test_setup import is_service_running

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from inputremapper.daemon import Daemon, BUS_NAME
from tests.lib.test_setup import test_setup


def gtk_iteration():
    """Iterate while events are pending."""
    while Gtk.events_pending():
        Gtk.main_iteration()


@test_setup
class TestDBusDaemon(unittest.TestCase):
    def setUp(self):
        # You need to install input-remapper into your system in order for this test
        # to work.
        self.process = multiprocessing.Process(
            target=os.system, args=("input-remapper-service -d",)
        )
        self.process.start()
        time.sleep(1)

        # should not use pkexec, but rather connect to the previously
        # spawned process
        self.interface = Daemon.connect()

    def tearDown(self):
        self.interface.stop_all()
        os.system("pkill -f input-remapper-service")

        for _ in range(10):
            time.sleep(0.1)
            if not is_service_running():
                break

        self.assertFalse(is_service_running())

    def test_can_connect(self):
        # it's a remote dbus object
        self.assertEqual(self.interface._bus_name, BUS_NAME)
        self.assertFalse(isinstance(self.interface, Daemon))
        self.assertEqual(self.interface.hello("foo"), "foo")


if __name__ == "__main__":
    unittest.main()
