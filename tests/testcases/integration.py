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
import sys
import unittest
from unittest.mock import patch
from importlib.util import spec_from_loader, module_from_spec
from importlib.machinery import SourceFileLoader

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from fakes import UseFakes, fake_config_path
from keymapper.config import get_config


def gtk_iteration():
    """Iterate while events are pending."""
    while Gtk.events_pending():
        Gtk.main_iteration()


def launch(argv=None, bin_path='bin/key-mapper-gtk'):
    """Start alsacontrol-gtk with the command line argument array argv."""
    print('\nLaunching UI')
    if not argv:
        argv = ['-d']

    with patch.object(sys, 'argv', [''] + [str(arg) for arg in argv]):
        loader = SourceFileLoader('__main__', bin_path)
        spec = spec_from_loader('__main__', loader)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)

    gtk_iteration()

    return module.window


class Integration(unittest.TestCase):
    """For tests that use the window.

    Try to modify the configuration and .asoundrc only by calling
    functions of the window.
    """
    @classmethod
    def setUpClass(cls):
        # iterate a few times when Gtk.main() is called, but don't block
        # there and just continue to the tests while the UI becomes
        # unresponsive
        Gtk.main = gtk_iteration

        # doesn't do much except avoid some Gtk assertion error, whatever:
        Gtk.main_quit = lambda: None

    def setUp(self):
        self.fakes = UseFakes()
        self.fakes.patch()
        self.window = launch()

    def tearDown(self):
        self.window.on_close()
        self.window.window.destroy()
        gtk_iteration()
        self.fakes.restore()
        if os.path.exists(fake_config_path):
            os.remove(fake_config_path)
        config = get_config()
        config.create_config_file()
        config.load_config()

    def test_can_start(self):
        self.assertIsNotNone(self.window)
        self.assertTrue(self.window.window.get_visible())


if __name__ == "__main__":
    unittest.main()
