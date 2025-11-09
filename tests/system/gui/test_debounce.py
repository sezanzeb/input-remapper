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
