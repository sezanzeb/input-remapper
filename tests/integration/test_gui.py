#!/usr/bin/python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2022 sezanzeb <proxima@sezanzeb.de>
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


# the tests file needs to be imported first to make sure patches are loaded
from tests.test import (
    get_project_root,
    logger,
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
from inputremapper.input_event import InputEvent

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk

from inputremapper.configs.system_mapping import system_mapping, XMODMAP_FILENAME
from inputremapper.gui.active_preset import active_preset
from inputremapper.configs.paths import CONFIG_PATH, get_preset_path, get_config_path
from inputremapper.configs.global_config import global_config, WHEEL, MOUSE, BUTTONS
from inputremapper.gui.reader import reader
from inputremapper.gui.helper import RootHelper
from inputremapper.gui.utils import gtk_iteration
from inputremapper.gui.user_interface import UserInterface
from inputremapper.gui.editor.editor import SET_KEY_FIRST
from inputremapper.injection.injector import RUNNING, FAILED, UNKNOWN
from inputremapper.event_combination import EventCombination
from inputremapper.daemon import Daemon
from inputremapper.groups import groups


# iterate a few times when Gtk.main() is called, but don't block
# there and just continue to the tests while the UI becomes
# unresponsive
Gtk.main = gtk_iteration

# doesn't do much except avoid some Gtk assertion error, whatever:
Gtk.main_quit = lambda: None


def launch(argv=None) -> UserInterface:
    """Start input-remapper-gtk with the command line argument array argv."""
    bin_path = os.path.join(get_project_root(), "bin", "input-remapper-gtk")

    if not argv:
        argv = ["-d"]

    with patch(
        "inputremapper.gui.user_interface.UserInterface.setup_timeouts",
        lambda *args: None,
    ):
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
    module.user_interface.setup_timeouts()

    return module.user_interface


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
    test.user_interface.on_stop_injecting_clicked(None)
    gtk_iteration()
    test.user_interface.on_close()
    test.user_interface.window.destroy()
    gtk_iteration()
    cleanup()

    # do this now, not when all tests are finished
    test.user_interface.dbus.stop_all()
    if isinstance(test.user_interface.dbus, Daemon):
        atexit.unregister(test.user_interface.dbus.stop_all)


class GtkKeyEvent:
    def __init__(self, keyval):
        self.keyval = keyval

    def get_keyval(self):
        return True, self.keyval


class TestGroupsFromHelper(unittest.TestCase):
    def setUp(self):
        self.injector = None
        self.grab = evdev.InputDevice.grab

        # don't try to connect, return an object instance of it instead
        self.original_connect = Daemon.connect
        Daemon.connect = Daemon

        self.original_os_system = os.system

        def os_system(cmd):
            # instead of running pkexec, fork instead. This will make
            # the helper aware of all the test patches
            if "pkexec input-remapper-control --command helper" in cmd:
                # the forked process should get the initial groups
                groups.refresh()
                multiprocessing.Process(target=RootHelper).start()
                # the gui an empty dict, because it doesn't know any devices
                # without the help of the privileged helper
                groups.set_groups([])
                assert len(groups) == 0
                return 0

            return self.original_os_system(cmd)

        os.system = os_system

        self.user_interface = launch()

    def tearDown(self):
        clean_up_integration(self)
        os.system = self.original_os_system
        Daemon.connect = self.original_connect

    def test_knows_devices(self):
        # verify that it is working as expected. The gui doesn't have knowledge
        # of groups until the root-helper provides them
        gtk_iteration()
        self.assertEqual(len(groups), 0)

        # perform some iterations so that the gui ends up running
        # consume_newest_keycode, which will make it receive devices.
        # Restore patch, otherwise gtk complains when disabling handlers
        for _ in range(10):
            time.sleep(0.02)
            gtk_iteration()

        self.assertIsNotNone(groups.find(key="Foo Device 2"))
        self.assertIsNotNone(groups.find(name="Bar Device"))
        self.assertIsNotNone(groups.find(name="gamepad"))
        self.assertEqual(self.user_interface.group.name, "Foo Device")


class PatchedConfirmDelete:
    def __init__(self, user_interface, response=Gtk.ResponseType.ACCEPT):
        self.response = response
        self.user_interface = user_interface
        self.patch = None

    def _confirm_delete_run_patch(self):
        """A patch for the deletion confirmation that briefly shows the dialog."""
        confirm_delete = self.user_interface.confirm_delete
        # the emitted signal causes the dialog to close
        GLib.timeout_add(
            100,
            lambda: confirm_delete.emit("response", self.response),
        )
        Gtk.MessageDialog.run(confirm_delete)  # don't recursively call the patch
        return self.response

    def __enter__(self):
        self.patch = patch.object(
            self.user_interface.get("confirm-delete"),
            "run",
            self._confirm_delete_run_patch,
        )
        self.patch.__enter__()

    def __exit__(self, *args, **kwargs):
        self.patch.__exit__(*args, **kwargs)


class GuiTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.injector = None
        cls.grab = evdev.InputDevice.grab
        cls.original_start_processes = UserInterface.start_processes

        def start_processes(self):
            """Avoid running pkexec which requires user input, and fork in
            order to pass the fixtures to the helper and daemon process.
            """
            multiprocessing.Process(target=RootHelper).start()
            self.dbus = Daemon()

        UserInterface.start_processes = start_processes

    def _callTestMethod(self, method):
        """Retry all tests if they fail.

        GUI tests suddenly started to lag a lot and fail randomly, and even
        though that improved drastically, sometimes they still do.
        """
        attempts = 0
        while True:
            attempts += 1
            try:
                method()
                break
            except Exception as e:
                if attempts == 2:
                    raise e

            # try again
            print("Test failed, trying again...")
            self.tearDown()
            self.setUp()

    def setUp(self):
        self.user_interface = launch()
        self.editor = self.user_interface.editor
        self.toggle = self.editor.get_recording_toggle()
        self.selection_label_listbox = self.user_interface.get(
            "selection_label_listbox"
        )
        self.window = self.user_interface.get("window")

        self.grab_fails = False

        def grab(_):
            if self.grab_fails:
                raise OSError()

        evdev.InputDevice.grab = grab

        global_config._save_config()

        self.throttle()

        self.assertIsNotNone(self.user_interface.group)
        self.assertIsNotNone(self.user_interface.group.key)
        self.assertIsNotNone(self.user_interface.preset_name)

    def tearDown(self):
        clean_up_integration(self)

        self.throttle()

    def throttle(self):
        """Give GTK some time to process everything."""
        # tests suddenly started to freeze my computer up completely
        # and tests started to fail. By using this (and by optimizing some
        # redundant calls in the gui) it worked again.
        for _ in range(10):
            gtk_iteration()
            time.sleep(0.002)

    @classmethod
    def tearDownClass(cls):
        UserInterface.start_processes = cls.original_start_processes

    def activate_recording_toggle(self):
        logger.info("Activating the recording toggle")
        self.set_focus(self.toggle)
        self.toggle.set_active(True)

    def disable_recording_toggle(self):
        logger.info("Deactivating the recording toggle")
        self.set_focus(None)
        # should happen automatically:
        self.assertFalse(self.toggle.get_active())

    def set_focus(self, widget):
        logger.info("Focusing %s", widget)

        self.user_interface.window.set_focus(widget)

        # for whatever miraculous reason it suddenly takes 0.005s before gtk does
        # anything, even for old code.
        time.sleep(0.02)
        gtk_iteration()

    def get_selection_labels(self):
        return self.selection_label_listbox.get_children()

    def get_status_text(self):
        status_bar = self.user_interface.get("status_bar")
        return status_bar.get_message_area().get_children()[0].get_label()

    def get_unfiltered_symbol_input_text(self):
        buffer = self.editor.get_code_editor().get_buffer()
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)

    def select_mapping(self, i: int):
        """Select one of the mappings of a preset.

        Parameters
        ----------
        i
            if -1, will select the "empty row",
            0 will select the uppermost row.
            1 will select the second row, and so on
        """
        selection_label = self.get_selection_labels()[i]
        self.selection_label_listbox.select_row(selection_label)
        logger.info(
            'Selecting mapping %s "%s"',
            selection_label.get_combination(),
            selection_label.get_label(),
        )
        return selection_label

    def add_mapping_via_ui(self, key, symbol, expect_success=True, target=None):
        """Modify the one empty mapping that always exists.

        Utility function for other tests.

        Parameters
        ----------
        key : EventCombination or None
        expect_success : boolean
            If the key can be stored in the selection label. False if this change
            is going to cause a duplicate.
        target : str
            the target selection
        """
        logger.info(
            'Adding mapping %s, "%s", expecting to %s',
            key,
            symbol,
            "work" if expect_success else "fail",
        )

        self.throttle()

        self.assertIsNone(reader.get_unreleased_keys())

        changed = active_preset.has_unsaved_changes()

        # wait for the window to create a new empty selection_label if needed
        time.sleep(0.1)
        gtk_iteration()

        # the empty selection_label is expected to be the last one
        selection_label = self.select_mapping(-1)
        self.assertIsNone(selection_label.get_combination())
        self.assertFalse(self.editor._input_has_arrived)

        if self.toggle.get_active():
            self.assertEqual(self.toggle.get_label(), "Press Key")
        else:
            self.assertEqual(self.toggle.get_label(), "Change Key")

        # the recording toggle connects to focus events
        self.set_focus(self.toggle)
        self.toggle.set_active(True)
        gtk_iteration()
        gtk_iteration()
        self.assertIsNone(selection_label.get_combination())
        self.assertEqual(self.toggle.get_label(), "Press Key")

        if key:
            # modifies the keycode in the selection_label not by writing into the input,
            # but by sending an event. press down all the keys of a combination
            for sub_key in key:
                send_event_to_reader(new_event(*sub_key.event_tuple))
                # this will be consumed all at once, since no gtk_iteration
                # is done

            # make the window consume the keycode
            self.sleep(len(key))

            # holding down
            self.assertIsNotNone(reader.get_unreleased_keys())
            self.assertGreater(len(reader.get_unreleased_keys()), 0)
            self.assertTrue(self.editor._input_has_arrived)
            self.assertTrue(self.toggle.get_active())

            # release all the keys
            for sub_key in key:
                send_event_to_reader(new_event(*sub_key.type_and_code, 0))

            # wait for the window to consume the keycode
            self.sleep(len(key))

            # released
            self.assertIsNone(reader.get_unreleased_keys())
            self.assertFalse(self.editor._input_has_arrived)

            if expect_success:
                self.assertEqual(self.editor.get_combination(), key)
                # the previously new entry, which has been edited now, is still the
                # selected one
                self.assertEqual(self.editor.active_selection_label, selection_label)
                self.assertEqual(
                    self.editor.active_selection_label.get_label(),
                    key.beautify(),
                )
                self.assertFalse(self.toggle.get_active())
                self.assertEqual(len(reader._unreleased), 0)

        if not expect_success:
            self.assertIsNone(selection_label.get_combination())
            self.assertEqual(self.editor.get_symbol_input_text(), "")
            self.assertFalse(self.editor._input_has_arrived)
            # it won't switch the focus to the symbol input
            self.assertTrue(self.toggle.get_active())
            self.assertEqual(active_preset.has_unsaved_changes(), changed)
            return selection_label

        if key is None:
            self.assertEqual(self.get_unfiltered_symbol_input_text(), SET_KEY_FIRST)
            self.assertEqual(self.editor.get_symbol_input_text(), "")

        # set the target selection
        if target:
            self.editor.set_target_selection(target)
            self.assertEqual(self.editor.get_target_selection(), target)
        else:
            self.assertEqual(self.editor.get_target_selection(), "keyboard")

        # set the symbol to make the new selection_label complete
        self.editor.set_symbol_input_text(symbol)
        self.assertEqual(self.editor.get_symbol_input_text(), symbol)

        # unfocus them to trigger some final logic
        self.set_focus(None)
        correct_case = system_mapping.correct_case(symbol)
        self.assertEqual(self.editor.get_symbol_input_text(), correct_case)
        self.assertFalse(active_preset.has_unsaved_changes())

        self.set_focus(self.editor.get_code_editor())
        self.set_focus(None)

        return selection_label

    def sleep(self, num_events):
        for _ in range(num_events * 2):
            time.sleep(EVENT_READ_TIMEOUT)
            gtk_iteration()

        time.sleep(1 / 30)  # one window iteration

        gtk_iteration()


class TestGui(GuiTestBase):
    """For tests that use the window.

    Try to modify the configuration only by calling functions of the window.
    """

    def test_can_start(self):
        self.assertIsNotNone(self.user_interface)
        self.assertTrue(self.user_interface.window.get_visible())

    def test_gui_clean(self):
        # check that the test is correctly set up so that the user interface is clean
        selection_labels = self.selection_label_listbox.get_children()
        self.assertEqual(len(selection_labels), 1)
        self.assertEqual(self.editor.active_selection_label, selection_labels[0])
        self.assertEqual(
            self.selection_label_listbox.get_selected_row(),
            selection_labels[0],
        )
        self.assertEqual(len(active_preset), 0)
        self.assertEqual(selection_labels[0].get_label(), "new entry")
        self.assertEqual(self.editor.get_symbol_input_text(), "")
        preset_selection = self.user_interface.get("preset_selection")
        self.assertEqual(preset_selection.get_active_id(), "new preset")
        self.assertEqual(len(active_preset), 0)
        self.assertEqual(self.editor.get_recording_toggle().get_label(), "Change Key")
        self.assertEqual(self.get_unfiltered_symbol_input_text(), SET_KEY_FIRST)

    def test_ctrl_q(self):
        closed = False

        def on_close():
            nonlocal closed
            closed = True

        with patch.object(self.user_interface, "on_close", on_close):
            self.user_interface.on_key_press(
                self.user_interface, GtkKeyEvent(Gdk.KEY_Control_L)
            )
            self.user_interface.on_key_press(
                self.user_interface, GtkKeyEvent(Gdk.KEY_a)
            )
            self.user_interface.on_key_release(
                self.user_interface, GtkKeyEvent(Gdk.KEY_Control_L)
            )
            self.user_interface.on_key_release(
                self.user_interface, GtkKeyEvent(Gdk.KEY_a)
            )
            self.user_interface.on_key_press(
                self.user_interface, GtkKeyEvent(Gdk.KEY_b)
            )
            self.user_interface.on_key_press(
                self.user_interface, GtkKeyEvent(Gdk.KEY_q)
            )
            self.user_interface.on_key_release(
                self.user_interface, GtkKeyEvent(Gdk.KEY_q)
            )
            self.user_interface.on_key_release(
                self.user_interface, GtkKeyEvent(Gdk.KEY_b)
            )
            self.assertFalse(closed)

            # while keys are being recorded no shortcut should work
            self.toggle.set_active(True)
            self.user_interface.on_key_press(
                self.user_interface, GtkKeyEvent(Gdk.KEY_Control_L)
            )
            self.user_interface.on_key_press(
                self.user_interface, GtkKeyEvent(Gdk.KEY_q)
            )
            self.assertFalse(closed)

            self.toggle.set_active(False)
            self.user_interface.on_key_press(
                self.user_interface, GtkKeyEvent(Gdk.KEY_Control_L)
            )
            self.user_interface.on_key_press(
                self.user_interface, GtkKeyEvent(Gdk.KEY_q)
            )
            self.assertTrue(closed)

            self.user_interface.on_key_release(
                self.user_interface, GtkKeyEvent(Gdk.KEY_Control_L)
            )
            self.user_interface.on_key_release(
                self.user_interface, GtkKeyEvent(Gdk.KEY_q)
            )

    def test_ctrl_r(self):
        with patch.object(reader, "refresh_groups") as reader_get_devices_patch:
            self.user_interface.on_key_press(
                self.user_interface, GtkKeyEvent(Gdk.KEY_Control_L)
            )
            self.user_interface.on_key_press(
                self.user_interface, GtkKeyEvent(Gdk.KEY_r)
            )
            reader_get_devices_patch.assert_called_once()

    def test_ctrl_del(self):
        with patch.object(self.user_interface.dbus, "stop_injecting") as stop_injecting:
            self.user_interface.on_key_press(
                self.user_interface, GtkKeyEvent(Gdk.KEY_Control_L)
            )
            self.user_interface.on_key_press(
                self.user_interface, GtkKeyEvent(Gdk.KEY_Delete)
            )
            stop_injecting.assert_called_once()

    def test_show_device_mapping_status(self):
        # this function may not return True, otherwise the timeout
        # runs forever
        self.assertFalse(self.user_interface.show_device_mapping_status())

    def test_autoload(self):
        self.assertFalse(
            global_config.is_autoloaded(
                self.user_interface.group.key, self.user_interface.preset_name
            )
        )

        with spy(self.user_interface.dbus, "set_config_dir") as set_config_dir:
            self.user_interface.on_autoload_switch(None, False)
            set_config_dir.assert_called_once()

        self.assertFalse(
            global_config.is_autoloaded(
                self.user_interface.group.key, self.user_interface.preset_name
            )
        )

        self.user_interface.on_select_device(FakeDeviceDropdown("Foo Device 2"))
        gtk_iteration()
        self.assertFalse(self.user_interface.get("preset_autoload_switch").get_active())

        # select a preset for the first device
        self.user_interface.get("preset_autoload_switch").set_active(True)
        gtk_iteration()
        self.assertTrue(self.user_interface.get("preset_autoload_switch").get_active())
        self.assertEqual(self.user_interface.group.key, "Foo Device 2")
        self.assertEqual(self.user_interface.group.name, "Foo Device")
        self.assertTrue(
            global_config.is_autoloaded(self.user_interface.group.key, "new preset")
        )
        self.assertFalse(global_config.is_autoloaded("Bar Device", "new preset"))
        self.assertListEqual(
            list(global_config.iterate_autoload_presets()),
            [("Foo Device 2", "new preset")],
        )

        # create a new preset, the switch should be correctly off and the
        # global_config not changed.
        self.user_interface.on_create_preset_clicked()
        gtk_iteration()
        self.assertEqual(self.user_interface.preset_name, "new preset 2")
        self.assertFalse(self.user_interface.get("preset_autoload_switch").get_active())
        self.assertTrue(global_config.is_autoloaded("Foo Device 2", "new preset"))
        self.assertFalse(global_config.is_autoloaded("Foo Device", "new preset"))
        self.assertFalse(global_config.is_autoloaded("Foo Device", "new preset 2"))
        self.assertFalse(global_config.is_autoloaded("Foo Device 2", "new preset 2"))

        # select a preset for the second device
        self.user_interface.on_select_device(FakeDeviceDropdown("Bar Device"))
        self.user_interface.get("preset_autoload_switch").set_active(True)
        gtk_iteration()
        self.assertTrue(global_config.is_autoloaded("Foo Device 2", "new preset"))
        self.assertFalse(global_config.is_autoloaded("Foo Device", "new preset"))
        self.assertTrue(global_config.is_autoloaded("Bar Device", "new preset"))
        self.assertListEqual(
            list(global_config.iterate_autoload_presets()),
            [("Foo Device 2", "new preset"), ("Bar Device", "new preset")],
        )

        # disable autoloading for the second device
        self.user_interface.get("preset_autoload_switch").set_active(False)
        gtk_iteration()
        self.assertTrue(global_config.is_autoloaded("Foo Device 2", "new preset"))
        self.assertFalse(global_config.is_autoloaded("Foo Device", "new preset"))
        self.assertFalse(global_config.is_autoloaded("Bar Device", "new preset"))
        self.assertListEqual(
            list(global_config.iterate_autoload_presets()),
            [("Foo Device 2", "new preset")],
        )

    def test_select_device(self):
        # creates a new empty preset when no preset exists for the device
        self.user_interface.on_select_device(FakeDeviceDropdown("Foo Device"))
        m1 = get_key_mapping()
        m1.event_combination = "1,50,1"
        m1.output_symbol = "q"
        m2 = get_key_mapping()
        m2.event_combination = "1,51,1"
        m2.output_symbol = "u"
        m3 = get_key_mapping()
        m3.event_combination = "1,52,1"
        m3.output_symbol = "x"
        active_preset.add(m1)
        active_preset.add(m2)
        active_preset.add(m3)
        self.assertEqual(len(active_preset), 3)
        self.user_interface.on_select_device(FakeDeviceDropdown("Bar Device"))
        self.assertEqual(len(active_preset), 0)
        # it creates the file for that right away. It may have been possible
        # to write it such that it doesn't (its empty anyway), but it does,
        # so use that to test it in more detail.
        path = get_preset_path("Bar Device", "new preset")
        self.assertTrue(os.path.exists(path))
        with open(path, "r") as file:
            self.assertEqual(file.read(), "")

    def test_permission_error_on_create_preset_clicked(self):
        def save(_=None):
            raise PermissionError

        with patch.object(active_preset, "save", save):
            self.user_interface.on_create_preset_clicked()
            status = self.get_status_text()
            self.assertIn("Permission denied", status)

    def test_show_injection_result_failure(self):
        def get_state(_=None):
            return FAILED

        with patch.object(self.user_interface.dbus, "get_state", get_state):
            self.user_interface.show_injection_result()
            text = self.get_status_text()
            self.assertIn("Failed", text)

    def test_editor_keycode_to_string(self):
        # not an integration test, but I have all the selection_label tests here already
        self.assertEqual(
            EventCombination((EV_KEY, evdev.ecodes.KEY_A, 1)).beautify(), "a"
        )
        self.assertEqual(
            EventCombination([EV_KEY, evdev.ecodes.KEY_A, 1]).beautify(), "a"
        )
        self.assertEqual(
            EventCombination((EV_ABS, evdev.ecodes.ABS_HAT0Y, -1)).beautify(), "DPad Up"
        )
        self.assertEqual(
            EventCombination((EV_KEY, evdev.ecodes.BTN_A, 1)).beautify(), "Button A"
        )
        self.assertEqual(EventCombination((EV_KEY, 1234, 1)).beautify(), "1234")
        self.assertEqual(
            EventCombination([EV_ABS, evdev.ecodes.ABS_HAT0X, -1]).beautify(),
            "DPad Left",
        )
        self.assertEqual(
            EventCombination([EV_ABS, evdev.ecodes.ABS_HAT0Y, -1]).beautify(), "DPad Up"
        )
        self.assertEqual(
            EventCombination([EV_KEY, evdev.ecodes.BTN_A, 1]).beautify(), "Button A"
        )
        self.assertEqual(EventCombination([EV_KEY, 1234, 1]).beautify(), "1234")
        self.assertEqual(
            EventCombination([EV_ABS, evdev.ecodes.ABS_X, 1]).beautify(),
            "Joystick Right",
        )
        self.assertEqual(
            EventCombination([EV_ABS, evdev.ecodes.ABS_RY, 1]).beautify(),
            "Joystick 2 Down",
        )
        self.assertEqual(
            EventCombination([EV_REL, evdev.ecodes.REL_HWHEEL, 1]).beautify(),
            "Wheel Right",
        )
        self.assertEqual(
            EventCombination([EV_REL, evdev.ecodes.REL_WHEEL, -1]).beautify(),
            "Wheel Down",
        )

        # combinations
        self.assertEqual(
            EventCombination(
                (EV_KEY, evdev.ecodes.BTN_A, 1),
                (EV_KEY, evdev.ecodes.BTN_B, 1),
                (EV_KEY, evdev.ecodes.BTN_C, 1),
            ).beautify(),
            "Button A + Button B + Button C",
        )

    def test_is_waiting_for_input(self):
        self.activate_recording_toggle()
        self.assertTrue(self.editor.is_waiting_for_input())

        self.disable_recording_toggle()
        self.assertFalse(self.editor.is_waiting_for_input())

    def test_editor_simple(self):
        self.assertEqual(self.toggle.get_label(), "Change Key")

        self.assertEqual(len(self.selection_label_listbox.get_children()), 1)

        selection_label = self.selection_label_listbox.get_children()[0]
        self.activate_recording_toggle()
        self.assertTrue(self.editor.is_waiting_for_input())
        self.assertEqual(self.toggle.get_label(), "Press Key")

        self.user_interface.consume_newest_keycode()
        # nothing happens
        self.assertIsNone(selection_label.get_combination())
        self.assertEqual(len(active_preset), 0)
        self.assertEqual(self.toggle.get_label(), "Press Key")

        send_event_to_reader(InputEvent.from_tuple((EV_KEY, 30, 1)))
        self.user_interface.consume_newest_keycode()
        # no symbol configured yet, so the active_preset remains empty
        self.assertEqual(len(active_preset), 0)
        self.assertEqual(len(selection_label.get_combination()), 1)
        self.assertEqual(selection_label.get_combination()[0], (EV_KEY, 30, 1))
        # this is KEY_A in linux/input-event-codes.h,
        # but KEY_ is removed from the text for display purposes
        self.assertEqual(selection_label.get_label(), "a")

        # providing the same key again doesn't do any harm
        # (Maybe this could happen for gamepads or something, idk)
        send_event_to_reader(InputEvent.from_tuple((EV_KEY, 30, 1)))
        self.user_interface.consume_newest_keycode()
        self.assertEqual(len(active_preset), 0)  # not released yet
        self.assertEqual(len(selection_label.get_combination()), 1)
        self.assertEqual(selection_label.get_combination()[0], (EV_KEY, 30, 1))

        time.sleep(0.11)
        # new empty entry was added
        gtk_iteration()
        self.assertEqual(
            len(self.selection_label_listbox.get_children()),
            2,
        )

        self.disable_recording_toggle()
        self.set_focus(self.editor.get_code_editor())
        self.assertFalse(self.editor.is_waiting_for_input())

        self.editor.set_symbol_input_text("Shift_L")

        self.set_focus(None)
        self.assertFalse(self.editor.is_waiting_for_input())

        num_mappings = len(active_preset)
        self.assertEqual(num_mappings, 1)

        time.sleep(0.1)
        gtk_iteration()
        self.assertEqual(
            len(self.selection_label_listbox.get_children()),
            2,
        )

        self.assertEqual(
            active_preset.get_mapping(EventCombination([EV_KEY, 30, 1])),
            ("Shift_L", "keyboard"),
        )
        self.assertEqual(self.editor.get_target_selection(), "keyboard")
        self.assertEqual(self.editor.get_symbol_input_text(), "Shift_L")
        self.assertEqual(len(selection_label.get_combination()), 1)
        self.assertEqual(selection_label.get_combination()[0], (EV_KEY, 30, 1))

        self.editor.set_target_selection("mouse")
        time.sleep(0.1)
        gtk_iteration()
        self.assertEqual(
            len(self.selection_label_listbox.get_children()),
            2,
        )
        self.assertEqual(
            active_preset.get_mapping(EventCombination([EV_KEY, 30, 1])),
            ("Shift_L", "mouse"),
        )
        self.assertEqual(self.editor.get_target_selection(), "mouse")
        self.assertEqual(self.editor.get_symbol_input_text(), "Shift_L")
        self.assertEqual(selection_label.get_combination()[0], (EV_KEY, 30, 1))

    def test_editor_not_focused(self):
        # focus anything that is not the selection_label,
        # no keycode should be inserted into it
        self.set_focus(self.user_interface.get("preset_name_input"))
        send_event_to_reader(new_event(1, 61, 1))
        self.user_interface.consume_newest_keycode()

        selection_labels = self.get_selection_labels()
        self.assertEqual(len(selection_labels), 1)
        selection_label = selection_labels[0]

        # the empty selection_label has this combination not set
        self.assertIsNone(selection_label.get_combination())

        # focus the text input instead
        self.set_focus(self.editor.get_code_editor())
        send_event_to_reader(new_event(1, 61, 1))
        self.user_interface.consume_newest_keycode()

        # still nothing set
        self.assertIsNone(selection_label.get_combination())

    def test_show_status(self):
        self.user_interface.show_status(0, "a" * 100)
        text = self.get_status_text()
        self.assertIn("...", text)

        self.user_interface.show_status(0, "b")
        text = self.get_status_text()
        self.assertNotIn("...", text)

    def test_clears_unreleased_on_focus_change(self):
        ev_1 = EventCombination([EV_KEY, 41, 1])

        # focus
        self.set_focus(self.toggle)
        send_event_to_reader(new_event(*ev_1[0].event_tuple))
        reader.read()
        self.assertEqual(reader.get_unreleased_keys(), ev_1)

        # unfocus
        # doesn't call reader.clear. Otherwise the super key cannot be mapped,
        # because the start menu that opens up would unfocus the user interface
        self.set_focus(None)
        self.assertEqual(reader.get_unreleased_keys(), ev_1)

        # focus the toggle after selecting a different selection_label.
        # It resets the reader
        self.editor.add_empty()
        self.select_mapping(-1)
        self.set_focus(self.toggle)
        self.toggle.set_active(True)

        self.assertEqual(reader.get_unreleased_keys(), None)

    def test_editor(self):
        """Comprehensive test for the editor."""
        system_mapping.clear()
        system_mapping._set("Foo_BAR", 41)
        system_mapping._set("B", 42)
        system_mapping._set("c", 43)
        system_mapping._set("d", 44)

        # how many selection_labels there should be in the end
        num_selection_labels_target = 3

        ev_1 = EventCombination([EV_KEY, 10, 1])
        ev_2 = EventCombination([EV_ABS, evdev.ecodes.ABS_HAT0X, -1])

        """edit"""

        # add two selection_labels by modifiying the one empty selection_label that
        # exists. Insert lowercase, it should be corrected to uppercase as stored
        # in system_mapping
        self.add_mapping_via_ui(ev_1, "foo_bar", target="mouse")
        self.add_mapping_via_ui(ev_2, "k(b).k(c)")

        # one empty selection_label added automatically again
        time.sleep(0.1)
        gtk_iteration()
        self.assertEqual(len(self.get_selection_labels()), num_selection_labels_target)

        self.assertEqual(active_preset.get_mapping(ev_1), ("Foo_BAR", "mouse"))
        self.assertEqual(active_preset.get_mapping(ev_2), ("k(b).k(c)", "keyboard"))

        """edit first selection_label"""

        self.select_mapping(0)
        self.assertEqual(self.editor.get_combination(), ev_1)
        self.set_focus(self.editor.get_code_editor())
        self.editor.set_symbol_input_text("c")
        self.set_focus(None)

        # after unfocusing, it stores the mapping. So loading it again will retain
        # the mapping that was used
        preset_name = self.user_interface.preset_name
        preset_path = self.user_interface.group.get_preset_path(preset_name)
        active_preset.load(preset_path)

        self.assertEqual(active_preset.get_mapping(ev_1), ("c", "mouse"))
        self.assertEqual(active_preset.get_mapping(ev_2), ("k(b).k(c)", "keyboard"))

        """add duplicate"""

        # try to add a duplicate keycode, it should be ignored
        self.add_mapping_via_ui(ev_2, "d", expect_success=False)
        self.assertEqual(active_preset.get_mapping(ev_2), ("k(b).k(c)", "keyboard"))
        # and the number of selection_labels shouldn't change
        self.assertEqual(len(self.get_selection_labels()), num_selection_labels_target)

    def test_hat0x(self):
        # it should be possible to add all of them
        ev_1 = EventCombination([EV_ABS, evdev.ecodes.ABS_HAT0X, -1])
        ev_2 = EventCombination([EV_ABS, evdev.ecodes.ABS_HAT0X, 1])
        ev_3 = EventCombination([EV_ABS, evdev.ecodes.ABS_HAT0Y, -1])
        ev_4 = EventCombination([EV_ABS, evdev.ecodes.ABS_HAT0Y, 1])

        self.add_mapping_via_ui(ev_1, "a")
        self.add_mapping_via_ui(ev_2, "b")
        self.add_mapping_via_ui(ev_3, "c")
        self.add_mapping_via_ui(ev_4, "d")

        self.assertEqual(active_preset.get_mapping(ev_1), ("a", "keyboard"))
        self.assertEqual(active_preset.get_mapping(ev_2), ("b", "keyboard"))
        self.assertEqual(active_preset.get_mapping(ev_3), ("c", "keyboard"))
        self.assertEqual(active_preset.get_mapping(ev_4), ("d", "keyboard"))

        # and trying to add them as duplicate selection_labels will be ignored for each
        # of them
        self.add_mapping_via_ui(ev_1, "e", expect_success=False)
        self.add_mapping_via_ui(ev_2, "f", expect_success=False)
        self.add_mapping_via_ui(ev_3, "g", expect_success=False)
        self.add_mapping_via_ui(ev_4, "h", expect_success=False)

        self.assertEqual(active_preset.get_mapping(ev_1), ("a", "keyboard"))
        self.assertEqual(active_preset.get_mapping(ev_2), ("b", "keyboard"))
        self.assertEqual(active_preset.get_mapping(ev_3), ("c", "keyboard"))
        self.assertEqual(active_preset.get_mapping(ev_4), ("d", "keyboard"))

    def test_combination(self):
        # it should be possible to write a combination combination
        ev_1 = InputEvent.from_tuple((EV_KEY, evdev.ecodes.KEY_A, 1))
        ev_2 = InputEvent.from_tuple((EV_ABS, evdev.ecodes.ABS_HAT0X, 1))
        ev_3 = InputEvent.from_tuple((EV_KEY, evdev.ecodes.KEY_C, 1))
        ev_4 = InputEvent.from_tuple((EV_ABS, evdev.ecodes.ABS_HAT0X, -1))
        combination_1 = EventCombination(ev_1, ev_2, ev_3)
        combination_2 = EventCombination(ev_2, ev_1, ev_3)

        # same as 1, but different D-Pad direction
        combination_3 = EventCombination(ev_1, ev_4, ev_3)
        combination_4 = EventCombination(ev_4, ev_1, ev_3)

        # same as 1, but the last combination is different
        combination_5 = EventCombination(ev_1, ev_3, ev_2)
        combination_6 = EventCombination(ev_3, ev_1, ev_2)

        self.add_mapping_via_ui(combination_1, "a")
        self.assertEqual(active_preset.get_mapping(combination_1), ("a", "keyboard"))
        self.assertEqual(active_preset.get_mapping(combination_2), ("a", "keyboard"))
        self.assertIsNone(active_preset.get_mapping(combination_3))
        self.assertIsNone(active_preset.get_mapping(combination_4))
        self.assertIsNone(active_preset.get_mapping(combination_5))
        self.assertIsNone(active_preset.get_mapping(combination_6))

        # it won't write the same combination again, even if the
        # first two events are in a different order
        self.add_mapping_via_ui(combination_2, "b", expect_success=False)
        self.assertEqual(active_preset.get_mapping(combination_1), ("a", "keyboard"))
        self.assertEqual(active_preset.get_mapping(combination_2), ("a", "keyboard"))
        self.assertIsNone(active_preset.get_mapping(combination_3))
        self.assertIsNone(active_preset.get_mapping(combination_4))
        self.assertIsNone(active_preset.get_mapping(combination_5))
        self.assertIsNone(active_preset.get_mapping(combination_6))

        self.add_mapping_via_ui(combination_3, "c")
        self.assertEqual(active_preset.get_mapping(combination_1), ("a", "keyboard"))
        self.assertEqual(active_preset.get_mapping(combination_2), ("a", "keyboard"))
        self.assertEqual(active_preset.get_mapping(combination_3), ("c", "keyboard"))
        self.assertEqual(active_preset.get_mapping(combination_4), ("c", "keyboard"))
        self.assertIsNone(active_preset.get_mapping(combination_5))
        self.assertIsNone(active_preset.get_mapping(combination_6))

        # same as with combination_2, the existing combination_3 blocks
        # combination_4 because they have the same keys and end in the
        # same key.
        self.add_mapping_via_ui(combination_4, "d", expect_success=False)
        self.assertEqual(active_preset.get_mapping(combination_1), ("a", "keyboard"))
        self.assertEqual(active_preset.get_mapping(combination_2), ("a", "keyboard"))
        self.assertEqual(active_preset.get_mapping(combination_3), ("c", "keyboard"))
        self.assertEqual(active_preset.get_mapping(combination_4), ("c", "keyboard"))
        self.assertIsNone(active_preset.get_mapping(combination_5))
        self.assertIsNone(active_preset.get_mapping(combination_6))

        self.add_mapping_via_ui(combination_5, "e")
        self.assertEqual(active_preset.get_mapping(combination_1), ("a", "keyboard"))
        self.assertEqual(active_preset.get_mapping(combination_2), ("a", "keyboard"))
        self.assertEqual(active_preset.get_mapping(combination_3), ("c", "keyboard"))
        self.assertEqual(active_preset.get_mapping(combination_4), ("c", "keyboard"))
        self.assertEqual(active_preset.get_mapping(combination_5), ("e", "keyboard"))
        self.assertEqual(active_preset.get_mapping(combination_6), ("e", "keyboard"))

        error_icon = self.user_interface.get("error_status_icon")
        warning_icon = self.user_interface.get("warning_status_icon")

        self.assertFalse(error_icon.get_visible())
        self.assertFalse(warning_icon.get_visible())

    def test_remove_selection_label(self):
        """Comprehensive test for selection_labels 2."""

        def remove(
            selection_label, code, symbol, num_selection_labels_after, target="keyboard"
        ):
            """Remove a selection_label by clicking the delete button.

            Parameters
            ----------
            selection_label : SelectionLabel
            code : int or None
                keycode of the mapping that is associated with this selection_label
            symbol : string
                ouptut of the mapping that is associated with this selection_label
            num_selection_labels_after : int
                after deleting, how many selection_labels are expected to still be there
            target :
                selected target in target_selector
            """
            self.selection_label_listbox.select_row(selection_label)

            if code is not None and symbol is not None:
                self.assertEqual(
                    active_preset.get_mapping(EventCombination([EV_KEY, code, 1])),
                    (symbol, target),
                )

            if symbol is not None:
                self.assertEqual(self.editor.get_symbol_input_text(), symbol)

            self.assertEqual(self.editor.get_target_selection(), target)

            if code is None:
                self.assertIsNone(selection_label.get_combination())
            else:
                self.assertEqual(
                    selection_label.get_combination(),
                    EventCombination([EV_KEY, code, 1]),
                )

            with PatchedConfirmDelete(self.user_interface):
                self.editor._on_delete_button_clicked()

            time.sleep(0.2)
            gtk_iteration()

            # if a reference to the selection_label is held somewhere and it is
            # accidentally used again, make sure to not provide any outdated
            # information that is supposed to be deleted
            self.assertIsNone(selection_label.get_combination())
            if code is not None:
                self.assertIsNone(
                    active_preset.get_mapping(EventCombination([EV_KEY, code, 1]))
                )

            self.assertEqual(
                len(self.get_selection_labels()),
                num_selection_labels_after,
            )

        # sleeps are added to be able to visually follow and debug the test. Add two
        # selection_labels by modifiying the one empty selection_label that exists
        selection_label_1 = self.add_mapping_via_ui(
            EventCombination([EV_KEY, 10, 1]), "a"
        )
        selection_label_2 = self.add_mapping_via_ui(
            EventCombination([EV_KEY, 11, 1]), "b"
        )

        # no empty selection_label added because one is unfinished
        time.sleep(0.2)
        gtk_iteration()
        self.assertEqual(len(self.get_selection_labels()), 3)

        self.assertEqual(
            active_preset.get_mapping(EventCombination([EV_KEY, 11, 1])),
            ("b", "keyboard"),
        )

        remove(selection_label_1, 10, "a", 2)
        remove(selection_label_2, 11, "b", 1)

        # there is no empty selection_label at the moment, so after removing that one,
        # which is the only selection_label, one empty selection_label will be there.
        # So the number of selection_labels won't change.
        remove(self.selection_label_listbox.get_children()[-1], None, None, 1)

    def test_problematic_combination(self):
        combination = EventCombination((EV_KEY, KEY_LEFTSHIFT, 1), (EV_KEY, 82, 1))
        self.add_mapping_via_ui(combination, "b")
        text = self.get_status_text()
        self.assertIn("shift", text)

        error_icon = self.user_interface.get("error_status_icon")
        warning_icon = self.user_interface.get("warning_status_icon")

        self.assertFalse(error_icon.get_visible())
        self.assertTrue(warning_icon.get_visible())

    def test_rename_and_save(self):
        self.assertEqual(self.user_interface.group.name, "Foo Device")
        self.assertFalse(global_config.is_autoloaded("Foo Device", "new preset"))

        m1 = get_key_mapping()
        active_preset.add(m1)
        self.assertEqual(self.user_interface.preset_name, "new preset")
        self.user_interface.save_preset()
        self.assertEqual(
            active_preset.get_mapping(EventCombination([99, 99, 99])),
            m1,
        )
        global_config.set_autoload_preset("Foo Device", "new preset")
        self.assertTrue(global_config.is_autoloaded("Foo Device", "new preset"))

        m2 = get_key_mapping()
        m2.output_symbol = "b"
        active_preset.get_mapping(EventCombination([99, 99, 99])).output_symbol = "b"
        self.user_interface.get("preset_name_input").set_text("asdf")
        self.user_interface.save_preset()
        self.user_interface.on_rename_button_clicked(None)
        self.assertEqual(self.user_interface.preset_name, "asdf")
        preset_path = f"{CONFIG_PATH}/presets/Foo Device/asdf.json"
        self.assertTrue(os.path.exists(preset_path))
        self.assertEqual(
            active_preset.get_mapping(EventCombination([99, 99, 99])),
            m2,
        )

        # after renaming the preset it is still set to autoload
        self.assertTrue(global_config.is_autoloaded("Foo Device", "asdf"))
        # ALSO IN THE ACTUAL CONFIG FILE!
        global_config.load_config()
        self.assertTrue(global_config.is_autoloaded("Foo Device", "asdf"))

        error_icon = self.user_interface.get("error_status_icon")
        self.assertFalse(error_icon.get_visible())

        # otherwise save won't do anything
        m2.output_symbol = "c"
        active_preset.get_mapping(EventCombination([99, 99, 99])).output_symbol = "c"
        self.assertTrue(active_preset.has_unsaved_changes())

        def save():
            raise PermissionError

        with patch.object(active_preset, "save", save):
            self.user_interface.save_preset()
            status = self.get_status_text()
            self.assertIn("Permission denied", status)

        with PatchedConfirmDelete(self.user_interface):
            self.user_interface.on_delete_preset_clicked(None)
            self.assertFalse(os.path.exists(preset_path))

    def test_rename_create_switch(self):
        # after renaming a preset and saving it, new presets
        # start with "new preset" again
        m1 = get_key_mapping()
        # active_preset.change(EventCombination([EV_KEY, 14, 1]), "keyboard", "a", None)
        active_preset.add(m1)
        self.user_interface.get("preset_name_input").set_text("asdf")
        self.user_interface.save_preset()
        self.user_interface.on_rename_button_clicked(None)
        self.assertEqual(len(active_preset), 1)
        self.assertEqual(self.user_interface.preset_name, "asdf")

        self.user_interface.on_create_preset_clicked()
        self.assertEqual(self.user_interface.preset_name, "new preset")
        self.assertEqual(len(self.selection_label_listbox.get_children()), 1)
        self.assertEqual(len(active_preset), 0)
        self.user_interface.save_preset()

        # symbol and code in the gui won't be carried over after selecting a preset
        self.editor.set_combination(EventCombination([EV_KEY, 15, 1]))
        self.editor.set_symbol_input_text("b")

        # selecting the first preset again loads the saved mapping, and saves
        # the current changes in the gui
        self.user_interface.on_select_preset(FakePresetDropdown("asdf"))
        self.assertEqual(
            active_preset.get_mapping(EventCombination([99, 99, 99])),
            m1,
        )
        self.assertEqual(len(active_preset), 1)
        self.assertEqual(len(self.selection_label_listbox.get_children()), 2)
        global_config.set_autoload_preset("Foo Device", "new preset")

        # renaming a preset to an existing name appends a number
        self.user_interface.on_select_preset(FakePresetDropdown("new preset"))
        self.user_interface.get("preset_name_input").set_text("asdf")
        self.user_interface.on_rename_button_clicked(None)
        self.assertEqual(self.user_interface.preset_name, "asdf 2")
        # and that added number is correctly used in the autoload
        # configuration as well
        self.assertTrue(global_config.is_autoloaded("Foo Device", "asdf 2"))
        m2 = get_key_mapping()
        m2.event_combination = "1,15,1"
        m2.output_symbol = "b"
        self.assertEqual(
            active_preset.get_mapping(EventCombination([EV_KEY, 15, 1])),
            m2,
        )
        self.assertEqual(len(active_preset), 1)
        self.assertEqual(len(self.selection_label_listbox.get_children()), 2)

        self.assertEqual(self.user_interface.get("preset_name_input").get_text(), "")

        # renaming the current preset to itself doesn't append a number and
        # it doesn't do anything on the file system
        def _raise(*_):
            # should not get called
            raise AssertionError

        with patch.object(os, "rename", _raise):
            self.user_interface.get("preset_name_input").set_text("asdf 2")
            self.user_interface.on_rename_button_clicked(None)
            self.assertEqual(self.user_interface.preset_name, "asdf 2")

            self.user_interface.get("preset_name_input").set_text("")
            self.user_interface.on_rename_button_clicked(None)
            self.assertEqual(self.user_interface.preset_name, "asdf 2")

    def test_check_for_unknown_symbols(self):
        status = self.user_interface.get("status_bar")
        error_icon = self.user_interface.get("error_status_icon")
        warning_icon = self.user_interface.get("warning_status_icon")

        active_preset.change(EventCombination([EV_KEY, 71, 1]), "keyboard", "qux", None)
        active_preset.change(EventCombination([EV_KEY, 72, 1]), "keyboard", "foo", None)
        self.user_interface.save_preset()
        tooltip = status.get_tooltip_text().lower()
        self.assertIn("qux", tooltip)
        self.assertTrue(error_icon.get_visible())
        self.assertFalse(warning_icon.get_visible())

        # it will still save it though
        with open(get_preset_path("Foo Device", "new preset")) as f:
            content = f.read()
            self.assertIn("qux", content)
            self.assertIn("foo", content)

        active_preset.change(EventCombination([EV_KEY, 71, 1]), "keyboard", "a", None)
        self.user_interface.save_preset()
        tooltip = status.get_tooltip_text().lower()
        self.assertIn("foo", tooltip)
        self.assertTrue(error_icon.get_visible())
        self.assertFalse(warning_icon.get_visible())

        active_preset.change(EventCombination([EV_KEY, 72, 1]), "keyboard", "b", None)
        self.user_interface.save_preset()
        tooltip = status.get_tooltip_text()
        self.assertIsNone(tooltip)
        self.assertFalse(error_icon.get_visible())
        self.assertFalse(warning_icon.get_visible())

    def test_check_macro_syntax(self):
        status = self.user_interface.get("status_bar")
        error_icon = self.user_interface.get("error_status_icon")
        warning_icon = self.user_interface.get("warning_status_icon")

        active_preset.change(
            EventCombination([EV_KEY, 9, 1]), "keyboard", "k(1))", None
        )
        self.user_interface.save_preset()
        tooltip = status.get_tooltip_text().lower()
        self.assertIn("brackets", tooltip)
        self.assertTrue(error_icon.get_visible())
        self.assertFalse(warning_icon.get_visible())

        active_preset.change(EventCombination([EV_KEY, 9, 1]), "keyboard", "k(1)", None)
        self.user_interface.save_preset()
        tooltip = (status.get_tooltip_text() or "").lower()
        self.assertNotIn("brackets", tooltip)
        self.assertFalse(error_icon.get_visible())
        self.assertFalse(warning_icon.get_visible())

        self.assertEqual(
            active_preset.get_mapping(EventCombination([EV_KEY, 9, 1])),
            ("k(1)", "keyboard"),
        )

    def test_select_device_and_preset(self):
        foo_device_path = f"{CONFIG_PATH}/presets/Foo Device"
        key_10 = EventCombination([EV_KEY, 10, 1])
        key_11 = EventCombination([EV_KEY, 11, 1])

        # created on start because the first device is selected and some empty
        # preset prepared.
        self.assertTrue(os.path.exists(f"{foo_device_path}/new preset.json"))
        self.assertEqual(self.user_interface.group.name, "Foo Device")
        self.assertEqual(self.user_interface.preset_name, "new preset")
        # change it to check if the gui loads presets correctly later
        self.editor.set_combination(key_10)
        self.editor.set_symbol_input_text("a")

        # create another one
        self.user_interface.on_create_preset_clicked()
        gtk_iteration()
        self.assertTrue(os.path.exists(f"{foo_device_path}/new preset.json"))
        self.assertTrue(os.path.exists(f"{foo_device_path}/new preset 2.json"))
        self.assertEqual(self.user_interface.preset_name, "new preset 2")
        self.assertEqual(len(active_preset), 0)
        # this should not be loaded when "new preset" is selected, because it belongs
        # to "new preset 2":
        self.editor.set_combination(key_11)
        self.editor.set_symbol_input_text("a")

        # select the first one again
        self.user_interface.on_select_preset(FakePresetDropdown("new preset"))
        gtk_iteration()
        self.assertEqual(self.user_interface.preset_name, "new preset")

        self.assertEqual(len(active_preset), 1)
        self.assertEqual(active_preset.get_mapping(key_10), ("a", "keyboard"))

        self.assertListEqual(
            sorted(os.listdir(f"{foo_device_path}")),
            sorted(["new preset.json", "new preset 2.json"]),
        )

        """now try to change the name"""

        self.user_interface.get("preset_name_input").set_text("abc 123")
        gtk_iteration()
        self.assertEqual(self.user_interface.preset_name, "new preset")
        self.assertFalse(os.path.exists(f"{foo_device_path}/abc 123.json"))

        # putting new information into the editor does not lead to some weird
        # problems. when doing the rename everything will be saved and then moved
        # to the new path
        self.editor.set_combination(EventCombination([EV_KEY, 10, 1]))
        self.editor.set_symbol_input_text("1")

        self.assertEqual(self.user_interface.preset_name, "new preset")
        self.user_interface.on_rename_button_clicked(None)
        self.assertEqual(self.user_interface.preset_name, "abc 123")

        gtk_iteration()
        self.assertEqual(self.user_interface.preset_name, "abc 123")
        self.assertTrue(os.path.exists(f"{foo_device_path}/abc 123.json"))
        self.assertListEqual(
            sorted(os.listdir(os.path.join(CONFIG_PATH, "presets"))),
            sorted(["Foo Device"]),
        )
        self.assertListEqual(
            sorted(os.listdir(f"{foo_device_path}")),
            sorted(["abc 123.json", "new preset 2.json"]),
        )

    def test_copy_preset(self):
        selection_labels = self.selection_label_listbox
        self.add_mapping_via_ui(EventCombination([EV_KEY, 81, 1]), "a")
        time.sleep(0.1)
        gtk_iteration()
        self.user_interface.save_preset()
        # 2 selection_labels: the changed selection_label and an empty selection_label
        self.assertEqual(len(selection_labels.get_children()), 2)

        # should be cleared when creating a new preset
        active_preset.set("a.b", 3)
        self.assertEqual(active_preset.get("a.b"), 3)

        self.user_interface.on_create_preset_clicked()

        # the preset should be empty, only one empty selection_label present
        self.assertEqual(len(selection_labels.get_children()), 1)
        self.assertIsNone(active_preset.get("a.b"))

        # add one new selection_label again and a setting
        self.add_mapping_via_ui(EventCombination([EV_KEY, 81, 1]), "b")
        time.sleep(0.1)
        gtk_iteration()
        self.user_interface.save_preset()
        self.assertEqual(len(selection_labels.get_children()), 2)
        active_preset.set(["foo", "bar"], 2)

        # this time it should be copied
        self.user_interface.on_copy_preset_clicked()
        self.assertEqual(self.user_interface.preset_name, "new preset 2 copy")
        self.assertEqual(len(selection_labels.get_children()), 2)
        self.assertEqual(self.editor.get_symbol_input_text(), "b")
        self.assertEqual(active_preset.get(["foo", "bar"]), 2)

        # make another copy
        self.user_interface.on_copy_preset_clicked()
        self.assertEqual(self.user_interface.preset_name, "new preset 2 copy 2")
        self.assertEqual(len(selection_labels.get_children()), 2)
        self.assertEqual(self.editor.get_symbol_input_text(), "b")
        self.assertEqual(len(active_preset), 1)
        self.assertEqual(active_preset.get("foo.bar"), 2)

    def test_gamepad_config(self):
        # set some stuff in the beginning, otherwise gtk fails to
        # do handler_unblock_by_func, which makes no sense at all.
        # but it ONLY fails on right_joystick_purpose for some reason,
        # unblocking the left one works just fine. I should open a bug report
        # on gtk or something probably.
        self.user_interface.get("left_joystick_purpose").set_active_id(BUTTONS)
        self.user_interface.get("right_joystick_purpose").set_active_id(BUTTONS)
        self.user_interface.get("joystick_mouse_speed").set_value(1)
        active_preset.set_has_unsaved_changes(False)

        # select a device that is not a gamepad
        self.user_interface.on_select_device(FakeDeviceDropdown("Foo Device"))
        self.assertFalse(self.user_interface.get("gamepad_config").is_visible())
        self.assertFalse(active_preset.has_unsaved_changes())

        # select a gamepad
        self.user_interface.on_select_device(FakeDeviceDropdown("gamepad"))
        self.assertTrue(self.user_interface.get("gamepad_config").is_visible())
        self.assertFalse(active_preset.has_unsaved_changes())

        # set stuff
        gtk_iteration()
        self.user_interface.get("left_joystick_purpose").set_active_id(WHEEL)
        self.user_interface.get("right_joystick_purpose").set_active_id(WHEEL)
        joystick_mouse_speed = 5
        self.user_interface.get("joystick_mouse_speed").set_value(joystick_mouse_speed)

        # it should be stored in active_preset, which overwrites the
        # global_config
        global_config.set("gamepad.joystick.left_purpose", MOUSE)
        global_config.set("gamepad.joystick.right_purpose", MOUSE)
        global_config.set("gamepad.joystick.pointer_speed", 50)
        self.assertTrue(active_preset.has_unsaved_changes())
        left_purpose = active_preset.get("gamepad.joystick.left_purpose")
        right_purpose = active_preset.get("gamepad.joystick.right_purpose")
        pointer_speed = active_preset.get("gamepad.joystick.pointer_speed")
        self.assertEqual(left_purpose, WHEEL)
        self.assertEqual(right_purpose, WHEEL)
        self.assertEqual(pointer_speed, 2**joystick_mouse_speed)

        # select a device that is not a gamepad again
        self.user_interface.on_select_device(FakeDeviceDropdown("Foo Device"))
        self.assertFalse(self.user_interface.get("gamepad_config").is_visible())
        self.assertFalse(active_preset.has_unsaved_changes())

    def test_wont_start(self):
        error_icon = self.user_interface.get("error_status_icon")
        preset_name = "foo preset"
        group_name = "Bar Device"
        self.user_interface.preset_name = preset_name
        self.user_interface.group = groups.find(name=group_name)

        # empty

        active_preset.empty()
        self.user_interface.save_preset()
        self.user_interface.on_apply_preset_clicked(None)
        text = self.get_status_text()
        self.assertIn("add keys", text)
        self.assertTrue(error_icon.get_visible())
        self.assertNotEqual(
            self.user_interface.dbus.get_state(self.user_interface.group.key), RUNNING
        )

        # not empty, but keys are held down

        active_preset.change(EventCombination([EV_KEY, KEY_A, 1]), "keyboard", "a")
        self.user_interface.save_preset()
        send_event_to_reader(new_event(EV_KEY, KEY_A, 1))
        reader.read()
        self.assertEqual(len(reader._unreleased), 1)
        self.assertFalse(self.user_interface.unreleased_warn)
        self.user_interface.on_apply_preset_clicked(None)
        text = self.get_status_text()
        self.assertIn("release", text)
        self.assertTrue(error_icon.get_visible())
        self.assertNotEqual(
            self.user_interface.dbus.get_state(self.user_interface.group.key), RUNNING
        )
        self.assertTrue(self.user_interface.unreleased_warn)
        self.assertEqual(
            self.user_interface.get("apply_system_layout").get_opacity(), 0.4
        )
        self.assertEqual(
            self.user_interface.get("key_recording_toggle").get_opacity(), 1
        )

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
            self.user_interface.on_apply_preset_clicked(None)
            self.assertFalse(self.user_interface.unreleased_warn)
            text = self.get_status_text()
            # it takes a little bit of time
            self.assertIn("Starting injection", text)
            self.assertFalse(error_icon.get_visible())
            wait()
            text = self.get_status_text()
            self.assertIn("not grabbed", text)
            self.assertTrue(error_icon.get_visible())
            self.assertNotEqual(
                self.user_interface.dbus.get_state(self.user_interface.group.key),
                RUNNING,
            )

            # for the second try, release the key. that should also work
            send_event_to_reader(new_event(EV_KEY, KEY_A, 0))
            reader.read()
            self.assertEqual(len(reader._unreleased), 0)

        # this time work properly

        self.grab_fails = False
        active_preset.save(get_preset_path(group_name, preset_name))
        self.user_interface.on_apply_preset_clicked(None)
        text = self.get_status_text()
        self.assertIn("Starting injection", text)
        self.assertFalse(error_icon.get_visible())
        wait()
        text = self.get_status_text()
        self.assertIn("Applied", text)
        text = self.get_status_text()
        self.assertNotIn("CTRL + DEL", text)  # only shown if btn_left mapped
        self.assertFalse(error_icon.get_visible())
        self.assertEqual(
            self.user_interface.dbus.get_state(self.user_interface.group.key), RUNNING
        )

        self.assertEqual(
            self.user_interface.get("apply_system_layout").get_opacity(), 1
        )
        self.assertEqual(
            self.user_interface.get("key_recording_toggle").get_opacity(), 0.4
        )

        # because this test managed to reproduce some minor bug:
        # The mapping is supposed to be in active_preset._mapping, not in _config.
        # For reasons I don't remember.
        self.assertNotIn("mapping", active_preset._config)

    def test_wont_start_2(self):
        preset_name = "foo preset"
        group_name = "Bar Device"
        self.user_interface.preset_name = preset_name
        self.user_interface.group = groups.find(name=group_name)

        def wait():
            """Wait for the injector process to finish doing stuff."""
            for _ in range(10):
                time.sleep(0.1)
                gtk_iteration()
                if "Starting" not in self.get_status_text():
                    return

        # btn_left mapped
        active_preset.change(EventCombination(InputEvent.btn_left()), "keyboard", "a")
        self.user_interface.save_preset()

        # and combination held down
        send_event_to_reader(new_event(EV_KEY, KEY_A, 1))
        reader.read()
        self.assertEqual(len(reader._unreleased), 1)
        self.assertFalse(self.user_interface.unreleased_warn)

        # first apply, shows btn_left warning
        self.user_interface.on_apply_preset_clicked(None)
        text = self.get_status_text()
        self.assertIn("click", text)
        self.assertEqual(
            self.user_interface.dbus.get_state(self.user_interface.group.key), UNKNOWN
        )

        # second apply, shows unreleased warning
        self.user_interface.on_apply_preset_clicked(None)
        text = self.get_status_text()
        self.assertIn("release", text)
        self.assertEqual(
            self.user_interface.dbus.get_state(self.user_interface.group.key), UNKNOWN
        )

        # third apply, overwrites both warnings
        self.user_interface.on_apply_preset_clicked(None)
        wait()
        self.assertEqual(
            self.user_interface.dbus.get_state(self.user_interface.group.key), RUNNING
        )
        text = self.get_status_text()
        # because btn_left is mapped, shows help on how to stop
        # injecting via the keyboard
        self.assertIn("CTRL + DEL", text)

    def test_can_modify_mapping(self):
        preset_name = "foo preset"
        group_name = "Bar Device"
        self.user_interface.preset_name = preset_name
        self.user_interface.group = groups.find(name=group_name)

        self.assertNotEqual(
            self.user_interface.dbus.get_state(self.user_interface.group.key), RUNNING
        )
        self.user_interface.can_modify_preset()
        text = self.get_status_text()
        self.assertNotIn("Stop Injection", text)

        active_preset.change(EventCombination([EV_KEY, KEY_A, 1]), "keyboard", "b")
        active_preset.save(get_preset_path(group_name, preset_name))
        self.user_interface.on_apply_preset_clicked(None)

        # wait for the injector to start
        for _ in range(10):
            time.sleep(0.1)
            gtk_iteration()
            if "Starting" not in self.get_status_text():
                break

        self.assertEqual(
            self.user_interface.dbus.get_state(self.user_interface.group.key), RUNNING
        )

        # the preset cannot be changed anymore
        self.assertFalse(self.user_interface.can_modify_preset())

        # the toggle button should reset itself shortly
        self.user_interface.editor.get_recording_toggle().set_active(True)
        for _ in range(10):
            time.sleep(0.1)
            gtk_iteration()
            if not self.user_interface.editor.get_recording_toggle().get_active():
                break

        self.assertFalse(self.user_interface.editor.get_recording_toggle().get_active())
        text = self.get_status_text()
        self.assertIn("Stop Injection", text)

    def test_start_injecting(self):
        keycode_from = 9
        keycode_to = 200

        self.add_mapping_via_ui(EventCombination([EV_KEY, keycode_from, 1]), "a")
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
        active_preset.save(get_preset_path("Foo Device", "foo preset"))

        # use only the manipulated system_mapping
        if os.path.exists(os.path.join(tmp, XMODMAP_FILENAME)):
            os.remove(os.path.join(tmp, XMODMAP_FILENAME))

        # select the second Foo device
        self.user_interface.group = groups.find(key="Foo Device 2")

        with spy(self.user_interface.dbus, "set_config_dir") as spy1:
            self.user_interface.preset_name = "foo preset"

            with spy(self.user_interface.dbus, "start_injecting") as spy2:
                self.user_interface.on_apply_preset_clicked(None)
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
        self.user_interface.populate_devices()
        for entry in self.user_interface.device_store:
            # whichever attribute contains "input-remapper"
            self.assertNotIn("input-remapper", "".join(entry))

    def test_gamepad_purpose_mouse_and_button(self):
        self.user_interface.on_select_device(FakeDeviceDropdown("gamepad"))
        self.user_interface.get("right_joystick_purpose").set_active_id(MOUSE)
        self.user_interface.get("left_joystick_purpose").set_active_id(BUTTONS)
        self.user_interface.get("joystick_mouse_speed").set_value(6)
        gtk_iteration()
        speed = active_preset.get("gamepad.joystick.pointer_speed")
        active_preset.set("gamepad.joystick.non_linearity", 1)
        self.assertEqual(speed, 2**6)

        # don't consume the events in the reader, they are used to test
        # the injection
        reader.terminate()
        time.sleep(0.1)

        push_events(
            "gamepad",
            [new_event(EV_ABS, ABS_RX, MIN_ABS), new_event(EV_ABS, ABS_X, MAX_ABS)]
            * 100,
        )

        active_preset.change(EventCombination([EV_ABS, ABS_X, 1]), "keyboard", "a")
        self.user_interface.save_preset()

        gtk_iteration()

        self.user_interface.on_apply_preset_clicked(None)
        time.sleep(0.3)

        history = []
        while uinput_write_history_pipe[0].poll():
            history.append(uinput_write_history_pipe[0].recv().t)

        count_mouse = history.count((EV_REL, REL_X, -speed))
        count_button = history.count((EV_KEY, KEY_A, 1))
        self.assertGreater(count_mouse, 1)
        self.assertEqual(count_button, 1)
        self.assertEqual(count_button + count_mouse, len(history))

        self.assertIn("gamepad", self.user_interface.dbus.injectors)

    def test_stop_injecting(self):
        keycode_from = 16
        keycode_to = 90

        self.add_mapping_via_ui(EventCombination([EV_KEY, keycode_from, 1]), "t")
        system_mapping.clear()
        system_mapping._set("t", keycode_to)

        # not all of those events should be processed, since that takes some
        # time due to time.sleep in the fakes and the injection is stopped.
        push_events("Bar Device", [new_event(1, keycode_from, 1)] * 100)

        active_preset.save(get_preset_path("Bar Device", "foo preset"))

        self.user_interface.group = groups.find(name="Bar Device")
        self.user_interface.preset_name = "foo preset"
        self.user_interface.on_apply_preset_clicked(None)

        pipe = uinput_write_history_pipe[0]
        # block until the first event is available, indicating that
        # the injector is ready
        write_history = [pipe.recv()]

        # stop
        self.user_interface.on_stop_injecting_clicked(None)

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
        self.editor.set_combination(EventCombination([EV_KEY, 71, 1]))
        self.editor.set_symbol_input_text("a")
        self.user_interface.get("preset_name_input").set_text("asdf")
        self.user_interface.on_rename_button_clicked(None)
        gtk_iteration()
        self.assertEqual(self.user_interface.preset_name, "asdf")
        self.assertEqual(len(active_preset), 1)
        self.user_interface.save_preset()
        self.assertTrue(os.path.exists(get_preset_path("Foo Device", "asdf")))

        with PatchedConfirmDelete(self.user_interface, Gtk.ResponseType.CANCEL):
            self.user_interface.on_delete_preset_clicked(None)
            self.assertTrue(os.path.exists(get_preset_path("Foo Device", "asdf")))
            self.assertEqual(self.user_interface.preset_name, "asdf")
            self.assertEqual(self.user_interface.group.name, "Foo Device")

            with PatchedConfirmDelete(self.user_interface):
                self.user_interface.on_delete_preset_clicked(None)
                self.assertFalse(os.path.exists(get_preset_path("Foo Device", "asdf")))
                self.assertEqual(self.user_interface.preset_name, "new preset")
                self.assertEqual(self.user_interface.group.name, "Foo Device")

    def test_populate_devices(self):
        preset_selection = self.user_interface.get("preset_selection")

        # create two presets
        self.user_interface.get("preset_name_input").set_text("preset 1")
        self.user_interface.on_rename_button_clicked(None)
        self.assertEqual(preset_selection.get_active_id(), "preset 1")

        # to make sure the next preset has a slightly higher timestamp
        time.sleep(0.1)
        self.user_interface.on_create_preset_clicked()
        self.user_interface.get("preset_name_input").set_text("preset 2")
        self.user_interface.on_rename_button_clicked(None)
        self.assertEqual(preset_selection.get_active_id(), "preset 2")

        # select the older one
        preset_selection.set_active_id("preset 1")
        self.assertEqual(self.user_interface.preset_name, "preset 1")

        # add a device that doesn't exist to the dropdown
        unknown_key = "key-1234"
        self.user_interface.device_store.insert(0, [unknown_key, None, "foo"])

        self.user_interface.populate_devices()
        # the newest preset should be selected
        self.assertEqual(self.user_interface.preset_name, "preset 2")

        # the list contains correct entries
        # and the non-existing entry should be removed
        entries = [tuple(entry) for entry in self.user_interface.device_store]
        keys = [entry[0] for entry in self.user_interface.device_store]
        self.assertNotIn(unknown_key, keys)
        self.assertIn("Foo Device", keys)
        self.assertIn(("Foo Device", "input-keyboard", "Foo Device"), entries)
        self.assertIn(("Foo Device 2", "input-mouse", "Foo Device 2"), entries)
        self.assertIn(("Bar Device", "input-keyboard", "Bar Device"), entries)
        self.assertIn(("gamepad", "input-gaming", "gamepad"), entries)

        # it won't crash due to "list index out of range"
        # when `types` is an empty list. Won't show an icon
        groups.find(key="Foo Device 2").types = []
        self.user_interface.populate_devices()
        self.assertIn(
            ("Foo Device 2", None, "Foo Device 2"),
            [tuple(entry) for entry in self.user_interface.device_store],
        )

    def test_shared_presets(self):
        # devices with the same name (but different key because the key is
        # unique) share the same presets.
        # Those devices would usually be of the same model of keyboard for example

        # 1. create a preset
        self.user_interface.on_select_device(FakeDeviceDropdown("Foo Device 2"))
        self.user_interface.on_create_preset_clicked()
        self.add_mapping_via_ui(EventCombination([3, 2, 1]), "qux")
        self.user_interface.get("preset_name_input").set_text("asdf")
        self.user_interface.on_rename_button_clicked(None)
        self.user_interface.save_preset()
        self.assertIn("asdf.json", os.listdir(get_preset_path("Foo Device")))

        # 2. switch to the different device, there should be no preset named asdf
        self.user_interface.on_select_device(FakeDeviceDropdown("Bar Device"))
        self.assertEqual(self.user_interface.preset_name, "new preset")
        self.assertNotIn("asdf.json", os.listdir(get_preset_path("Bar Device")))
        self.assertEqual(self.editor.get_symbol_input_text(), "")

        # 3. switch to the device with the same name as the first one
        self.user_interface.on_select_device(FakeDeviceDropdown("Foo Device"))
        # the newest preset is asdf, it should be automatically selected
        self.assertEqual(self.user_interface.preset_name, "asdf")
        self.assertEqual(self.editor.get_symbol_input_text(), "qux")

    def test_delete_last_preset(self):
        with PatchedConfirmDelete(self.user_interface):
            # add some rows
            for code in range(3):
                self.add_mapping_via_ui(EventCombination([1, code, 1]), "qux")

            self.user_interface.on_delete_preset_clicked()
            # the ui should be clear now
            self.test_gui_clean()
            device_path = f"{CONFIG_PATH}/presets/{self.user_interface.group.key}"
            self.assertTrue(os.path.exists(f"{device_path}/new preset.json"))

            self.user_interface.on_delete_preset_clicked()
            # deleting an empty preset als doesn't do weird stuff
            self.test_gui_clean()
            device_path = f"{CONFIG_PATH}/presets/{self.user_interface.group.key}"
            self.assertTrue(os.path.exists(f"{device_path}/new preset.json"))

    def test_enable_disable_symbol_input(self):
        # should be disabled by default since no key is recorded yet
        self.assertEqual(self.get_unfiltered_symbol_input_text(), SET_KEY_FIRST)
        self.assertFalse(self.editor.get_code_editor().get_sensitive())

        self.editor.enable_symbol_input()
        self.assertEqual(self.get_unfiltered_symbol_input_text(), "")
        self.assertTrue(self.editor.get_text_input().get_sensitive())

        # disable it
        self.editor.disable_symbol_input()
        self.assertFalse(self.editor.get_text_input().get_sensitive())

        # try to enable it by providing a key via set_combination
        self.editor.set_combination(EventCombination((1, 201, 1)))
        self.assertEqual(self.get_unfiltered_symbol_input_text(), "")
        self.assertTrue(self.editor.get_text_input().get_sensitive())

        # disable it again
        self.editor.set_combination(None)
        self.assertFalse(self.editor.get_text_input().get_sensitive())

        # try to enable it via the reader
        self.activate_recording_toggle()
        send_event_to_reader(InputEvent.from_tuple((EV_KEY, 101, 1)))
        self.user_interface.consume_newest_keycode()
        self.assertEqual(self.get_unfiltered_symbol_input_text(), "")
        self.assertTrue(self.editor.get_code_editor().get_sensitive())

        # it wouldn't clear user input, if for whatever reason (a bug?) there is user
        # input in there when enable_symbol_input is called.
        self.editor.set_symbol_input_text("foo")
        self.editor.enable_symbol_input()
        self.assertEqual(self.get_unfiltered_symbol_input_text(), "foo")

    def test_whitespace_symbol(self):
        # test how the editor behaves when the text of a mapping is a whitespace.
        # Caused an "Expected `symbol` not to be empty" error in the past, because
        # the symbol was not stripped of whitespaces and logic was performed that
        # resulted in a call to actually changing the mapping.
        self.add_mapping_via_ui(EventCombination([1, 201, 1]), "a")
        self.add_mapping_via_ui(EventCombination([1, 202, 1]), "b")

        self.select_mapping(1)
        self.assertEqual(self.editor.get_symbol_input_text(), "b")
        self.editor.set_symbol_input_text(" ")

        self.select_mapping(0)
        self.assertEqual(self.editor.get_symbol_input_text(), "a")


class TestAutocompletion(GuiTestBase):
    def press_key(self, keyval):
        event = Gdk.EventKey()
        event.keyval = keyval
        self.editor.autocompletion.navigate(None, event)

    def test_autocomplete_key(self):
        self.add_mapping_via_ui(EventCombination([1, 99, 1]), "")
        source_view = self.editor.get_code_editor()
        self.set_focus(source_view)

        complete_key_name = "Test_Foo_Bar"

        system_mapping.clear()
        system_mapping._set(complete_key_name, 1)

        # it can autocomplete a combination inbetween other things
        incomplete = "qux_1\n +  + qux_2"
        Gtk.TextView.do_insert_at_cursor(source_view, incomplete)
        Gtk.TextView.do_move_cursor(
            source_view,
            Gtk.MovementStep.VISUAL_POSITIONS,
            -8,
            False,
        )
        Gtk.TextView.do_insert_at_cursor(source_view, "foo")

        time.sleep(0.11)
        gtk_iteration()

        autocompletion = self.editor.autocompletion
        self.assertTrue(autocompletion.visible)

        self.press_key(Gdk.KEY_Down)
        self.press_key(Gdk.KEY_Return)

        # the first suggestion should have been selected
        modified_symbol = self.editor.get_symbol_input_text().strip()
        self.assertEqual(modified_symbol, f"qux_1\n + {complete_key_name} + qux_2")

        # try again, but a whitespace completes the word and so no autocompletion
        # should be shown
        Gtk.TextView.do_insert_at_cursor(source_view, " + foo ")

        time.sleep(0.11)
        gtk_iteration()

        self.assertFalse(autocompletion.visible)

    def test_autocomplete_function(self):
        self.add_mapping_via_ui(EventCombination([1, 99, 1]), "")
        source_view = self.editor.get_code_editor()
        self.set_focus(source_view)

        incomplete = "key(KEY_A).\nepea"
        Gtk.TextView.do_insert_at_cursor(source_view, incomplete)

        time.sleep(0.11)
        gtk_iteration()

        autocompletion = self.editor.autocompletion
        self.assertTrue(autocompletion.visible)

        self.press_key(Gdk.KEY_Down)
        self.press_key(Gdk.KEY_Return)

        # the first suggestion should have been selected
        modified_symbol = self.editor.get_symbol_input_text().strip()
        self.assertEqual(modified_symbol, "key(KEY_A).\nrepeat")

    def test_close_autocompletion(self):
        self.add_mapping_via_ui(EventCombination([1, 99, 1]), "")
        source_view = self.editor.get_code_editor()
        self.set_focus(source_view)

        Gtk.TextView.do_insert_at_cursor(source_view, "KEY_")

        time.sleep(0.11)
        gtk_iteration()

        autocompletion = self.editor.autocompletion
        self.assertTrue(autocompletion.visible)

        self.press_key(Gdk.KEY_Down)
        self.press_key(Gdk.KEY_Escape)

        self.assertFalse(autocompletion.visible)

        symbol = self.editor.get_symbol_input_text().strip()
        self.assertEqual(symbol, "KEY_")

    def test_writing_still_works(self):
        self.add_mapping_via_ui(EventCombination([1, 99, 1]), "")
        source_view = self.editor.get_code_editor()
        self.set_focus(source_view)

        Gtk.TextView.do_insert_at_cursor(source_view, "KEY_")

        autocompletion = self.editor.autocompletion

        time.sleep(0.11)
        gtk_iteration()
        self.assertTrue(autocompletion.visible)

        # writing still works while an entry is selected
        self.press_key(Gdk.KEY_Down)

        Gtk.TextView.do_insert_at_cursor(source_view, "A")

        time.sleep(0.11)
        gtk_iteration()
        self.assertTrue(autocompletion.visible)

        Gtk.TextView.do_insert_at_cursor(source_view, "1234foobar")

        time.sleep(0.11)
        gtk_iteration()
        # no key matches this completion, so it closes again
        self.assertFalse(autocompletion.visible)

    def test_cycling(self):
        self.add_mapping_via_ui(EventCombination([1, 99, 1]), "")
        source_view = self.editor.get_code_editor()
        self.set_focus(source_view)

        Gtk.TextView.do_insert_at_cursor(source_view, "KEY_")

        autocompletion = self.editor.autocompletion

        time.sleep(0.11)
        gtk_iteration()
        self.assertTrue(autocompletion.visible)

        self.assertEqual(
            autocompletion.scrolled_window.get_vadjustment().get_value(), 0
        )

        # cycle to the end of the list because there is no element higher than index 0
        self.press_key(Gdk.KEY_Up)
        self.assertGreater(
            autocompletion.scrolled_window.get_vadjustment().get_value(), 0
        )

        # go back to the start, because it can't go down further
        self.press_key(Gdk.KEY_Down)
        self.assertEqual(
            autocompletion.scrolled_window.get_vadjustment().get_value(), 0
        )


if __name__ == "__main__":
    unittest.main()
