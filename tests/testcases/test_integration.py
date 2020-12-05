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
import grp
import os
import unittest
import evdev
from evdev.events import EV_KEY
import json
from unittest.mock import patch
from importlib.util import spec_from_loader, module_from_spec
from importlib.machinery import SourceFileLoader

import gi
import shutil
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from keymapper.state import custom_mapping, system_mapping
from keymapper.paths import CONFIG, get_config_path, USER
from keymapper.config import config
from keymapper.dev.reader import keycode_reader
from keymapper.gtk.row import to_string

from tests.test import tmp, pending_events, Event, uinput_write_history_pipe, \
    clear_write_history


def gtk_iteration():
    """Iterate while events are pending."""
    while Gtk.events_pending():
        Gtk.main_iteration()


# iterate a few times when Gtk.main() is called, but don't block
# there and just continue to the tests while the UI becomes
# unresponsive
Gtk.main = gtk_iteration

# doesn't do much except avoid some Gtk assertion error, whatever:
Gtk.main_quit = lambda: None


def launch(argv=None):
    """Start key-mapper-gtk with the command line argument array argv."""
    if os.path.exists(tmp):
        shutil.rmtree(tmp)
    custom_mapping.empty()

    bin_path = os.path.join(os.getcwd(), 'bin', 'key-mapper-gtk')

    if not argv:
        argv = ['-d']

    with patch.object(sys, 'argv', [''] + [str(arg) for arg in argv]):
        loader = SourceFileLoader('__main__', bin_path)
        spec = spec_from_loader('__main__', loader)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)

    gtk_iteration()

    return module.window


class FakeDropdown(Gtk.ComboBoxText):
    def __init__(self, name):
        self.name = name

    def get_active_text(self):
        return self.name

    def get_active_id(self):
        return self.name


class TestIntegration(unittest.TestCase):
    """For tests that use the window.

    Try to modify the configuration only by calling functions of the window.
    """
    def setUp(self):
        self.window = launch()

    def tearDown(self):
        self.window.on_apply_system_layout_clicked(None)
        gtk_iteration()
        self.window.on_close()
        self.window.window.destroy()
        gtk_iteration()
        shutil.rmtree('/tmp/key-mapper-test')
        clear_write_history()
        system_mapping.populate()

    def get_rows(self):
        return self.window.get('key_list').get_children()

    def test_show_device_mapping_status(self):
        # this function may not return True, otherwise the timeout
        # runs forever
        self.assertFalse(self.window.show_device_mapping_status())

    def test_autoload(self):
        self.window.on_preset_autoload_switch_activate(None, False)
        self.assertFalse(config.is_autoloaded(
            self.window.selected_device,
            self.window.selected_preset
        ))

        # select a preset for the first device
        self.window.on_select_device(FakeDropdown('device 1'))
        self.window.on_preset_autoload_switch_activate(None, True)
        self.assertTrue(config.is_autoloaded('device 1', 'new preset'))
        self.assertFalse(config.is_autoloaded('device 2', 'new preset'))
        self.assertListEqual(
            list(config.iterate_autoload_presets()),
            [('device 1', 'new preset')]
        )

        # select a preset for the second device
        self.window.on_select_device(FakeDropdown('device 2'))
        self.window.on_preset_autoload_switch_activate(None, True)
        self.assertTrue(config.is_autoloaded('device 1', 'new preset'))
        self.assertTrue(config.is_autoloaded('device 2', 'new preset'))
        self.assertListEqual(
            list(config.iterate_autoload_presets()),
            [('device 1', 'new preset'), ('device 2', 'new preset')]
        )

        # disable autoloading for the second device
        self.window.on_preset_autoload_switch_activate(None, False)
        self.assertTrue(config.is_autoloaded('device 1', 'new preset'))
        self.assertFalse(config.is_autoloaded('device 2', 'new preset'))
        self.assertListEqual(
            list(config.iterate_autoload_presets()),
            [('device 1', 'new preset')]
        )

    def test_select_device(self):
        # creates a new empty preset when no preset exists for the device
        self.window.on_select_device(FakeDropdown('device 1'))
        custom_mapping.change((EV_KEY, 50), 'q')
        custom_mapping.change((EV_KEY, 51), 'u')
        custom_mapping.change((EV_KEY, 52), 'x')
        self.assertEqual(len(custom_mapping), 3)
        self.window.on_select_device(FakeDropdown('device 2'))
        self.assertEqual(len(custom_mapping), 0)
        # it creates the file for that right away. It may have been possible
        # to write it such that it doesn't (its empty anyway), but it does,
        # so use that to test it in more detail.
        path = get_config_path('device 2', 'new preset')
        self.assertTrue(os.path.exists(path))
        with open(path, 'r') as file:
            preset = json.load(file)
            self.assertEqual(len(preset['mapping']), 0)

    def test_can_start(self):
        self.assertIsNotNone(self.window)
        self.assertTrue(self.window.window.get_visible())

    def test_row_keycode_to_string(self):
        # not an integration test, but I have all the row tests here already
        self.assertEqual(to_string(EV_KEY, 10), '9')
        self.assertEqual(to_string(EV_KEY, 39), 'SEMICOLON')

    def test_row_simple(self):
        rows = self.window.get('key_list').get_children()
        self.assertEqual(len(rows), 1)

        row = rows[0]

        row.set_new_keycode(None, None)
        self.assertIsNone(row.get_keycode())
        self.assertEqual(len(custom_mapping), 0)
        self.assertEqual(row.keycode_input.get_label(), None)

        row.set_new_keycode(EV_KEY, 30)
        self.assertEqual(len(custom_mapping), 0)
        self.assertEqual(row.get_keycode(), (EV_KEY, 30))
        # this is KEY_A in linux/input-event-codes.h,
        # but KEY_ is removed from the text
        self.assertEqual(row.keycode_input.get_label(), 'A')

        row.set_new_keycode(EV_KEY, 30)
        self.assertEqual(len(custom_mapping), 0)
        self.assertEqual(row.get_keycode(), (EV_KEY, 30))

        time.sleep(0.1)
        gtk_iteration()
        self.assertEqual(len(self.window.get('key_list').get_children()), 1)

        row.character_input.set_text('Shift_L')
        self.assertEqual(len(custom_mapping), 1)

        time.sleep(0.1)
        gtk_iteration()
        self.assertEqual(len(self.window.get('key_list').get_children()), 2)

        self.assertEqual(custom_mapping.get_character(EV_KEY, 30), 'Shift_L')
        self.assertEqual(row.get_character(), 'Shift_L')
        self.assertEqual(row.get_keycode(), (EV_KEY, 30))

    def change_empty_row(self, code, char, code_first=True, success=True):
        """Modify the one empty row that always exists.

        Utility function for other tests.

        Parameters
        ----------
        code_first : boolean
            If True, the code is entered and then the character.
            If False, the character is entered first.
        success : boolean
            If this change on the empty row is going to result in a change
            in the mapping eventually. False if this change is going to
            cause a duplicate.
        """
        # wait for the window to create a new empty row if needed
        time.sleep(0.1)
        gtk_iteration()

        # find the empty row
        rows = self.get_rows()
        row = rows[-1]
        self.assertNotIn('changed', row.get_style_context().list_classes())
        self.assertIsNone(row.keycode_input.get_label())
        self.assertEqual(row.character_input.get_text(), '')

        if char and not code_first:
            # set the character to make the new row complete
            self.assertIsNone(row.get_character())
            row.character_input.set_text(char)
            self.assertEqual(row.get_character(), char)

        self.window.window.set_focus(row.keycode_input)

        if code:
            # modifies the keycode in the row not by writing into the input,
            # but by sending an event
            keycode_reader._pipe[1].send((EV_KEY, code))
            time.sleep(0.1)
            gtk_iteration()
            if success:
                self.assertEqual(row.get_keycode(), (EV_KEY, code))
                self.assertIn(
                    'changed',
                    row.get_style_context().list_classes()
                )

        if not success:
            self.assertIsNone(row.get_keycode())
            self.assertIsNone(row.get_character())
            self.assertNotIn('changed', row.get_style_context().list_classes())

        if char and code_first:
            # set the character to make the new row complete
            self.assertIsNone(row.get_character())
            row.character_input.set_text(char)
            self.assertEqual(row.get_character(), char)

        return row

    def test_rows(self):
        """Comprehensive test for rows."""
        # how many rows there should be in the end
        num_rows_target = 3

        # add two rows by modifiying the one empty row that exists
        self.change_empty_row(10, 'a', code_first=False)
        self.change_empty_row(11, 'k(b).k(c)')

        # one empty row added automatically again
        time.sleep(0.1)
        gtk_iteration()
        # sleep one more time because it's funny to watch the ui
        # during the test, how rows turn blue and stuff
        time.sleep(0.1)
        self.assertEqual(len(self.get_rows()), num_rows_target)

        self.assertEqual(custom_mapping.get_character(EV_KEY, 10), 'a')
        self.assertEqual(custom_mapping.get_character(EV_KEY, 11), 'k(b).k(c)')
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

        self.assertEqual(custom_mapping.get_character(EV_KEY, 10), 'c')
        self.assertEqual(custom_mapping.get_character(EV_KEY, 11), 'k(b).k(c)')
        self.assertTrue(custom_mapping.changed)

        # try to add a duplicate keycode, it should be ignored
        self.change_empty_row(11, 'd', success=False)
        self.assertEqual(custom_mapping.get_character(EV_KEY, 11), 'k(b).k(c)')
        # and the number of rows shouldn't change
        self.assertEqual(len(self.get_rows()), num_rows_target)

    def test_remove_row(self):
        """Comprehensive test for rows 2."""
        # sleeps are added to be able to visually follow and debug the test
        # add two rows by modifiying the one empty row that exists
        row_1 = self.change_empty_row(10, 'a')
        row_2 = self.change_empty_row(11, 'b')
        row_3 = self.change_empty_row(None, 'c')

        # no empty row added because one is unfinished
        time.sleep(0.2)
        gtk_iteration()
        self.assertEqual(len(self.get_rows()), 3)

        self.assertEqual(custom_mapping.get_character(EV_KEY, 11), 'b')

        def remove(row, code, char, num_rows_after):
            if code is not None and char is not None:
                self.assertEqual(custom_mapping.get_character(EV_KEY, code), char)

            self.assertEqual(row.get_character(), char)
            if code is None:
                self.assertIsNone(row.get_keycode())
            else:
                self.assertEqual(row.get_keycode(), (EV_KEY, code))
            row.on_delete_button_clicked()
            time.sleep(0.2)
            gtk_iteration()
            self.assertIsNone(row.get_keycode())
            self.assertIsNone(row.get_character())
            self.assertIsNone(custom_mapping.get_character(EV_KEY, code))
            self.assertEqual(len(self.get_rows()), num_rows_after)

        remove(row_1, 10, 'a', 2)
        remove(row_2, 11, 'b', 1)
        # there is no empty row at the moment, so after removing that one,
        # which is the only row, one empty row will be there. So the number
        # of rows won't change.
        remove(row_3, None, 'c', 1)

    def test_rename_and_save(self):
        custom_mapping.change((EV_KEY, 14), 'a', (None, None))
        self.assertEqual(self.window.selected_preset, 'new preset')
        self.window.on_save_preset_clicked(None)
        self.assertEqual(custom_mapping.get_character(EV_KEY, 14), 'a')

        custom_mapping.change((EV_KEY, 14), 'b', (None, None))
        self.window.get('preset_name_input').set_text('asdf')
        self.window.on_save_preset_clicked(None)
        self.assertEqual(self.window.selected_preset, 'asdf')
        self.assertTrue(os.path.exists(f'{CONFIG}/device 1/asdf.json'))
        self.assertEqual(custom_mapping.get_character(EV_KEY, 14), 'b')

    def test_select_device_and_preset(self):
        # created on start because the first device is selected and some empty
        # preset prepared.
        self.assertTrue(os.path.exists(f'{CONFIG}/device 1/new preset.json'))
        self.assertEqual(self.window.selected_device, 'device 1')
        self.assertEqual(self.window.selected_preset, 'new preset')

        # create another one
        self.window.on_create_preset_clicked(None)
        gtk_iteration()
        self.assertTrue(os.path.exists(f'{CONFIG}/device 1/new preset.json'))
        self.assertTrue(os.path.exists(f'{CONFIG}/device 1/new preset 2.json'))
        self.assertEqual(self.window.selected_preset, 'new preset 2')

        self.window.on_select_preset(FakeDropdown('new preset'))
        gtk_iteration()
        self.assertEqual(self.window.selected_preset, 'new preset')

        self.assertListEqual(
            sorted(os.listdir(f'{CONFIG}/device 1')),
            sorted(['new preset.json', 'new preset 2.json'])
        )

        # now try to change the name
        self.window.get('preset_name_input').set_text('abc 123')
        gtk_iteration()
        self.assertEqual(self.window.selected_preset, 'new preset')
        self.assertFalse(os.path.exists(f'{CONFIG}/device 1/abc 123.json'))
        custom_mapping.change((EV_KEY, 10), '1', (None, None))
        self.window.on_save_preset_clicked(None)
        gtk_iteration()
        self.assertEqual(self.window.selected_preset, 'abc 123')
        self.assertTrue(os.path.exists(f'{CONFIG}/device 1/abc 123.json'))
        self.assertListEqual(
            sorted(os.listdir(CONFIG)),
            sorted(['device 1'])
        )
        self.assertListEqual(
            sorted(os.listdir(f'{CONFIG}/device 1')),
            sorted(['abc 123.json', 'new preset 2.json'])
        )

    def test_start_injecting(self):
        keycode_from = 9
        keycode_to = 200

        self.change_empty_row(keycode_from, 'a')
        system_mapping.clear()
        system_mapping._set('a', keycode_to)

        pending_events['device 2'] = [
            Event(evdev.events.EV_KEY, keycode_from, 1),
            Event(evdev.events.EV_KEY, keycode_from, 0)
        ]

        custom_mapping.save('device 2', 'foo preset')

        self.window.selected_device = 'device 2'
        self.window.selected_preset = 'foo preset'
        self.window.on_apply_preset_clicked(None)

        # the integration tests will cause the injection to be started as
        # processes, as intended. Luckily, recv will block until the events
        # are handled and pushed.

        # Note, that pushing events to pending_events won't work anymore
        # from here on because the injector processes memory cannot be
        # modified from here.

        event = uinput_write_history_pipe[0].recv()
        self.assertEqual(event.type, evdev.events.EV_KEY)
        self.assertEqual(event.code, keycode_to)
        self.assertEqual(event.value, 1)

        event = uinput_write_history_pipe[0].recv()
        self.assertEqual(event.type, evdev.events.EV_KEY)
        self.assertEqual(event.code, keycode_to)
        self.assertEqual(event.value, 0)

    def test_stop_injecting(self):
        keycode_from = 16
        keycode_to = 90

        self.change_empty_row(keycode_from, 't')
        system_mapping.clear()
        system_mapping._set('t', keycode_to)

        # not all of those events should be processed, since that takes some
        # time due to time.sleep in the fakes and the injection is stopped.
        pending_events['device 2'] = [Event(1, keycode_from, 1)] * 100

        custom_mapping.save('device 2', 'foo preset')

        self.window.selected_device = 'device 2'
        self.window.selected_preset = 'foo preset'
        self.window.on_apply_preset_clicked(None)

        pipe = uinput_write_history_pipe[0]
        # block until the first event is available, indicating that
        # the injector is ready
        write_history = [pipe.recv()]

        # stop
        self.window.on_apply_system_layout_clicked(None)

        # try to receive a few of the events
        time.sleep(0.2)
        while pipe.poll():
            write_history.append(pipe.recv())

        len_before = len(write_history)
        self.assertLess(len(write_history), 50)

        # since the injector should not be running anymore, no more events
        # should be received after waiting even more time
        time.sleep(0.2)
        while pipe.poll():
            write_history.append(pipe.recv())
        self.assertEqual(len(write_history), len_before)


original_access = os.access
original_getgrnam = grp.getgrnam


class TestPermissions(unittest.TestCase):
    def tearDown(self):
        os.access = original_access
        os.getgrnam = original_getgrnam

        self.window.on_close()
        self.window.window.destroy()
        gtk_iteration()
        shutil.rmtree('/tmp/key-mapper-test')

    def test_check_groups_missing(self):
        # TODO modify test
        class Grnam:
            def __init__(self, group):
                self.gr_mem = []

        grp.getgrnam = Grnam

        self.window = launch()
        status = self.window.get('status_bar')

        labels = ''
        for label in status.get_message_area():
            labels += label.get_text()
        self.assertIn('input', labels)
        self.assertIn('plugdev', labels)

    def test_check_plugdev_missing(self):
        # TODO modify test
        class Grnam:
            def __init__(self, group):
                if group == 'input':
                    self.gr_mem = [USER]
                else:
                    self.gr_mem = []

        grp.getgrnam = Grnam

        self.window = launch()
        status = self.window.get('status_bar')

        labels = ''
        for label in status.get_message_area():
            labels += label.get_text()
        self.assertNotIn('input', labels)
        self.assertIn('plugdev', labels)

    def test_check_write_uinput(self):
        # TODO modify test
        class Grnam:
            def __init__(self, group):
                self.gr_mem = [USER]

        grp.getgrnam = Grnam

        def access(path, mode):
            return False

        os.access = access

        self.window = launch()
        status = self.window.get('status_bar')

        labels = ''
        for label in status.get_message_area():
            labels += label.get_text()
        self.assertNotIn('plugdev', labels)
        self.assertIn('Insufficient permissions on /dev/uinput', labels)


if __name__ == "__main__":
    unittest.main()
