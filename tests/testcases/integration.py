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


import sys
import time
import os
import unittest
from unittest.mock import patch
from importlib.util import spec_from_loader, module_from_spec
from importlib.machinery import SourceFileLoader

import gi
import shutil
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from keymapper.mapping import custom_mapping
from keymapper.paths import USERS_SYMBOLS, KEYCODES_PATH

from test import tmp


def gtk_iteration():
    """Iterate while events are pending."""
    while Gtk.events_pending():
        Gtk.main_iteration()


def launch(argv=None, bin_path='bin/key-mapper-gtk'):
    """Start key-mapper-gtk with the command line argument array argv."""
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

    Try to modify the configuration only by calling functions of the window.
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
        if os.path.exists(tmp):
            shutil.rmtree(tmp)
        self.window = launch()

    def tearDown(self):
        gtk_iteration()
        self.window.on_close()
        self.window.window.destroy()
        gtk_iteration()
        shutil.rmtree('/tmp/key-mapper-test')

    def get_rows(self):
        return self.window.get('key_list').get_children()

    def test_can_start(self):
        self.assertIsNotNone(self.window)
        self.assertTrue(self.window.window.get_visible())

    def test_adds_empty_rows(self):
        rows = len(self.window.get('key_list').get_children())
        self.assertEqual(rows, 1)

        custom_mapping.change(None, 13, 'a')
        time.sleep(0.2)
        gtk_iteration()

        rows = len(self.window.get('key_list').get_children())
        self.assertEqual(rows, 2)

    def test_rows(self):
        """Comprehensive test for rows."""
        class FakeEvent:
            def __init__(self, keycode):
                self.keycode = keycode

            def get_keycode(self):
                return [True, self.keycode]

        def change_empty_row(keycode, character):
            """Modify the one empty row that always exists."""
            # wait for the window to create a new empty row if needed
            time.sleep(0.2)
            gtk_iteration()

            # find the empty row
            rows = self.get_rows()
            row = rows[-1]
            self.assertNotIn('changed', row.get_style_context().list_classes())
            self.assertIsNone(row.keycode.get_label())
            self.assertEqual(row.character_input.get_text(), '')

            row.on_key_pressed(None, FakeEvent(keycode))

            self.assertEqual(int(row.keycode.get_label()), keycode)

            # set the character to make the new row complete
            row.character_input.set_text(character)

            self.assertIn('changed', row.get_style_context().list_classes())

            return row

        # add two rows by modifiying the one empty row that exists
        change_empty_row(10, 'a')
        change_empty_row(11, 'b')

        # one empty row added automatically again
        time.sleep(0.2)
        gtk_iteration()
        # sleep one more time because it's funny to watch the ui
        # during the test, how rows turn blue and stuff
        time.sleep(0.2)
        self.assertEqual(len(self.get_rows()), 3)

        self.assertEqual(custom_mapping.get_character(10), 'a')
        self.assertEqual(custom_mapping.get_character(11), 'b')
        self.assertTrue(custom_mapping.changed)

        self.window.on_save_preset_clicked(None)
        for row in self.get_rows():
            self.assertNotIn(
                'changed',
                row.get_style_context().list_classes()
            )
        self.assertFalse(custom_mapping.changed)

        # now change the first row and it should turn blue,
        # but the other should remain unhighlighted
        row = self.get_rows()[0]
        row.character_input.set_text('c')
        self.assertIn('changed', row.get_style_context().list_classes())
        for row in self.get_rows()[1:]:
            self.assertNotIn(
                'changed',
                row.get_style_context().list_classes()
            )

        self.assertEqual(custom_mapping.get_character(10), 'c')
        self.assertEqual(custom_mapping.get_character(11), 'b')
        self.assertTrue(custom_mapping.changed)

    def test_rename_and_save(self):
        custom_mapping.change(None, 14, 'a')
        self.assertEqual(self.window.selected_preset, 'new preset')
        self.window.on_save_preset_clicked(None)
        self.assertEqual(custom_mapping.get_character(14), 'a')

        custom_mapping.change(None, 14, 'b')
        self.window.get('preset_name_input').set_text('asdf')
        self.window.on_save_preset_clicked(None)
        self.assertEqual(self.window.selected_preset, 'asdf')
        self.assertTrue(os.path.exists(f'{USERS_SYMBOLS}/device_1/asdf'))
        self.assertEqual(custom_mapping.get_character(14), 'b')

    def test_select_device_and_preset(self):
        class FakeDropdown(Gtk.ComboBoxText):
            def __init__(self, name):
                self.name = name

            def get_active_text(self):
                return self.name

            def get_active_id(self):
                return self.name

        # created on start because the first device is selected and some empty
        # preset prepared.
        self.assertTrue(os.path.exists(f'{USERS_SYMBOLS}/device_1/new_preset'))
        self.assertEqual(self.window.selected_device, 'device 1')
        self.assertEqual(self.window.selected_preset, 'new preset')

        # create another one
        self.window.on_create_preset_clicked(None)
        gtk_iteration()
        self.assertTrue(os.path.exists(f'{USERS_SYMBOLS}/device_1/new_preset'))
        self.assertTrue(os.path.exists(f'{USERS_SYMBOLS}/device_1/new_preset_2'))
        self.assertEqual(self.window.selected_preset, 'new preset 2')

        self.window.on_select_preset(FakeDropdown('new preset'))
        gtk_iteration()
        self.assertEqual(self.window.selected_preset, 'new preset')

        self.assertListEqual(
            sorted(os.listdir(f'{USERS_SYMBOLS}/device_1')),
            ['new_preset', 'new_preset_2']
        )

        # now try to change the name
        self.window.get('preset_name_input').set_text('abc 123')
        gtk_iteration()
        self.assertEqual(self.window.selected_preset, 'new preset')
        self.assertFalse(os.path.exists(f'{USERS_SYMBOLS}/device_1/abc_123'))
        custom_mapping.change(None, 10, '1')
        self.window.on_save_preset_clicked(None)
        self.assertTrue(os.path.exists(KEYCODES_PATH))
        gtk_iteration()
        self.assertEqual(self.window.selected_preset, 'abc 123')
        self.assertTrue(os.path.exists(f'{USERS_SYMBOLS}/device_1/abc_123'))
        self.assertListEqual(
            sorted(os.listdir(USERS_SYMBOLS)),
            ['default', 'device_1']
        )
        self.assertListEqual(
            sorted(os.listdir(f'{USERS_SYMBOLS}/device_1')),
            ['abc_123', 'new_preset_2']
        )


if __name__ == "__main__":
    unittest.main()
