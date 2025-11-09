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
from typing import Tuple, List, Optional, Iterable
from unittest.mock import patch, MagicMock, call

import evdev
import gi
import sys
from evdev.ecodes import (
    EV_KEY,
    EV_ABS,
    KEY_LEFTSHIFT,
    KEY_A,
    KEY_Q,
    EV_REL,
)

from inputremapper.gui.autocompletion import (
    get_incomplete_parameter,
    get_incomplete_function_name,
)
from inputremapper.injection.global_uinputs import GlobalUInputs, FrontendUInput, UInput
from inputremapper.injection.mapping_handlers.mapping_parser import MappingParser
from inputremapper.input_event import InputEvent
from tests.system.gui.test_components import FlowBoxTestUtils
from tests.lib.cleanup import cleanup
from tests.lib.constants import EVENT_READ_TIMEOUT
from tests.lib.fixtures import fixtures
from tests.lib.fixtures import prepare_presets
from tests.lib.logger import logger
from tests.lib.pipes import push_event, push_events, uinput_write_history_pipe
from tests.lib.spy import spy

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GtkSource", "4")
gi.require_version("GLib", "2.0")
from gi.repository import Gtk, GLib, Gdk, GtkSource

from inputremapper.configs.keyboard_layout import keyboard_layout
from inputremapper.configs.mapping import Mapping
from inputremapper.configs.paths import PathUtils
from inputremapper.configs.global_config import GlobalConfig
from inputremapper.groups import _Groups
from inputremapper.gui.data_manager import DataManager
from inputremapper.gui.messages.message_broker import (
    MessageBroker,
    MessageType,
)
from inputremapper.gui.messages.message_data import StatusData, CombinationRecorded
from inputremapper.gui.components.editor import (
    MappingSelectionLabel,
    SET_KEY_FIRST,
    CodeEditor,
)
from inputremapper.gui.components.device_groups import DeviceGroupEntry
from inputremapper.gui.controller import Controller
from inputremapper.gui.reader_service import ReaderService
from inputremapper.gui.utils import gtk_iteration, Colors, debounce, debounce_manager
from inputremapper.gui.user_interface import UserInterface
from inputremapper.injection.injector import InjectorState
from inputremapper.configs.input_config import InputCombination, InputConfig
from inputremapper.daemon import Daemon, DaemonProxy
from inputremapper.bin.input_remapper_gtk import InputRemapperGtkBin

from tests.lib.test_setup import test_setup
from tests.system.gui.gui_test_base import (
    launch,
    start_reader_service,
    clean_up_gui_test,
)


@test_setup
class TestGroupsFromReaderService(unittest.TestCase):
    def patch_os_system(self):
        def os_system(cmd, original_os_system=os.system):
            # instead of running pkexec, fork instead. This will make
            # the reader-service aware of all the test patches
            if "pkexec input-remapper-control --command start-reader-service" in cmd:
                # don't start the reader-service just log that it was.
                self.reader_service_started()
                return 0

            return original_os_system(cmd)

        self.os_system_patch = patch.object(
            os,
            "system",
            os_system,
        )

        # this is already part of the test. we need a bit of patching and hacking
        # because we want to discover the groups as early a possible, to reduce startup
        # time for the application
        self.os_system_patch.start()

    def bootstrap_daemon(self):
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

    def patch_daemon(self):
        # don't try to connect, return an object instance of it instead
        self.daemon_connect_patch = patch.object(
            Daemon,
            "connect",
            lambda: self.bootstrap_daemon(),
        )
        self.daemon_connect_patch.start()

    def setUp(self):
        self.reader_service_started = MagicMock()
        self.patch_os_system()
        self.patch_daemon()

        (
            self.user_interface,
            self.controller,
            self.data_manager,
            self.message_broker,
            self.daemon,
            self.global_config,
        ) = launch()

    def tearDown(self):
        clean_up_gui_test(self)
        self.os_system_patch.stop()
        self.daemon_connect_patch.stop()

    def test_knows_devices(self):
        # verify that it is working as expected. The gui doesn't have knowledge
        # of groups until the root-reader-service provides them
        self.data_manager._reader_client.groups.set_groups([])
        gtk_iteration()
        self.reader_service_started.assert_called()
        self.assertEqual(len(self.data_manager.get_group_keys()), 0)

        # start the reader-service delayed
        start_reader_service()
        # perform some iterations so that the reader ends up reading from the pipes
        # which will make it receive devices.
        for _ in range(10):
            time.sleep(0.02)
            gtk_iteration()

        self.assertIn("Foo Device 2", self.data_manager.get_group_keys())
        self.assertIn("Foo Device 2", self.data_manager.get_group_keys())
        self.assertIn("Bar Device", self.data_manager.get_group_keys())
        self.assertIn("gamepad", self.data_manager.get_group_keys())
        self.assertEqual(self.data_manager.active_group.name, "Foo Device")


if __name__ == "__main__":
    unittest.main()
