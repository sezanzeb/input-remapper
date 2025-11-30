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

import asyncio
import atexit
import multiprocessing
import os
import time
import unittest
from contextlib import contextmanager
from typing import Tuple, List, Optional
from unittest.mock import patch

import evdev
import gi
import sys

from inputremapper.injection.global_uinputs import GlobalUInputs, FrontendUInput, UInput
from inputremapper.injection.mapping_handlers.mapping_parser import MappingParser
from tests.lib.cleanup import cleanup
from tests.lib.constants import EVENT_READ_TIMEOUT
from tests.lib.fixtures import prepare_presets
from tests.lib.logger import logger

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GtkSource", "4")
gi.require_version("GLib", "2.0")
from gi.repository import Gtk, GLib, GtkSource

from inputremapper.configs.mapping import Mapping
from inputremapper.configs.global_config import GlobalConfig
from inputremapper.groups import _Groups
from inputremapper.gui.data_manager import DataManager
from inputremapper.gui.messages.message_broker import (
    MessageBroker,
)
from inputremapper.gui.components.editor import (
    MappingSelectionLabel,
)
from inputremapper.gui.controller import Controller
from inputremapper.gui.reader_service import ReaderService
from inputremapper.gui.utils import gtk_iteration
from inputremapper.gui.user_interface import UserInterface
from inputremapper.configs.input_config import InputCombination, InputConfig
from inputremapper.daemon import Daemon, DaemonProxy
from inputremapper.bin.input_remapper_gtk import InputRemapperGtkBin


# iterate a few times when Gtk.main() is called, but don't block
# there and just continue to the tests while the UI becomes
# unresponsive
Gtk.main = gtk_iteration

# doesn't do much except avoid some Gtk assertion error, whatever:
Gtk.main_quit = lambda: None


def launch() -> Tuple[
    UserInterface,
    Controller,
    DataManager,
    MessageBroker,
    DaemonProxy,
    GlobalConfig,
]:
    """Start input-remapper-gtk."""
    with patch.object(sys, "argv", ["/usr/bin/input-remapper-gtk", "-d"]):
        return_ = InputRemapperGtkBin.main()

    gtk_iteration()
    # otherwise a new handler is added with each call to launch, which
    # spams tons of garbage when all tests finish
    atexit.unregister(InputRemapperGtkBin.stop)
    return return_


def start_reader_service():
    def process():
        global_uinputs = GlobalUInputs(FrontendUInput)
        reader_service = ReaderService(_Groups(), global_uinputs)
        loop = asyncio.new_event_loop()
        loop.run_until_complete(reader_service.run())

    multiprocessing.Process(target=process).start()


def os_system_patch(cmd, original_os_system=os.system):
    # instead of running pkexec, fork instead. This will make
    # the reader-service aware of all the test patches
    if "pkexec input-remapper-control --command start-reader-service" in cmd:
        logger.info("pkexec-patch starting ReaderService process")
        start_reader_service()
        return 0

    return original_os_system(cmd)


@contextmanager
def patch_services():
    """Don't connect to the dbus and don't use pkexec to start the reader-service"""

    def bootstrap_daemon():
        # The daemon gets fresh instances of everything, because as far as I remember
        # it runs in a separate process.
        global_config = GlobalConfig()
        global_uinputs = GlobalUInputs(UInput)
        mapping_parser = MappingParser(global_uinputs)

        return Daemon(
            global_config,
            global_uinputs,
            mapping_parser,
        )

    with (
        patch.object(
            os,
            "system",
            os_system_patch,
        ),
        patch.object(Daemon, "connect", bootstrap_daemon),
    ):
        yield


def clean_up_gui_test(test):
    logger.info("clean_up_gui_test")
    test.controller.stop_injecting()
    gtk_iteration()
    test.user_interface.on_gtk_close()
    test.user_interface.window.destroy()
    gtk_iteration()
    cleanup()

    # do this now, not when all tests are finished
    test.daemon.stop_all()
    if isinstance(test.daemon, Daemon):
        atexit.unregister(test.daemon.stop_all)


class GtkKeyEvent:
    def __init__(self, keyval):
        self.keyval = keyval

    def get_keyval(self):
        return True, self.keyval


@contextmanager
def patch_confirm_delete(
    user_interface: UserInterface,
    response=Gtk.ResponseType.ACCEPT,
):
    original_create_dialog = user_interface._create_dialog

    def _create_dialog_patch(*args, **kwargs):
        """A patch for the deletion confirmation that briefly shows the dialog."""
        confirm_cancel_dialog = original_create_dialog(*args, **kwargs)

        # the emitted signal causes the dialog to close
        GLib.timeout_add(
            100,
            lambda: confirm_cancel_dialog.emit("response", response),
        )

        # don't recursively call the patch
        Gtk.MessageDialog.run(confirm_cancel_dialog)

        confirm_cancel_dialog.run = lambda: response

        return confirm_cancel_dialog

    with patch.object(
        user_interface,
        "_create_dialog",
        _create_dialog_patch,
    ):
        # Tests are run during `yield`
        yield


class GuiTestBase(unittest.TestCase):
    def setUp(self):
        prepare_presets()
        with patch_services():
            (
                self.user_interface,
                self.controller,
                self.data_manager,
                self.message_broker,
                self.daemon,
                self.global_config,
            ) = launch()

        get = self.user_interface.get
        self.device_selection: Gtk.FlowBox = get("device_selection")
        self.preset_selection: Gtk.ComboBoxText = get("preset_selection")
        self.selection_label_listbox: Gtk.ListBox = get("selection_label_listbox")
        self.target_selection: Gtk.ComboBox = get("target-selector")
        self.recording_toggle: Gtk.ToggleButton = get("key_recording_toggle")
        self.recording_status: Gtk.ToggleButton = get("recording_status")
        self.status_bar: Gtk.Statusbar = get("status_bar")
        self.autoload_toggle: Gtk.Switch = get("preset_autoload_switch")
        self.code_editor: GtkSource.View = get("code_editor")
        self.output_box: GtkSource.View = get("output")

        self.delete_preset_btn: Gtk.Button = get("delete_preset")
        self.copy_preset_btn: Gtk.Button = get("copy_preset")
        self.create_preset_btn: Gtk.Button = get("create_preset")
        self.start_injector_btn: Gtk.Button = get("apply_preset")
        self.stop_injector_btn: Gtk.Button = get("stop_injection_preset_page")
        self.rename_btn: Gtk.Button = get("rename-button")
        self.rename_input: Gtk.Entry = get("preset_name_input")
        self.create_mapping_btn: Gtk.Button = get("create_mapping_button")
        self.delete_mapping_btn: Gtk.Button = get("delete-mapping")

        self._test_initial_state()

        self.grab_fails = False

        def grab(_):
            if self.grab_fails:
                raise OSError()

        evdev.InputDevice.grab = grab

        self.global_config._save_config()

        self.throttle(20)

        self.assertIsNotNone(self.data_manager.active_group)
        self.assertIsNotNone(self.data_manager.active_preset)

    def tearDown(self):
        clean_up_gui_test(self)

        # this is important, otherwise it keeps breaking things in the background
        self.assertIsNone(self.data_manager._reader_client._read_timeout)

        self.throttle(20)

    def get_code_input(self):
        buffer = self.code_editor.get_buffer()
        return buffer.get_text(
            buffer.get_start_iter(),
            buffer.get_end_iter(),
            True,
        )

    def _test_initial_state(self):
        # make sure each test deals with the same initial state
        self.assertEqual(self.controller.data_manager, self.data_manager)
        self.assertEqual(self.data_manager.active_group.key, "Foo Device")
        # if the modification-date from `prepare_presets` is not destroyed, preset3
        # should be selected as the newest one
        self.assertEqual(self.data_manager.active_preset.name, "preset3")
        self.assertEqual(self.data_manager.active_mapping.target_uinput, "keyboard")
        self.assertEqual(self.target_selection.get_active_id(), "keyboard")
        self.assertEqual(
            self.data_manager.active_mapping.input_combination,
            InputCombination([InputConfig(type=1, code=5)]),
        )
        self.assertEqual(
            self.data_manager.active_input_config, InputConfig(type=1, code=5)
        )
        self.assertGreater(
            len(self.user_interface.autocompletion._target_key_capabilities), 0
        )

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

    def throttle(self, time_=10):
        """Give GTK some time in ms to process everything."""
        # tests suddenly started to freeze my computer up completely and tests started
        # to fail. By using this (and by optimizing some redundant calls in the gui) it
        # worked again. EDIT: Might have been caused by my broken/bloated ssd. I'll
        # keep it in some places, since it did make the tests more reliable after all.
        for _ in range(time_ // 2):
            gtk_iteration()
            time.sleep(0.002)

    def set_focus(self, widget):
        logger.info("Focusing %s", widget)

        self.user_interface.window.set_focus(widget)

        self.throttle(20)

    def focus_source_view(self):
        # despite the focus and gtk_iterations, gtk never runs the event handlers for
        # the focus-in-event (_update_placeholder), which would clear the placeholder
        # text. Remove it manually, it can't be helped. Fun fact: when the
        # window gets destroyed, gtk runs the handler 10 times for good measure.
        # Lost one hour of my life on GTK again. It's gone! Forever! Use qt next time.
        source_view = self.code_editor
        self.set_focus(source_view)
        self.code_editor.get_buffer().set_text("")
        return source_view

    def get_selection_labels(self) -> List[MappingSelectionLabel]:
        return self.selection_label_listbox.get_children()

    def get_status_text(self):
        status_bar = self.user_interface.get("status_bar")
        return status_bar.get_message_area().get_children()[0].get_label()

    def get_unfiltered_symbol_input_text(self):
        buffer = self.code_editor.get_buffer()
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)

    def select_mapping(self, i: int):
        """Select one of the mappings of a preset.

        Parameters
        ----------
        i
            if -1, will select the last row,
            0 will select the uppermost row.
            1 will select the second row, and so on
        """
        selection_label = self.get_selection_labels()[i]
        self.selection_label_listbox.select_row(selection_label)
        logger.info(
            'Selecting mapping %s "%s"',
            selection_label.combination,
            selection_label.name,
        )
        gtk_iteration()
        return selection_label

    def add_mapping(self, mapping: Optional[Mapping] = None):
        self.controller.create_mapping()
        self.controller.load_mapping(InputCombination.empty_combination())
        gtk_iteration()
        if mapping:
            self.controller.update_mapping(**mapping.dict(exclude_defaults=True))
            gtk_iteration()

    def sleep(self, num_events):
        for _ in range(num_events * 2):
            time.sleep(EVENT_READ_TIMEOUT)
            gtk_iteration()

        time.sleep(1 / 30)  # one window iteration

        gtk_iteration()
