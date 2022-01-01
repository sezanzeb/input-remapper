#!/usr/bin/python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@sezanzeb.de>
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


import sys
import time
import atexit
import os
import unittest
import multiprocessing
import evdev
from evdev.ecodes import (
    EV_KEY,
    EV_ABS,
    KEY_LEFTSHIFT,
    KEY_A,
    ABS_RX,
    EV_REL,
    REL_X,
    ABS_X,
)
import json
from unittest.mock import patch
from importlib.util import spec_from_loader, module_from_spec
from importlib.machinery import SourceFileLoader

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

from inputremapper.system_mapping import system_mapping, XMODMAP_FILENAME
from inputremapper.gui.custom_mapping import custom_mapping
from inputremapper.paths import CONFIG_PATH, get_preset_path, get_config_path
from inputremapper.config import config, WHEEL, MOUSE, BUTTONS
from inputremapper.gui.reader import reader
from inputremapper.injection.injector import RUNNING, FAILED, UNKNOWN
from inputremapper.gui.row import Row, to_string, HOLDING, IDLE
from inputremapper.gui.window import Window
from inputremapper.key import Key
from inputremapper.daemon import Daemon
from inputremapper.groups import groups
from inputremapper.gui.helper import RootHelper

from tests.test import (
    tmp,
    push_events,
    new_event,
    spy,
    cleanup,
    uinput_write_history_pipe,
    MAX_ABS,
    EVENT_READ_TIMEOUT,
    send_event_to_reader,
    MIN_ABS,
)


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
    """Start input-remapper-gtk with the command line argument array argv."""
    bin_path = os.path.join(os.getcwd(), "bin", "input-remapper-gtk")

    if not argv:
        argv = ["-d"]

    with patch("inputremapper.gui.window.Window.setup_timeouts", lambda *args: None):
        with patch.object(sys, "argv", [""] + [str(arg) for arg in argv]):
            loader = SourceFileLoader("__main__", bin_path)
            spec = spec_from_loader("__main__", loader)
            module = module_from_spec(spec)
            spec.loader.exec_module(module)

    gtk_iteration()

    # otherwise a new handler is added with each call to launch, which
    # spams tons of garbage when all tests finish
    atexit.unregister(module.stop)

    # to avoid triggering any timeouts while the module loads, patch it and
    # do it afterwards. Because some tests don't want them to be triggered
    # yet and test the windows initial state. This is only a problem on
    # slow computers that take long for the window import.
    module.window.setup_timeouts()

    return module.window


class FakeDeviceDropdown(Gtk.ComboBoxText):
    def __init__(self, group):
        if type(group) == str:
            group = groups.find(key=group)

        self.group = group

    def get_active_text(self):
        return self.group.name

    def get_active_id(self):
        return self.group.key

    def set_active_id(self, key):
        self.group = groups.find(key=key)


class FakePresetDropdown(Gtk.ComboBoxText):
    def __init__(self, name):
        self.name = name

    def get_active_text(self):
        return self.name

    def get_active_id(self):
        return self.name

    def set_active_id(self, name):
        self.name = name


def clean_up_integration(test):
    if hasattr(test, "original_on_close"):
        test.window.on_close = test.original_on_close

    test.window.on_restore_defaults_clicked(None)
    gtk_iteration()
    test.window.on_close()
    test.window.window.destroy()
    gtk_iteration()
    cleanup()

    # do this now, not when all tests are finished
    test.window.dbus.stop_all()
    if isinstance(test.window.dbus, Daemon):
        atexit.unregister(test.window.dbus.stop_all)


original_on_select_preset = Window.on_select_preset


class GtkKeyEvent:
    def __init__(self, keyval):
        self.keyval = keyval

    def get_keyval(self):
        return True, self.keyval


class TestGroupsFromHelper(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.injector = None
        cls.grab = evdev.InputDevice.grab

        # don't try to connect, return an object instance of it instead
        cls.original_connect = Daemon.connect
        Daemon.connect = Daemon

        cls.original_os_system = os.system

        def os_system(cmd):
            # instead of running pkexec, fork instead. This will make
            # the helper aware of all the test patches
            if "pkexec input-remapper-control --command helper" in cmd:
                # the forked process should get the initial groups
                groups.refresh()
                multiprocessing.Process(target=RootHelper).start()
                # the gui an empty dict, because it doesn't know any devices
                # without the help of the privileged helper
                groups.set_groups({})
                return 0

            return cls.original_os_system(cmd)

        os.system = os_system

    def setUp(self):
        self.window = launch()
        # verify that the ui doesn't have knowledge of any device yet
        print("test self.assertIsNone(self.window.group)")
        self.assertIsNone(self.window.group)
        self.assertEqual(len(groups), 0)

    def tearDown(self):
        clean_up_integration(self)

    @classmethod
    def tearDownClass(cls):
        os.system = cls.original_os_system
        Daemon.connect = cls.original_connect

    @patch("inputremapper.gui.window.Window.on_select_preset")
    def test_knows_devices(self, on_select_preset_patch):
        # verify that it is working as expected
        gtk_iteration()
        self.assertIsNone(self.window.group)
        self.assertIsNone(self.window.preset_name)
        self.assertEqual(len(groups), 0)
        on_select_preset_patch.assert_not_called()

        # perform some iterations so that the gui ends up running
        # consume_newest_keycode, which will make it receive devices.
        # Restore patch, otherwise gtk complains when disabling handlers
        Window.on_select_preset = original_on_select_preset
        for _ in range(10):
            time.sleep(0.01)
            gtk_iteration()

        self.assertIsNotNone(groups.find(key="Foo Device 2"))
        self.assertIsNotNone(groups.find(name="Bar Device"))
        self.assertIsNotNone(groups.find(name="gamepad"))
        self.assertEqual(self.window.group.name, "Foo Device")


class TestIntegration(unittest.TestCase):
    """For tests that use the window.

    Try to modify the configuration only by calling functions of the window.
    """

    @classmethod
    def setUpClass(cls):
        cls.injector = None
        cls.grab = evdev.InputDevice.grab

        def start_processes(self):
            """Avoid running pkexec which requires user input, and fork in
            order to pass the fixtures to the helper and daemon process.
            """
            multiprocessing.Process(target=RootHelper).start()
            self.dbus = Daemon()

        Window.start_processes = start_processes

    def setUp(self):
        self.window = launch()
        self.original_on_close = self.window.on_close

        self.grab_fails = False

        def grab(_):
            if self.grab_fails:
                raise OSError()

        evdev.InputDevice.grab = grab

        config.save_config()

    def tearDown(self):
        clean_up_integration(self)

    def get_rows(self):
        return self.window.get("key_list").get_children()

    def get_status_text(self):
        status_bar = self.window.get("status_bar")
        return status_bar.get_message_area().get_children()[0].get_label()

    def test_can_start(self):
        self.assertIsNotNone(self.window)
        self.assertTrue(self.window.window.get_visible())

    def test_ctrl_q(self):
        closed = False

        def on_close():
            nonlocal closed
            closed = True

        self.window.on_close = on_close

        self.window.key_press(self.window, GtkKeyEvent(Gdk.KEY_Control_L))
        self.window.key_press(self.window, GtkKeyEvent(Gdk.KEY_a))
        self.window.key_release(self.window, GtkKeyEvent(Gdk.KEY_Control_L))
        self.window.key_release(self.window, GtkKeyEvent(Gdk.KEY_a))
        self.window.key_press(self.window, GtkKeyEvent(Gdk.KEY_b))
        self.window.key_press(self.window, GtkKeyEvent(Gdk.KEY_q))
        self.window.key_release(self.window, GtkKeyEvent(Gdk.KEY_q))
        self.window.key_release(self.window, GtkKeyEvent(Gdk.KEY_b))
        self.assertFalse(closed)

        # while keys are being recorded no shortcut should work
        rows = self.get_rows()
        row = rows[-1]
        self.window.window.set_focus(row.keycode_input)
        self.window.key_press(self.window, GtkKeyEvent(Gdk.KEY_Control_L))
        self.window.key_press(self.window, GtkKeyEvent(Gdk.KEY_q))
        self.assertFalse(closed)

        self.window.window.set_focus(None)
        self.window.key_press(self.window, GtkKeyEvent(Gdk.KEY_Control_L))
        self.window.key_press(self.window, GtkKeyEvent(Gdk.KEY_q))
        self.assertTrue(closed)

        self.window.key_release(self.window, GtkKeyEvent(Gdk.KEY_Control_L))
        self.window.key_release(self.window, GtkKeyEvent(Gdk.KEY_q))

    def test_ctrl_r(self):
        with patch.object(reader, "refresh_groups") as reader_get_devices_patch:
            self.window.key_press(self.window, GtkKeyEvent(Gdk.KEY_Control_L))
            self.window.key_press(self.window, GtkKeyEvent(Gdk.KEY_r))
            reader_get_devices_patch.assert_called_once()

    def test_ctrl_del(self):
        with patch.object(self.window.dbus, "stop_injecting") as stop_injecting:
            self.window.key_press(self.window, GtkKeyEvent(Gdk.KEY_Control_L))
            self.window.key_press(self.window, GtkKeyEvent(Gdk.KEY_Delete))
            stop_injecting.assert_called_once()

    def test_show_device_mapping_status(self):
        # this function may not return True, otherwise the timeout
        # runs forever
        self.assertFalse(self.window.show_device_mapping_status())

    def test_autoload(self):
        with spy(self.window.dbus, "set_config_dir") as set_config_dir:
            self.window.on_autoload_switch(None, False)
            set_config_dir.assert_called_once()

        self.assertFalse(
            config.is_autoloaded(self.window.group.key, self.window.preset_name)
        )

        self.window.on_select_device(FakeDeviceDropdown("Foo Device 2"))
        gtk_iteration()
        self.assertFalse(self.window.get("preset_autoload_switch").get_active())

        # select a preset for the first device
        self.window.get("preset_autoload_switch").set_active(True)
        gtk_iteration()
        self.assertTrue(self.window.get("preset_autoload_switch").get_active())
        self.assertEqual(self.window.group.key, "Foo Device 2")
        self.assertEqual(self.window.group.name, "Foo Device")
        self.assertTrue(config.is_autoloaded(self.window.group.key, "new preset"))
        self.assertFalse(config.is_autoloaded("Bar Device", "new preset"))
        self.assertListEqual(
            list(config.iterate_autoload_presets()), [("Foo Device 2", "new preset")]
        )

        # create a new preset, the switch should be correctly off and the
        # config not changed.
        self.window.on_create_preset_clicked(None)
        gtk_iteration()
        self.assertEqual(self.window.preset_name, "new preset 2")
        self.assertFalse(self.window.get("preset_autoload_switch").get_active())
        self.assertTrue(config.is_autoloaded("Foo Device 2", "new preset"))
        self.assertFalse(config.is_autoloaded("Foo Device", "new preset"))
        self.assertFalse(config.is_autoloaded("Foo Device", "new preset 2"))
        self.assertFalse(config.is_autoloaded("Foo Device 2", "new preset 2"))

        # select a preset for the second device
        self.window.on_select_device(FakeDeviceDropdown("Bar Device"))
        self.window.get("preset_autoload_switch").set_active(True)
        gtk_iteration()
        self.assertTrue(config.is_autoloaded("Foo Device 2", "new preset"))
        self.assertFalse(config.is_autoloaded("Foo Device", "new preset"))
        self.assertTrue(config.is_autoloaded("Bar Device", "new preset"))
        self.assertListEqual(
            list(config.iterate_autoload_presets()),
            [("Foo Device 2", "new preset"), ("Bar Device", "new preset")],
        )

        # disable autoloading for the second device
        self.window.get("preset_autoload_switch").set_active(False)
        gtk_iteration()
        self.assertTrue(config.is_autoloaded("Foo Device 2", "new preset"))
        self.assertFalse(config.is_autoloaded("Foo Device", "new preset"))
        self.assertFalse(config.is_autoloaded("Bar Device", "new preset"))
        self.assertListEqual(
            list(config.iterate_autoload_presets()), [("Foo Device 2", "new preset")]
        )

    def test_select_device(self):
        # creates a new empty preset when no preset exists for the device
        self.window.on_select_device(FakeDeviceDropdown("Foo Device"))
        custom_mapping.change(Key(EV_KEY, 50, 1), "q")
        custom_mapping.change(Key(EV_KEY, 51, 1), "u")
        custom_mapping.change(Key(EV_KEY, 52, 1), "x")
        self.assertEqual(len(custom_mapping), 3)
        self.window.on_select_device(FakeDeviceDropdown("Bar Device"))
        self.assertEqual(len(custom_mapping), 0)
        # it creates the file for that right away. It may have been possible
        # to write it such that it doesn't (its empty anyway), but it does,
        # so use that to test it in more detail.
        path = get_preset_path("Bar Device", "new preset")
        self.assertTrue(os.path.exists(path))
        with open(path, "r") as file:
            preset = json.load(file)
            self.assertEqual(len(preset["mapping"]), 0)

    def test_permission_error_on_create_preset_clicked(self):
        def save(_=None):
            raise PermissionError

        with patch.object(custom_mapping, "save", save):
            self.window.on_create_preset_clicked(None)
            status = self.get_status_text()
            self.assertIn("Permission denied", status)

    def test_show_injection_result_failure(self):
        def get_state(_=None):
            return FAILED

        with patch.object(self.window.dbus, "get_state", get_state):
            self.window.show_injection_result()
            text = self.get_status_text()
            self.assertIn("Failed", text)

    def test_row_keycode_to_string(self):
        # not an integration test, but I have all the row tests here already
        self.assertEqual(to_string(Key(EV_KEY, evdev.ecodes.KEY_A, 1)), "a")
        self.assertEqual(
            to_string(Key(EV_ABS, evdev.ecodes.ABS_HAT0X, -1)), "DPad Left"
        )
        self.assertEqual(to_string(Key(EV_ABS, evdev.ecodes.ABS_HAT0Y, -1)), "DPad Up")
        self.assertEqual(to_string(Key(EV_KEY, evdev.ecodes.BTN_A, 1)), "Button A")
        self.assertEqual(to_string(Key(EV_KEY, 1234, 1)), "1234")
        self.assertEqual(
            to_string(Key(EV_ABS, evdev.ecodes.ABS_X, 1)), "Joystick Right"
        )
        self.assertEqual(
            to_string(Key(EV_ABS, evdev.ecodes.ABS_RY, 1)), "Joystick 2 Down"
        )
        self.assertEqual(
            to_string(Key(EV_REL, evdev.ecodes.REL_HWHEEL, 1)), "Wheel Right"
        )
        self.assertEqual(
            to_string(Key(EV_REL, evdev.ecodes.REL_WHEEL, -1)), "Wheel Down"
        )

        # combinations
        self.assertEqual(
            to_string(
                Key(
                    (EV_KEY, evdev.ecodes.BTN_A, 1),
                    (EV_KEY, evdev.ecodes.BTN_B, 1),
                    (EV_KEY, evdev.ecodes.BTN_C, 1),
                )
            ),
            "Button A + Button B + Button C",
        )

    def test_row_simple(self):
        rows = self.window.get("key_list").get_children()
        self.assertEqual(len(rows), 1)

        row = rows[0]

        row.set_new_key(None)
        self.assertIsNone(row.get_key())
        self.assertEqual(len(custom_mapping), 0)
        self.assertEqual(row.keycode_input.get_label(), "click here")

        row.set_new_key(Key(EV_KEY, 30, 1))
        self.assertEqual(len(custom_mapping), 0)
        self.assertEqual(row.get_key(), (EV_KEY, 30, 1))
        # this is KEY_A in linux/input-event-codes.h,
        # but KEY_ is removed from the text
        self.assertEqual(row.keycode_input.get_label(), "a")

        row.set_new_key(Key(EV_KEY, 30, 1))
        self.assertEqual(len(custom_mapping), 0)
        self.assertEqual(row.get_key(), (EV_KEY, 30, 1))

        time.sleep(0.1)
        gtk_iteration()
        self.assertEqual(len(self.window.get("key_list").get_children()), 1)

        row.symbol_input.set_text("Shift_L")
        self.assertEqual(len(custom_mapping), 1)

        time.sleep(0.1)
        gtk_iteration()
        self.assertEqual(len(self.window.get("key_list").get_children()), 2)

        self.assertEqual(custom_mapping.get_symbol(Key(EV_KEY, 30, 1)), "Shift_L")
        self.assertEqual(row.get_symbol(), "Shift_L")
        self.assertEqual(row.get_key(), (EV_KEY, 30, 1))

    def sleep(self, num_events):
        for _ in range(num_events * 2):
            time.sleep(EVENT_READ_TIMEOUT)
            gtk_iteration()

        time.sleep(1 / 30)  # one window iteration
        gtk_iteration()

    def test_row_not_focused(self):
        # focus anything that is not the row,
        # no keycode should be inserted into it
        self.window.window.set_focus(self.window.get("preset_name_input"))
        send_event_to_reader(new_event(1, 61, 1))
        self.window.consume_newest_keycode()

        rows = self.get_rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]

        # the empty row has this key not set
        self.assertIsNone(row.get_key())

        # focus the text input instead
        self.window.window.set_focus(row.symbol_input)
        send_event_to_reader(new_event(1, 61, 1))
        self.window.consume_newest_keycode()

        # still nothing set
        self.assertIsNone(row.get_key())

    def test_show_status(self):
        self.window.show_status(0, "a" * 100)
        text = self.get_status_text()
        self.assertIn("...", text)

        self.window.show_status(0, "b")
        text = self.get_status_text()
        self.assertNotIn("...", text)

    def change_empty_row(self, key, char, code_first=True, expect_success=True):
        """Modify the one empty row that always exists.

        Utility function for other tests.

        Parameters
        ----------
        key : Key or None
        code_first : boolean
            If True, the code is entered and then the symbol.
            If False, the symbol is entered first.
        expect_success : boolean
            If this change on the empty row is going to result in a change
            in the mapping eventually. False if this change is going to
            cause a duplicate.
        """
        self.assertIsNone(reader.get_unreleased_keys())

        changed = custom_mapping.changed

        # wait for the window to create a new empty row if needed
        time.sleep(0.1)
        gtk_iteration()

        # find the empty row
        rows = self.get_rows()
        row = rows[-1]
        self.assertIsNone(row.get_key())
        self.assertEqual(row.symbol_input.get_text(), "")
        self.assertEqual(row._state, IDLE)

        if char and not code_first:
            # set the symbol to make the new row complete
            self.assertIsNone(row.get_symbol())
            row.symbol_input.set_text(char)
            self.assertEqual(row.get_symbol(), char)

        if row.keycode_input.is_focus():
            self.assertEqual(row.keycode_input.get_label(), "press key")
        else:
            self.assertEqual(row.keycode_input.get_label(), "click here")

        self.window.window.set_focus(row.keycode_input)
        gtk_iteration()
        gtk_iteration()
        self.assertIsNone(row.get_key())
        self.assertEqual(row.keycode_input.get_label(), "press key")

        if key:
            # modifies the keycode in the row not by writing into the input,
            # but by sending an event. press down all the keys of a combination
            for sub_key in key:

                send_event_to_reader(new_event(*sub_key))
                # this will be consumed all at once, since no gt_iteration
                # is done

            # make the window consume the keycode
            self.sleep(len(key))

            # holding down
            self.assertIsNotNone(reader.get_unreleased_keys())
            self.assertGreater(len(reader.get_unreleased_keys()), 0)
            self.assertEqual(row._state, HOLDING)
            self.assertTrue(row.keycode_input.is_focus())

            # release all the keys
            for sub_key in key:
                send_event_to_reader(new_event(*sub_key[:2], 0))

            # wait for the window to consume the keycode
            self.sleep(len(key))

            # released
            self.assertIsNone(reader.get_unreleased_keys())
            self.assertEqual(row._state, IDLE)

            if expect_success:
                self.assertEqual(row.get_key(), key)
                self.assertEqual(row.keycode_input.get_label(), to_string(key))
                self.assertFalse(row.keycode_input.is_focus())
                self.assertEqual(len(reader._unreleased), 0)

        if not expect_success:
            self.assertIsNone(row.get_key())
            self.assertIsNone(row.get_symbol())
            self.assertEqual(row._state, IDLE)
            # it won't switch the focus to the symbol input
            self.assertTrue(row.keycode_input.is_focus())
            self.assertEqual(custom_mapping.changed, changed)
            return row

        if char and code_first:
            # set the symbol to make the new row complete
            self.assertIsNone(row.get_symbol())
            row.symbol_input.set_text(char)
            self.assertEqual(row.get_symbol(), char)

        # unfocus them to trigger some final logic
        self.window.window.set_focus(None)
        correct_case = system_mapping.correct_case(char)
        self.assertEqual(row.get_symbol(), correct_case)
        self.assertFalse(custom_mapping.changed)

        return row

    def test_clears_unreleased_on_focus_change(self):
        ev_1 = Key(EV_KEY, 41, 1)

        # focus
        self.window.window.set_focus(self.get_rows()[0].keycode_input)
        send_event_to_reader(new_event(*ev_1.keys[0]))
        reader.read()
        self.assertEqual(reader.get_unreleased_keys(), ev_1)

        # unfocus
        # doesn't call reader.clear
        # because otherwise the super key cannot be mapped
        self.window.window.set_focus(None)
        self.assertEqual(reader.get_unreleased_keys(), ev_1)

        # focus different row
        self.window.add_empty()
        self.window.window.set_focus(self.get_rows()[1].keycode_input)
        self.assertEqual(reader.get_unreleased_keys(), None)

    def test_rows(self):
        """Comprehensive test for rows."""
        system_mapping.clear()
        system_mapping._set("Foo_BAR", 41)
        system_mapping._set("B", 42)
        system_mapping._set("c", 43)
        system_mapping._set("d", 44)

        # how many rows there should be in the end
        num_rows_target = 3

        ev_1 = Key(EV_KEY, 10, 1)
        ev_2 = Key(EV_ABS, evdev.ecodes.ABS_HAT0X, -1)

        """edit"""

        # add two rows by modifiying the one empty row that exists.
        # Insert lowercase, it should be corrected to uppercase as stored
        # in system_mapping
        self.change_empty_row(ev_1, "foo_bar", code_first=False)
        self.change_empty_row(ev_2, "k(b).k(c)")

        # one empty row added automatically again
        time.sleep(0.1)
        gtk_iteration()
        self.assertEqual(len(self.get_rows()), num_rows_target)

        self.assertEqual(custom_mapping.get_symbol(ev_1), "Foo_BAR")
        self.assertEqual(custom_mapping.get_symbol(ev_2), "k(b).k(c)")

        """edit first row"""

        row = self.get_rows()[0]
        row.symbol_input.set_text("c")

        self.assertEqual(custom_mapping.get_symbol(ev_1), "c")
        self.assertEqual(custom_mapping.get_symbol(ev_2), "k(b).k(c)")
        self.assertTrue(custom_mapping.changed)

        """add duplicate"""

        # try to add a duplicate keycode, it should be ignored
        self.change_empty_row(ev_2, "d", expect_success=False)
        self.assertEqual(custom_mapping.get_symbol(ev_2), "k(b).k(c)")
        # and the number of rows shouldn't change
        self.assertEqual(len(self.get_rows()), num_rows_target)

    def test_hat0x(self):
        # it should be possible to add all of them
        ev_1 = Key(EV_ABS, evdev.ecodes.ABS_HAT0X, -1)
        ev_2 = Key(EV_ABS, evdev.ecodes.ABS_HAT0X, 1)
        ev_3 = Key(EV_ABS, evdev.ecodes.ABS_HAT0Y, -1)
        ev_4 = Key(EV_ABS, evdev.ecodes.ABS_HAT0Y, 1)

        self.change_empty_row(ev_1, "a")
        self.change_empty_row(ev_2, "b")
        self.change_empty_row(ev_3, "c")
        self.change_empty_row(ev_4, "d")

        self.assertEqual(custom_mapping.get_symbol(ev_1), "a")
        self.assertEqual(custom_mapping.get_symbol(ev_2), "b")
        self.assertEqual(custom_mapping.get_symbol(ev_3), "c")
        self.assertEqual(custom_mapping.get_symbol(ev_4), "d")

        # and trying to add them as duplicate rows will be ignored for each
        # of them
        self.change_empty_row(ev_1, "e", expect_success=False)
        self.change_empty_row(ev_2, "f", expect_success=False)
        self.change_empty_row(ev_3, "g", expect_success=False)
        self.change_empty_row(ev_4, "h", expect_success=False)

        self.assertEqual(custom_mapping.get_symbol(ev_1), "a")
        self.assertEqual(custom_mapping.get_symbol(ev_2), "b")
        self.assertEqual(custom_mapping.get_symbol(ev_3), "c")
        self.assertEqual(custom_mapping.get_symbol(ev_4), "d")

    def test_combination(self):
        # it should be possible to write a key combination
        ev_1 = Key(EV_KEY, evdev.ecodes.KEY_A, 1)
        ev_2 = Key(EV_ABS, evdev.ecodes.ABS_HAT0X, 1)
        ev_3 = Key(EV_KEY, evdev.ecodes.KEY_C, 1)
        ev_4 = Key(EV_ABS, evdev.ecodes.ABS_HAT0X, -1)
        combination_1 = Key(ev_1, ev_2, ev_3)
        combination_2 = Key(ev_2, ev_1, ev_3)

        # same as 1, but different D-Pad direction
        combination_3 = Key(ev_1, ev_4, ev_3)
        combination_4 = Key(ev_4, ev_1, ev_3)

        # same as 1, but the last key is different
        combination_5 = Key(ev_1, ev_3, ev_2)
        combination_6 = Key(ev_3, ev_1, ev_2)

        self.change_empty_row(combination_1, "a")
        self.assertEqual(custom_mapping.get_symbol(combination_1), "a")
        self.assertEqual(custom_mapping.get_symbol(combination_2), "a")
        self.assertIsNone(custom_mapping.get_symbol(combination_3))
        self.assertIsNone(custom_mapping.get_symbol(combination_4))
        self.assertIsNone(custom_mapping.get_symbol(combination_5))
        self.assertIsNone(custom_mapping.get_symbol(combination_6))

        # it won't write the same combination again, even if the
        # first two events are in a different order
        self.change_empty_row(combination_2, "b", expect_success=False)
        self.assertEqual(custom_mapping.get_symbol(combination_1), "a")
        self.assertEqual(custom_mapping.get_symbol(combination_2), "a")
        self.assertIsNone(custom_mapping.get_symbol(combination_3))
        self.assertIsNone(custom_mapping.get_symbol(combination_4))
        self.assertIsNone(custom_mapping.get_symbol(combination_5))
        self.assertIsNone(custom_mapping.get_symbol(combination_6))

        self.change_empty_row(combination_3, "c")
        self.assertEqual(custom_mapping.get_symbol(combination_1), "a")
        self.assertEqual(custom_mapping.get_symbol(combination_2), "a")
        self.assertEqual(custom_mapping.get_symbol(combination_3), "c")
        self.assertEqual(custom_mapping.get_symbol(combination_4), "c")
        self.assertIsNone(custom_mapping.get_symbol(combination_5))
        self.assertIsNone(custom_mapping.get_symbol(combination_6))

        # same as with combination_2, the existing combination_3 blocks
        # combination_4 because they have the same keys and end in the
        # same key.
        self.change_empty_row(combination_4, "d", expect_success=False)
        self.assertEqual(custom_mapping.get_symbol(combination_1), "a")
        self.assertEqual(custom_mapping.get_symbol(combination_2), "a")
        self.assertEqual(custom_mapping.get_symbol(combination_3), "c")
        self.assertEqual(custom_mapping.get_symbol(combination_4), "c")
        self.assertIsNone(custom_mapping.get_symbol(combination_5))
        self.assertIsNone(custom_mapping.get_symbol(combination_6))

        self.change_empty_row(combination_5, "e")
        self.assertEqual(custom_mapping.get_symbol(combination_1), "a")
        self.assertEqual(custom_mapping.get_symbol(combination_2), "a")
        self.assertEqual(custom_mapping.get_symbol(combination_3), "c")
        self.assertEqual(custom_mapping.get_symbol(combination_4), "c")
        self.assertEqual(custom_mapping.get_symbol(combination_5), "e")
        self.assertEqual(custom_mapping.get_symbol(combination_6), "e")

        error_icon = self.window.get("error_status_icon")
        warning_icon = self.window.get("warning_status_icon")

        self.assertFalse(error_icon.get_visible())
        self.assertFalse(warning_icon.get_visible())

    def test_remove_row(self):
        """Comprehensive test for rows 2."""
        # sleeps are added to be able to visually follow and debug the test.
        # add two rows by modifiying the one empty row that exists
        row_1 = self.change_empty_row(Key(EV_KEY, 10, 1), "a")
        row_2 = self.change_empty_row(Key(EV_KEY, 11, 1), "b")
        row_3 = self.change_empty_row(None, "c")

        # no empty row added because one is unfinished
        time.sleep(0.2)
        gtk_iteration()
        self.assertEqual(len(self.get_rows()), 3)

        self.assertEqual(custom_mapping.get_symbol(Key(EV_KEY, 11, 1)), "b")

        def remove(row, code, char, num_rows_after):
            """Remove a row by clicking the delete button.

            Parameters
            ----------
            row : Row
            code : int or None
                keycode of the mapping that is displayed by this row
            char : string or None
                ouptut of the mapping that is displayed by this row
            num_rows_after : int
                after deleting, how many rows are expected to still be there
            """
            if code is not None and char is not None:
                self.assertEqual(custom_mapping.get_symbol(Key(EV_KEY, code, 1)), char)

            self.assertEqual(row.get_symbol(), char)
            if code is None:
                self.assertIsNone(row.get_key())
            else:
                self.assertEqual(row.get_key(), Key(EV_KEY, code, 1))

            row.on_delete_button_clicked()
            time.sleep(0.2)
            gtk_iteration()

            # if a reference to the row is held somewhere and it is
            # accidentally used again, make sure to not provide any outdated
            # information that is supposed to be deleted
            self.assertIsNone(row.get_key())
            self.assertIsNone(row.get_symbol())
            if code is not None:
                self.assertIsNone(custom_mapping.get_symbol(Key(EV_KEY, code, 1)))
            self.assertEqual(len(self.get_rows()), num_rows_after)

        remove(row_1, 10, "a", 2)
        remove(row_2, 11, "b", 1)
        # there is no empty row at the moment, so after removing that one,
        # which is the only row, one empty row will be there. So the number
        # of rows won't change.
        remove(row_3, None, "c", 1)

    def test_problematic_combination(self):
        combination = Key((EV_KEY, KEY_LEFTSHIFT, 1), (EV_KEY, 82, 1))
        self.change_empty_row(combination, "b")
        text = self.get_status_text()
        self.assertIn("shift", text)

        error_icon = self.window.get("error_status_icon")
        warning_icon = self.window.get("warning_status_icon")

        self.assertFalse(error_icon.get_visible())
        self.assertTrue(warning_icon.get_visible())

    def test_rename_and_save(self):
        self.assertEqual(self.window.group.name, "Foo Device")
        self.assertFalse(config.is_autoloaded("Foo Device", "new preset"))

        custom_mapping.change(Key(EV_KEY, 14, 1), "a", None)
        self.assertEqual(self.window.preset_name, "new preset")
        self.window.save_preset()
        self.assertEqual(custom_mapping.get_symbol(Key(EV_KEY, 14, 1)), "a")
        config.set_autoload_preset("Foo Device", "new preset")
        self.assertTrue(config.is_autoloaded("Foo Device", "new preset"))

        custom_mapping.change(Key(EV_KEY, 14, 1), "b", None)
        self.window.get("preset_name_input").set_text("asdf")
        self.window.save_preset()
        self.window.on_rename_button_clicked(None)
        self.assertEqual(self.window.preset_name, "asdf")
        preset_path = f"{CONFIG_PATH}/presets/Foo Device/asdf.json"
        self.assertTrue(os.path.exists(preset_path))
        self.assertEqual(custom_mapping.get_symbol(Key(EV_KEY, 14, 1)), "b")

        # after renaming the preset it is still set to autoload
        self.assertTrue(config.is_autoloaded("Foo Device", "asdf"))
        # ALSO IN THE ACTUAL CONFIG FILE!
        config.load_config()
        self.assertTrue(config.is_autoloaded("Foo Device", "asdf"))

        error_icon = self.window.get("error_status_icon")
        self.assertFalse(error_icon.get_visible())

        # otherwise save won't do anything
        custom_mapping.change(Key(EV_KEY, 14, 1), "c", None)
        self.assertTrue(custom_mapping.changed)

        def save(_):
            raise PermissionError

        with patch.object(custom_mapping, "save", save):
            self.window.save_preset()
            status = self.get_status_text()
            self.assertIn("Permission denied", status)

        with patch.object(
            self.window, "show_confirm_delete", lambda: Gtk.ResponseType.ACCEPT
        ):
            self.window.on_delete_preset_clicked(None)
            self.assertFalse(os.path.exists(preset_path))

    def test_rename_create_switch(self):
        # after renaming a preset and saving it, new presets
        # start with "new preset" again
        custom_mapping.change(Key(EV_KEY, 14, 1), "a", None)
        self.window.get("preset_name_input").set_text("asdf")
        self.window.save_preset()
        self.window.on_rename_button_clicked(None)
        self.assertEqual(len(custom_mapping), 1)
        self.assertEqual(self.window.preset_name, "asdf")

        self.window.on_create_preset_clicked(None)
        self.assertEqual(self.window.preset_name, "new preset")
        self.assertIsNone(custom_mapping.get_symbol(Key(EV_KEY, 14, 1)))
        self.window.save_preset()

        # selecting the first one again loads the saved mapping
        self.window.on_select_preset(FakePresetDropdown("asdf"))
        self.assertEqual(custom_mapping.get_symbol(Key(EV_KEY, 14, 1)), "a")
        config.set_autoload_preset("Foo Device", "new preset")

        # renaming a preset to an existing name appends a number
        self.window.on_select_preset(FakePresetDropdown("new preset"))
        self.window.get("preset_name_input").set_text("asdf")
        self.window.on_rename_button_clicked(None)
        self.assertEqual(self.window.preset_name, "asdf 2")
        # and that added number is correctly used in the autoload
        # configuration as well
        self.assertTrue(config.is_autoloaded("Foo Device", "asdf 2"))

        self.assertEqual(self.window.get("preset_name_input").get_text(), "")

        # renaming the current preset to itself doesn't append a number and
        # it doesn't do anything on the file system
        def _raise(*_):
            # should not get called
            raise AssertionError

        with patch.object(os, "rename", _raise):
            self.window.get("preset_name_input").set_text("asdf 2")
            self.window.on_rename_button_clicked(None)
            self.assertEqual(self.window.preset_name, "asdf 2")

            self.window.get("preset_name_input").set_text("")
            self.window.on_rename_button_clicked(None)
            self.assertEqual(self.window.preset_name, "asdf 2")

    def test_avoids_redundant_saves(self):
        custom_mapping.change(Key(EV_KEY, 14, 1), "abcd", None)

        custom_mapping.changed = False
        self.window.save_preset()

        with open(get_preset_path("Foo Device", "new preset")) as f:
            content = f.read()
            self.assertNotIn("abcd", content)

        custom_mapping.changed = True
        self.window.save_preset()

        with open(get_preset_path("Foo Device", "new preset")) as f:
            content = f.read()
            self.assertIn("abcd", content)

    def test_check_for_unknown_symbols(self):
        status = self.window.get("status_bar")
        error_icon = self.window.get("error_status_icon")
        warning_icon = self.window.get("warning_status_icon")

        custom_mapping.change(Key(EV_KEY, 71, 1), "qux", None)
        custom_mapping.change(Key(EV_KEY, 72, 1), "foo", None)
        self.window.save_preset()
        tooltip = status.get_tooltip_text().lower()
        self.assertIn("qux", tooltip)
        self.assertTrue(error_icon.get_visible())
        self.assertFalse(warning_icon.get_visible())

        # it will still save it though
        with open(get_preset_path("Foo Device", "new preset")) as f:
            content = f.read()
            self.assertIn("qux", content)
            self.assertIn("foo", content)

        custom_mapping.change(Key(EV_KEY, 71, 1), "a", None)
        self.window.save_preset()
        tooltip = status.get_tooltip_text().lower()
        self.assertIn("foo", tooltip)
        self.assertTrue(error_icon.get_visible())
        self.assertFalse(warning_icon.get_visible())

        custom_mapping.change(Key(EV_KEY, 72, 1), "b", None)
        self.window.save_preset()
        tooltip = status.get_tooltip_text()
        self.assertIsNone(tooltip)
        self.assertFalse(error_icon.get_visible())
        self.assertFalse(warning_icon.get_visible())

    def test_check_macro_syntax(self):
        status = self.window.get("status_bar")
        error_icon = self.window.get("error_status_icon")
        warning_icon = self.window.get("warning_status_icon")

        custom_mapping.change(Key(EV_KEY, 9, 1), "k(1))", None)
        self.window.save_preset()
        tooltip = status.get_tooltip_text().lower()
        self.assertIn("brackets", tooltip)
        self.assertTrue(error_icon.get_visible())
        self.assertFalse(warning_icon.get_visible())

        custom_mapping.change(Key(EV_KEY, 9, 1), "k(1)", None)
        self.window.save_preset()
        tooltip = (status.get_tooltip_text() or "").lower()
        self.assertNotIn("brackets", tooltip)
        self.assertFalse(error_icon.get_visible())
        self.assertFalse(warning_icon.get_visible())

        self.assertEqual(custom_mapping.get_symbol(Key(EV_KEY, 9, 1)), "k(1)")

    def test_select_device_and_preset(self):
        # created on start because the first device is selected and some empty
        # preset prepared.
        self.assertTrue(
            os.path.exists(f"{CONFIG_PATH}/presets/Foo Device/new preset.json")
        )
        self.assertEqual(self.window.group.name, "Foo Device")
        self.assertEqual(self.window.preset_name, "new preset")

        # create another one
        self.window.on_create_preset_clicked(None)
        gtk_iteration()
        self.assertTrue(
            os.path.exists(f"{CONFIG_PATH}/presets/Foo Device/new preset.json")
        )
        self.assertTrue(
            os.path.exists(f"{CONFIG_PATH}/presets/Foo Device/new preset 2.json")
        )
        self.assertEqual(self.window.preset_name, "new preset 2")

        self.window.on_select_preset(FakePresetDropdown("new preset"))
        gtk_iteration()
        self.assertEqual(self.window.preset_name, "new preset")

        self.assertListEqual(
            sorted(os.listdir(f"{CONFIG_PATH}/presets/Foo Device")),
            sorted(["new preset.json", "new preset 2.json"]),
        )

        # now try to change the name
        self.window.get("preset_name_input").set_text("abc 123")
        gtk_iteration()
        self.assertEqual(self.window.preset_name, "new preset")
        self.assertFalse(
            os.path.exists(f"{CONFIG_PATH}/presets/Foo Device/abc 123.json")
        )
        custom_mapping.change(Key(EV_KEY, 10, 1), "1", None)
        self.window.save_preset()
        self.window.on_rename_button_clicked(None)
        gtk_iteration()
        self.assertEqual(self.window.preset_name, "abc 123")
        self.assertTrue(
            os.path.exists(f"{CONFIG_PATH}/presets/Foo Device/abc 123.json")
        )
        self.assertListEqual(
            sorted(os.listdir(os.path.join(CONFIG_PATH, "presets"))),
            sorted(["Foo Device"]),
        )
        self.assertListEqual(
            sorted(os.listdir(f"{CONFIG_PATH}/presets/Foo Device")),
            sorted(["abc 123.json", "new preset 2.json"]),
        )

    def test_copy_preset(self):
        key_list = self.window.get("key_list")
        self.change_empty_row(Key(EV_KEY, 81, 1), "a")
        time.sleep(0.1)
        gtk_iteration()
        self.window.save_preset()
        self.assertEqual(len(key_list.get_children()), 2)

        # should be cleared when creating a new preset
        custom_mapping.set("a.b", 3)
        self.assertEqual(custom_mapping.get("a.b"), 3)

        self.window.on_create_preset_clicked(None)

        # the preset should be empty, only one empty row present
        self.assertEqual(len(key_list.get_children()), 1)
        self.assertIsNone(custom_mapping.get("a.b"), 3)

        # add one new row again and a setting
        self.change_empty_row(Key(EV_KEY, 81, 1), "b")
        time.sleep(0.1)
        gtk_iteration()
        self.window.save_preset()
        self.assertEqual(len(key_list.get_children()), 2)
        custom_mapping.set(["foo", "bar"], 2)

        # this time it should be copied
        self.window.on_copy_preset_clicked(None)
        self.assertEqual(self.window.preset_name, "new preset 2 copy")
        self.assertEqual(len(key_list.get_children()), 2)
        self.assertEqual(key_list.get_children()[0].get_symbol(), "b")
        self.assertEqual(custom_mapping.get(["foo", "bar"]), 2)

        # make another copy
        self.window.on_copy_preset_clicked(None)
        self.assertEqual(self.window.preset_name, "new preset 2 copy 2")
        self.assertEqual(len(key_list.get_children()), 2)
        self.assertEqual(key_list.get_children()[0].get_symbol(), "b")
        self.assertEqual(len(custom_mapping), 1)
        self.assertEqual(custom_mapping.get("foo.bar"), 2)

    def test_gamepad_config(self):
        # set some stuff in the beginning, otherwise gtk fails to
        # do handler_unblock_by_func, which makes no sense at all.
        # but it ONLY fails on right_joystick_purpose for some reason,
        # unblocking the left one works just fine. I should open a bug report
        # on gtk or something probably.
        self.window.get("left_joystick_purpose").set_active_id(BUTTONS)
        self.window.get("right_joystick_purpose").set_active_id(BUTTONS)
        self.window.get("joystick_mouse_speed").set_value(1)
        custom_mapping.changed = False

        # select a device that is not a gamepad
        self.window.on_select_device(FakeDeviceDropdown("Foo Device"))
        self.assertFalse(self.window.get("gamepad_config").is_visible())
        self.assertFalse(custom_mapping.changed)

        # select a gamepad
        self.window.on_select_device(FakeDeviceDropdown("gamepad"))
        self.assertTrue(self.window.get("gamepad_config").is_visible())
        self.assertFalse(custom_mapping.changed)

        # set stuff
        gtk_iteration()
        self.window.get("left_joystick_purpose").set_active_id(WHEEL)
        self.window.get("right_joystick_purpose").set_active_id(WHEEL)
        joystick_mouse_speed = 5
        self.window.get("joystick_mouse_speed").set_value(joystick_mouse_speed)

        # it should be stored in custom_mapping, which overwrites the
        # global config
        config.set("gamepad.joystick.left_purpose", MOUSE)
        config.set("gamepad.joystick.right_purpose", MOUSE)
        config.set("gamepad.joystick.pointer_speed", 50)
        self.assertTrue(custom_mapping.changed)
        left_purpose = custom_mapping.get("gamepad.joystick.left_purpose")
        right_purpose = custom_mapping.get("gamepad.joystick.right_purpose")
        pointer_speed = custom_mapping.get("gamepad.joystick.pointer_speed")
        self.assertEqual(left_purpose, WHEEL)
        self.assertEqual(right_purpose, WHEEL)
        self.assertEqual(pointer_speed, 2 ** joystick_mouse_speed)

        # select a device that is not a gamepad again
        self.window.on_select_device(FakeDeviceDropdown("Foo Device"))
        self.assertFalse(self.window.get("gamepad_config").is_visible())
        self.assertFalse(custom_mapping.changed)

    def test_wont_start(self):
        error_icon = self.window.get("error_status_icon")
        preset_name = "foo preset"
        group_name = "Bar Device"
        self.window.preset_name = preset_name
        self.window.group = groups.find(name=group_name)

        # empty

        custom_mapping.empty()
        self.window.save_preset()
        self.window.on_apply_preset_clicked(None)
        text = self.get_status_text()
        self.assertIn("add keys", text)
        self.assertTrue(error_icon.get_visible())
        self.assertNotEqual(self.window.dbus.get_state(self.window.group.key), RUNNING)

        # not empty, but keys are held down

        custom_mapping.change(Key(EV_KEY, KEY_A, 1), "a")
        self.window.save_preset()
        send_event_to_reader(new_event(EV_KEY, KEY_A, 1))
        reader.read()
        self.assertEqual(len(reader._unreleased), 1)
        self.assertFalse(self.window.unreleased_warn)
        self.window.on_apply_preset_clicked(None)
        text = self.get_status_text()
        self.assertIn("release", text)
        self.assertTrue(error_icon.get_visible())
        self.assertNotEqual(self.window.dbus.get_state(self.window.group.key), RUNNING)
        self.assertTrue(self.window.unreleased_warn)
        self.assertEqual(self.window.get("apply_system_layout").get_opacity(), 0.4)

        # device grabbing fails

        def wait():
            """Wait for the injector process to finish doing stuff."""
            for _ in range(10):
                time.sleep(0.1)
                gtk_iteration()
                if "Starting" not in self.get_status_text():
                    return

        for i in range(2):
            # just pressing apply again will overwrite the previous error
            self.grab_fails = True
            self.window.on_apply_preset_clicked(None)
            self.assertFalse(self.window.unreleased_warn)
            text = self.get_status_text()
            # it takes a little bit of time
            self.assertIn("Starting injection", text)
            self.assertFalse(error_icon.get_visible())
            wait()
            text = self.get_status_text()
            self.assertIn("not grabbed", text)
            self.assertTrue(error_icon.get_visible())
            self.assertNotEqual(
                self.window.dbus.get_state(self.window.group.key), RUNNING
            )

            # for the second try, release the key. that should also work
            send_event_to_reader(new_event(EV_KEY, KEY_A, 0))
            reader.read()
            self.assertEqual(len(reader._unreleased), 0)

        # this time work properly

        self.grab_fails = False
        custom_mapping.save(get_preset_path(group_name, preset_name))
        self.window.on_apply_preset_clicked(None)
        text = self.get_status_text()
        self.assertIn("Starting injection", text)
        self.assertFalse(error_icon.get_visible())
        wait()
        text = self.get_status_text()
        self.assertIn("Applied", text)
        text = self.get_status_text()
        self.assertNotIn("CTRL + DEL", text)  # only shown if btn_left mapped
        self.assertFalse(error_icon.get_visible())
        self.assertEqual(self.window.dbus.get_state(self.window.group.key), RUNNING)

        # because this test managed to reproduce some minor bug:
        self.assertNotIn("mapping", custom_mapping._config)

    def test_wont_start_2(self):
        preset_name = "foo preset"
        group_name = "Bar Device"
        self.window.preset_name = preset_name
        self.window.group = groups.find(name=group_name)

        def wait():
            """Wait for the injector process to finish doing stuff."""
            for _ in range(10):
                time.sleep(0.1)
                gtk_iteration()
                if "Starting" not in self.get_status_text():
                    return

        # btn_left mapped
        custom_mapping.change(Key.btn_left(), "a")
        self.window.save_preset()

        # and key held down
        send_event_to_reader(new_event(EV_KEY, KEY_A, 1))
        reader.read()
        self.assertEqual(len(reader._unreleased), 1)
        self.assertFalse(self.window.unreleased_warn)

        # first apply, shows btn_left warning
        self.window.on_apply_preset_clicked(None)
        text = self.get_status_text()
        self.assertIn("click", text)
        self.assertEqual(self.window.dbus.get_state(self.window.group.key), UNKNOWN)

        # second apply, shows unreleased warning
        self.window.on_apply_preset_clicked(None)
        text = self.get_status_text()
        self.assertIn("release", text)
        self.assertEqual(self.window.dbus.get_state(self.window.group.key), UNKNOWN)

        # third apply, overwrites both warnings
        self.window.on_apply_preset_clicked(None)
        wait()
        self.assertEqual(self.window.dbus.get_state(self.window.group.key), RUNNING)
        text = self.get_status_text()
        # because btn_left is mapped, shows help on how to stop
        # injecting via the keyboard
        self.assertIn("CTRL + DEL", text)

    def test_can_modify_mapping(self):
        preset_name = "foo preset"
        group_name = "Bar Device"
        self.window.preset_name = preset_name
        self.window.group = groups.find(name=group_name)

        self.assertNotEqual(self.window.dbus.get_state(self.window.group.key), RUNNING)
        self.window.can_modify_mapping()
        text = self.get_status_text()
        self.assertNotIn("Restore Defaults", text)

        custom_mapping.change(Key(EV_KEY, KEY_A, 1), "b")
        custom_mapping.save(get_preset_path(group_name, preset_name))
        self.window.on_apply_preset_clicked(None)

        # wait for the injector to start
        for _ in range(10):
            time.sleep(0.1)
            gtk_iteration()
            if "Starting" not in self.get_status_text():
                return

        self.assertEqual(self.window.dbus.get_state(self.window.group.key), RUNNING)

        # the mapping cannot be changed anymore
        self.window.can_modify_mapping()
        text = self.get_status_text()
        self.assertIn("Restore Defaults", text)

    def test_start_injecting(self):
        keycode_from = 9
        keycode_to = 200

        self.change_empty_row(Key(EV_KEY, keycode_from, 1), "a")
        system_mapping.clear()
        system_mapping._set("a", keycode_to)

        push_events(
            "Foo Device 2",
            [
                new_event(evdev.events.EV_KEY, keycode_from, 1),
                new_event(evdev.events.EV_KEY, keycode_from, 0),
            ],
        )

        # injecting for group.key will look at paths containing group.name
        custom_mapping.save(get_preset_path("Foo Device", "foo preset"))

        # use only the manipulated system_mapping
        if os.path.exists(os.path.join(tmp, XMODMAP_FILENAME)):
            os.remove(os.path.join(tmp, XMODMAP_FILENAME))

        # select the second Foo device
        self.window.group = groups.find(key="Foo Device 2")

        with spy(self.window.dbus, "set_config_dir") as spy1:
            self.window.preset_name = "foo preset"

            with spy(self.window.dbus, "start_injecting") as spy2:
                self.window.on_apply_preset_clicked(None)
                # correctly uses group.key, not group.name
                spy2.assert_called_once_with("Foo Device 2", "foo preset")

            spy1.assert_called_once_with(get_config_path())

        # the integration tests will cause the injection to be started as
        # processes, as intended. Luckily, recv will block until the events
        # are handled and pushed.

        # Note, that appending events to pending_events won't work anymore
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

        # the input-remapper device will not be shown
        groups.refresh()
        self.window.populate_devices()
        for entry in self.window.device_store:
            # whichever attribute contains "input-remapper"
            self.assertNotIn("input-remapper", "".join(entry))

    def test_gamepad_purpose_mouse_and_button(self):
        self.window.on_select_device(FakeDeviceDropdown("gamepad"))
        self.window.get("right_joystick_purpose").set_active_id(MOUSE)
        self.window.get("left_joystick_purpose").set_active_id(BUTTONS)
        self.window.get("joystick_mouse_speed").set_value(6)
        gtk_iteration()
        speed = custom_mapping.get("gamepad.joystick.pointer_speed")
        custom_mapping.set("gamepad.joystick.non_linearity", 1)
        self.assertEqual(speed, 2 ** 6)

        # don't consume the events in the reader, they are used to test
        # the injection
        reader.terminate()
        time.sleep(0.1)

        push_events(
            "gamepad",
            [new_event(EV_ABS, ABS_RX, MIN_ABS), new_event(EV_ABS, ABS_X, MAX_ABS)]
            * 100,
        )

        custom_mapping.change(Key(EV_ABS, ABS_X, 1), "a")
        self.window.save_preset()

        gtk_iteration()

        self.window.on_apply_preset_clicked(None)
        time.sleep(0.3)

        history = []
        while uinput_write_history_pipe[0].poll():
            history.append(uinput_write_history_pipe[0].recv().t)

        count_mouse = history.count((EV_REL, REL_X, -speed))
        count_button = history.count((EV_KEY, KEY_A, 1))
        self.assertGreater(count_mouse, 1)
        self.assertEqual(count_button, 1)
        self.assertEqual(count_button + count_mouse, len(history))

        self.assertIn("gamepad", self.window.dbus.injectors)

    def test_stop_injecting(self):
        keycode_from = 16
        keycode_to = 90

        self.change_empty_row(Key(EV_KEY, keycode_from, 1), "t")
        system_mapping.clear()
        system_mapping._set("t", keycode_to)

        # not all of those events should be processed, since that takes some
        # time due to time.sleep in the fakes and the injection is stopped.
        push_events("Bar Device", [new_event(1, keycode_from, 1)] * 100)

        custom_mapping.save(get_preset_path("Bar Device", "foo preset"))

        self.window.group = groups.find(name="Bar Device")
        self.window.preset_name = "foo preset"
        self.window.on_apply_preset_clicked(None)

        pipe = uinput_write_history_pipe[0]
        # block until the first event is available, indicating that
        # the injector is ready
        write_history = [pipe.recv()]

        # stop
        self.window.on_restore_defaults_clicked(None)

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

    def test_delete_preset(self):
        custom_mapping.change(Key(EV_KEY, 71, 1), "a", None)
        self.window.get("preset_name_input").set_text("asdf")
        self.window.on_rename_button_clicked(None)
        gtk_iteration()
        self.assertEqual(self.window.preset_name, "asdf")
        self.assertEqual(len(custom_mapping), 1)
        self.window.save_preset()
        self.assertTrue(os.path.exists(get_preset_path("Foo Device", "asdf")))

        with patch.object(
            self.window, "show_confirm_delete", lambda: Gtk.ResponseType.CANCEL
        ):
            self.window.on_delete_preset_clicked(None)
            self.assertTrue(os.path.exists(get_preset_path("Foo Device", "asdf")))
            self.assertEqual(self.window.preset_name, "asdf")
            self.assertEqual(self.window.group.name, "Foo Device")

        with patch.object(
            self.window, "show_confirm_delete", lambda: Gtk.ResponseType.ACCEPT
        ):
            self.window.on_delete_preset_clicked(None)
            self.assertFalse(os.path.exists(get_preset_path("Foo Device", "asdf")))
            self.assertEqual(self.window.preset_name, "new preset")
            self.assertEqual(self.window.group.name, "Foo Device")

    def test_populate_devices(self):
        preset_selection = self.window.get("preset_selection")

        # create two presets
        self.window.get("preset_name_input").set_text("preset 1")
        self.window.on_rename_button_clicked(None)
        self.assertEqual(preset_selection.get_active_id(), "preset 1")

        # to make sure the next preset has a slightly higher timestamp
        time.sleep(0.1)
        self.window.on_create_preset_clicked(None)
        self.window.get("preset_name_input").set_text("preset 2")
        self.window.on_rename_button_clicked(None)
        self.assertEqual(preset_selection.get_active_id(), "preset 2")

        # select the older one
        preset_selection.set_active_id("preset 1")
        self.assertEqual(self.window.preset_name, "preset 1")

        # add a device that doesn't exist to the dropdown
        unknown_key = "key-1234"
        self.window.device_store.insert(0, [unknown_key, None, "foo"])

        self.window.populate_devices()
        # the newest preset should be selected
        self.assertEqual(self.window.preset_name, "preset 2")

        # the list contains correct entries
        # and the non-existing entry should be removed
        entries = [tuple(entry) for entry in self.window.device_store]
        keys = [entry[0] for entry in self.window.device_store]
        self.assertNotIn(unknown_key, keys)
        self.assertIn("Foo Device", keys)
        self.assertIn(("Foo Device", "input-keyboard", "Foo Device"), entries)
        self.assertIn(("Foo Device 2", "input-mouse", "Foo Device 2"), entries)
        self.assertIn(("Bar Device", "input-keyboard", "Bar Device"), entries)
        self.assertIn(("gamepad", "input-gaming", "gamepad"), entries)

        # it won't crash due to "list index out of range"
        # when `types` is an empty list. Won't show an icon
        groups.find(key="Foo Device 2").types = []
        self.window.populate_devices()
        self.assertIn(
            ("Foo Device 2", None, "Foo Device 2"),
            [tuple(entry) for entry in self.window.device_store],
        )

    def test_screw_up_rows(self):
        # add a row that is not present in custom_mapping
        key_list = self.window.get("key_list")
        key_list.forall(key_list.remove)
        for i in range(5):
            broken = Row(window=self.window, delete_callback=lambda: None)
            broken.set_new_key(Key(1, i, 1))
            broken.symbol_input.set_text("a")
            key_list.insert(broken, -1)
        custom_mapping.empty()

        # the ui has 5 rows, the custom_mapping 0. mismatch
        num_rows_before = len(key_list.get_children())
        self.assertEqual(len(custom_mapping), 0)
        self.assertEqual(num_rows_before, 5)

        # it returns true to keep the glib timeout going
        self.assertTrue(self.window.check_add_row())
        # it still adds a new empty row and won't break
        num_rows_after = len(key_list.get_children())
        self.assertEqual(num_rows_after, num_rows_before + 1)

        rows = key_list.get_children()
        self.assertEqual(rows[0].get_symbol(), "a")
        self.assertEqual(rows[1].get_symbol(), "a")
        self.assertEqual(rows[2].get_symbol(), "a")
        self.assertEqual(rows[3].get_symbol(), "a")
        self.assertEqual(rows[4].get_symbol(), "a")
        self.assertEqual(rows[5].get_symbol(), None)

    def test_shared_presets(self):
        # devices with the same name (but different key because the key is
        # unique) share the same presets
        key_list = self.window.get("key_list")

        # 1. create a preset
        self.window.on_select_device(FakeDeviceDropdown("Foo Device 2"))
        self.window.on_create_preset_clicked(None)
        self.change_empty_row(Key(3, 2, 1), "qux")
        self.window.get("preset_name_input").set_text("asdf")
        self.window.on_rename_button_clicked(None)
        self.window.save_preset()
        self.assertIn("asdf.json", os.listdir(get_preset_path("Foo Device")))

        # 2. switch to the other device, there should be no preset named asdf
        self.window.on_select_device(FakeDeviceDropdown("Bar Device"))
        self.assertEqual(self.window.preset_name, "new preset")
        self.assertNotIn("asdf.json", os.listdir(get_preset_path("Bar Device")))
        self.assertIsNone(key_list.get_children()[0].get_symbol(), None)

        # 3. switch to the device with the same name
        self.window.on_select_device(FakeDeviceDropdown("Foo Device"))
        # the newest preset is asdf, it should be automatically selected
        self.assertEqual(self.window.preset_name, "asdf")
        self.assertEqual(key_list.get_children()[0].get_symbol(), "qux")


if __name__ == "__main__":
    unittest.main()
