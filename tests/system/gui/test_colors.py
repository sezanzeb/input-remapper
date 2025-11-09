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
from tests.system.gui.gui_test_base import GuiTestBase


@test_setup
class TestColors(GuiTestBase):
    # requires a running ui, otherwise fails with segmentation faults
    def test_get_color_falls_back(self):
        fallback = Gdk.RGBA(0, 0.5, 1, 0.8)

        color = Colors.get_color(["doesnt_exist_1234"], fallback)

        self.assertIsInstance(color, Gdk.RGBA)
        self.assertAlmostEqual(color.red, fallback.red, delta=0.01)
        self.assertAlmostEqual(color.green, fallback.green, delta=0.01)
        self.assertAlmostEqual(color.blue, fallback.blue, delta=0.01)
        self.assertAlmostEqual(color.alpha, fallback.alpha, delta=0.01)

    def test_get_color_works(self):
        fallback = Gdk.RGBA(1, 0, 1, 0.1)

        color = Colors.get_color(
            ["accent_bg_color", "theme_selected_bg_color"], fallback
        )

        self.assertIsInstance(color, Gdk.RGBA)
        self.assertNotAlmostEqual(color.red, fallback.red, delta=0.01)
        self.assertNotAlmostEqual(color.green, fallback.blue, delta=0.01)
        self.assertNotAlmostEqual(color.blue, fallback.green, delta=0.01)
        self.assertNotAlmostEqual(color.alpha, fallback.alpha, delta=0.01)

    def _test_color_wont_fallback(self, get_color, fallback):
        color = get_color()
        self.assertIsInstance(color, Gdk.RGBA)
        if (
            (abs(color.green - fallback.green) < 0.01)
            and (abs(color.red - fallback.red) < 0.01)
            and (abs(color.blue - fallback.blue) < 0.01)
            and (abs(color.alpha - fallback.alpha) < 0.01)
        ):
            raise AssertionError(
                f"Color {color.to_string()} is similar to {fallback.toString()}"
            )

    def test_get_colors(self):
        self._test_color_wont_fallback(Colors.get_accent_color, Colors.fallback_accent)
        self._test_color_wont_fallback(Colors.get_border_color, Colors.fallback_border)
        self._test_color_wont_fallback(
            Colors.get_background_color, Colors.fallback_background
        )
        self._test_color_wont_fallback(Colors.get_base_color, Colors.fallback_base)
        self._test_color_wont_fallback(Colors.get_font_color, Colors.fallback_font)


if __name__ == "__main__":
    unittest.main()
