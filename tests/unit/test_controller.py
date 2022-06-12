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
import builtins
import json
import os.path
import unittest
from dataclasses import dataclass
from unittest.mock import patch, MagicMock
from typing import Tuple, List, Any

import gi

from inputremapper.injection.injector import (
    RUNNING,
    FAILED,
    NO_GRAB,
    UPGRADE_EVDEV,
    UNKNOWN,
)
from inputremapper.input_event import InputEvent

gi.require_version("Gtk", "3.0")
gi.require_version("GLib", "2.0")
gi.require_version("GtkSource", "4")
from gi.repository import Gtk

# from inputremapper.gui.helper import is_helper_running
from inputremapper.event_combination import EventCombination
from inputremapper.groups import _Groups
from inputremapper.gui.data_bus import (
    DataBus,
    MessageType,
    Signal,
    UInputsData,
    GroupsData,
    GroupData,
    PresetData,
    StatusData,
    CombinationUpdate,
    CombinationRecorded,
)
from inputremapper.gui.reader import Reader
from inputremapper.gui.utils import CTX_ERROR, CTX_APPLY
from inputremapper.gui.gettext import _
from inputremapper.injection.global_uinputs import GlobalUInputs
from inputremapper.configs.mapping import Mapping, UIMapping, MappingData
from tests.test import (
    quick_cleanup,
    get_key_mapping,
    FakeDaemonProxy,
    fixtures,
    prepare_presets,
)
from inputremapper.configs.global_config import global_config, GlobalConfig
from inputremapper.gui.controller import Controller, MAPPING_DEFAULTS
from inputremapper.gui.data_manager import DataManager, DEFAULT_PRESET_NAME
from inputremapper.configs.paths import get_preset_path, get_config_path
from inputremapper.configs.preset import Preset


@dataclass
class DummyGui:
    confirm_delete_ret: Gtk.ResponseType = Gtk.ResponseType.ACCEPT
    connect_calls: int = 0
    disconnect_calls: int = 0

    def confirm_delete(self, msg):
        return self.confirm_delete_ret

    def connect_shortcuts(self):
        self.connect_calls += 1

    def disconnect_shortcuts(self):
        self.disconnect_calls += 1


class TestError(Exception):
    pass


def get_controller_objects(
    data_bus=None, data_manager=None, user_interface=None
) -> Tuple[DataBus, DataManager, Any]:
    """useful to supply directly to the Controller.__init__"""
    if not data_bus:
        data_bus = DataBus()

    if not data_manager:
        uinputs = GlobalUInputs()
        uinputs.prepare_all()
        data_manager = DataManager(
            data_bus,
            GlobalConfig(),
            Reader(data_bus, _Groups()),
            FakeDaemonProxy(),
            uinputs,
        )

    if not user_interface:
        user_interface = DummyGui()
    return data_bus, data_manager, user_interface


class TestController(unittest.TestCase):
    def tearDown(self) -> None:
        quick_cleanup()

    def test_should_get_newest_group(self):
        """get_a_group should the newest group"""

        def f():
            return "foo"

        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        data_manager.get_newest_group_key = f

        self.assertEqual(controller.get_a_group(), "foo")

    def test_should_get_any_group(self):
        """get_a_group should return a valid group"""

        def f():
            raise FileNotFoundError()

        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        data_manager.get_newest_group_key = f

        fixture_keys = [
            fixture.get("group_key") or fixture.get("name")
            for fixture in fixtures.values()
        ]
        self.assertIn(controller.get_a_group(), fixture_keys)

    def test_should_get_newest_preset(self):
        """get_a_group should the newest group"""

        def f():
            return "bar"

        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        data_manager.get_newest_preset_name = f
        data_manager.load_group("Foo Device")

        self.assertEqual(controller.get_a_preset(), "bar")

    def test_should_get_any_preset(self):
        """get_a_preset should return a new preset if none exist"""

        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        data_manager.load_group("Foo Device")

        self.assertEqual(controller.get_a_preset(), "new preset")  # the default name

    def test_on_init_should_provide_uinputs(self):
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        calls: List[UInputsData] = []

        def f(data):
            calls.append(data)

        data_bus.subscribe(MessageType.uinputs, f)
        data_bus.signal(MessageType.init)
        self.assertEqual(
            ["keyboard", "gamepad", "mouse"], list(calls[-1].uinputs.keys())
        )

    def test_on_init_should_provide_groups(self):
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        calls: List[GroupsData] = []

        def f(groups):
            calls.append(groups)

        data_bus.subscribe(MessageType.groups, f)
        data_bus.signal(MessageType.init)
        self.assertEqual(
            ["Foo Device", "Foo Device 2", "Bar Device", "gamepad"],
            list(calls[-1].groups.keys()),
        )

    def test_on_init_should_provide_a_group(self):
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        calls: List[GroupData] = []

        def f(data):
            calls.append(data)

        data_bus.subscribe(MessageType.group, f)
        data_bus.signal(MessageType.init)
        self.assertGreaterEqual(len(calls), 1)

    def test_on_init_should_provide_a_preset(self):
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        calls: List[PresetData] = []

        def f(data):
            calls.append(data)

        data_bus.subscribe(MessageType.preset, f)
        data_bus.signal(MessageType.init)
        self.assertGreaterEqual(len(calls), 1)

    def test_on_init_should_provide_a_mapping(self):
        """only if there is one"""
        prepare_presets()
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        calls: List[MappingData] = []

        def f(data):
            calls.append(data)

        data_bus.subscribe(MessageType.mapping, f)
        data_bus.signal(MessageType.init)
        self.assertTrue(calls[-1].is_valid())

    def test_on_init_should_provide_a_default_mapping(self):
        """if there is no real preset available"""
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        calls: List[MappingData] = []

        def f(data):
            calls.append(data)

        data_bus.subscribe(MessageType.mapping, f)
        data_bus.signal(MessageType.init)
        for m in calls:
            self.assertEqual(m, UIMapping())

    def test_on_init_should_provide_status_if_helper_is_not_running(self):
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        calls: List[StatusData] = []

        def f(data):
            calls.append(data)

        data_bus.subscribe(MessageType.status, f)
        with patch("inputremapper.gui.controller.is_helper_running", lambda: False):
            data_bus.signal(MessageType.init)
        self.assertIn(StatusData(CTX_ERROR, _("The helper did not start")), calls)

    def test_on_init_should_not_provide_status_if_helper_is_running(self):
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        calls: List[StatusData] = []

        def f(data):
            calls.append(data)

        data_bus.subscribe(MessageType.status, f)
        with patch("inputremapper.gui.controller.is_helper_running", lambda: True):
            data_bus.signal(MessageType.init)

        self.assertNotIn(StatusData(CTX_ERROR, _("The helper did not start")), calls)

    def test_on_load_group_should_provide_preset(self):
        def f(*_):
            raise TestError()

        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        data_manager.load_preset = f
        self.assertRaises(TestError, controller.load_group, group_key="Foo Device")

    def test_on_load_group_should_provide_mapping(self):
        """if there is one"""
        prepare_presets()
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        calls: List[MappingData] = []

        def f(data):
            calls.append(data)

        data_bus.subscribe(MessageType.mapping, f)
        controller.load_group(group_key="Foo Device 2")
        self.assertTrue(calls[-1].is_valid())

    def test_on_load_group_should_provide_default_mapping(self):
        """if there is none"""
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        calls: List[MappingData] = []

        def f(data):
            calls.append(data)

        data_bus.subscribe(MessageType.mapping, f)

        controller.load_group(group_key="Foo Device")
        for m in calls:
            self.assertEqual(m, UIMapping())

    def test_on_load_preset_should_provide_mapping(self):
        """if there is one"""
        prepare_presets()
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        data_manager.load_group("Foo Device 2")
        calls: List[MappingData] = []

        def f(data):
            calls.append(data)

        data_bus.subscribe(MessageType.mapping, f)
        controller.load_preset(name="preset2")
        self.assertTrue(calls[-1].is_valid())

    def test_on_load_preset_should_provide_default_mapping(self):
        """if there is none"""
        Preset(get_preset_path("Foo Device", "bar")).save()
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        data_manager.load_group("Foo Device 2")
        calls: List[MappingData] = []

        def f(data):
            calls.append(data)

        data_bus.subscribe(MessageType.mapping, f)
        controller.load_preset(name="bar")
        for m in calls:
            self.assertEqual(m, UIMapping())

    def test_on_delete_preset_asks_for_confirmation(self):
        prepare_presets()
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        def f(*_):
            raise TestError()

        user_interface.confirm_delete = f

        data_bus.signal(MessageType.init)
        self.assertRaises(TestError, controller.delete_preset)

    def test_deletes_preset_when_confirmed(self):
        prepare_presets()
        self.assertTrue(os.path.isfile(get_preset_path("Foo Device", "preset2")))
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        user_interface.confirm_delete_ret = Gtk.ResponseType.ACCEPT

        path = get_preset_path("Foo Device", "preset2")
        controller.delete_preset()
        self.assertFalse(os.path.exists(get_preset_path("Foo Device", "preset2")))

    def test_does_not_delete_preset_when_not_confirmed(self):
        prepare_presets()
        self.assertTrue(os.path.isfile(get_preset_path("Foo Device", "preset2")))
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        user_interface.confirm_delete_ret = Gtk.ResponseType.CANCEL

        path = get_preset_path("Foo Device", "preset2")
        controller.delete_preset()
        self.assertTrue(os.path.isfile(get_preset_path("Foo Device", "preset2")))

    def test_copy_preset(self):
        prepare_presets()
        self.assertTrue(os.path.isfile(get_preset_path("Foo Device", "preset2")))

        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        controller.copy_preset()

        self.assertTrue(os.path.exists(get_preset_path("Foo Device", "preset2")))
        self.assertTrue(os.path.exists(get_preset_path("Foo Device", "preset2 copy")))

    def test_copy_preset_should_add_number(self):
        prepare_presets()
        self.assertTrue(os.path.isfile(get_preset_path("Foo Device", "preset2")))

        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        controller.copy_preset()  # creates "preset2 copy"
        data_manager.load_preset("preset2")
        controller.copy_preset()  # creates "preset2 copy 2"

        self.assertTrue(os.path.exists(get_preset_path("Foo Device", "preset2")))
        self.assertTrue(os.path.exists(get_preset_path("Foo Device", "preset2 copy")))
        self.assertTrue(
            os.path.exists(get_preset_path("Foo Device", "preset2 copy 2"))
        )

    def test_copy_preset_should_increment_existing_number(self):
        prepare_presets()
        self.assertTrue(os.path.isfile(get_preset_path("Foo Device", "preset2")))

        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        controller.copy_preset()  # creates "preset2 copy"
        data_manager.load_preset("preset2")
        controller.copy_preset()  # creates "preset2 copy 2"
        data_manager.load_preset("preset2")
        controller.copy_preset()  # creates "preset2 copy 3"

        self.assertTrue(os.path.exists(get_preset_path("Foo Device", "preset2")))
        self.assertTrue(os.path.exists(get_preset_path("Foo Device", "preset2 copy")))
        self.assertTrue(
            os.path.exists(get_preset_path("Foo Device", "preset2 copy 2"))
        )
        self.assertTrue(
            os.path.exists(get_preset_path("Foo Device", "preset2 copy 3"))
        )

    def test_copy_preset_should_not_append_copy_twice(self):
        prepare_presets()
        self.assertTrue(os.path.isfile(get_preset_path("Foo Device", "preset2")))

        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        controller.copy_preset()  # creates "preset2 copy"
        controller.copy_preset()  # creates "preset2 copy 2" not "preset2 copy copy"

        self.assertTrue(os.path.exists(get_preset_path("Foo Device", "preset2")))
        self.assertTrue(os.path.exists(get_preset_path("Foo Device", "preset2 copy")))
        self.assertTrue(
            os.path.exists(get_preset_path("Foo Device", "preset2 copy 2"))
        )

    def test_copy_preset_should_not_append_copy_to_copy_with_number(self):
        prepare_presets()
        self.assertTrue(os.path.isfile(get_preset_path("Foo Device", "preset2")))

        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        controller.copy_preset()  # creates "preset2 copy"
        data_manager.load_preset("preset2")
        controller.copy_preset()  # creates "preset2 copy 2"
        controller.copy_preset()  # creates "preset2 copy 3" not "preset2 copy 2 copy"

        self.assertTrue(os.path.exists(get_preset_path("Foo Device", "preset2")))
        self.assertTrue(os.path.exists(get_preset_path("Foo Device", "preset2 copy")))
        self.assertTrue(
            os.path.exists(get_preset_path("Foo Device", "preset2 copy 2"))
        )
        self.assertTrue(
            os.path.exists(get_preset_path("Foo Device", "preset2 copy 3"))
        )

    def test_rename_preset(self):
        prepare_presets()
        self.assertTrue(os.path.isfile(get_preset_path("Foo Device", "preset2")))
        self.assertFalse(os.path.exists(get_preset_path("Foo Device", "foo")))

        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        controller.rename_preset(new_name="foo")

        self.assertFalse(os.path.exists(get_preset_path("Foo Device", "preset2")))
        self.assertTrue(os.path.exists(get_preset_path("Foo Device", "foo")))

    def test_rename_preset_should_pick_available_name(self):
        prepare_presets()
        self.assertTrue(os.path.exists(get_preset_path("Foo Device", "preset2")))
        self.assertTrue(os.path.exists(get_preset_path("Foo Device", "preset3")))
        self.assertFalse(os.path.exists(get_preset_path("Foo Device", "preset3 2")))

        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        data_manager.load_group("Foo Device")
        data_manager.load_preset("preset2")
        controller.rename_preset(new_name="preset3")

        self.assertFalse(os.path.exists(get_preset_path("Foo Device", "preset2")))
        self.assertTrue(os.path.exists(get_preset_path("Foo Device", "preset3")))
        self.assertTrue(os.path.exists(get_preset_path("Foo Device", "preset3 2")))

    def test_rename_preset_should_not_rename_to_empty_name(self):
        prepare_presets()
        self.assertTrue(os.path.exists(get_preset_path("Foo Device", "preset2")))

        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        data_manager.load_group("Foo Device")
        data_manager.load_preset("preset2")
        controller.rename_preset(new_name="")

        self.assertTrue(os.path.exists(get_preset_path("Foo Device", "preset2")))

    def test_rename_preset_should_not_update_same_name(self):
        """when the new name is the same as the current name"""
        prepare_presets()
        self.assertTrue(os.path.exists(get_preset_path("Foo Device", "preset2")))

        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        controller.rename_preset(new_name="preset2")

        self.assertTrue(os.path.exists(get_preset_path("Foo Device", "preset2")))
        self.assertFalse(os.path.exists(get_preset_path("Foo Device", "preset2 2")))

    def test_on_add_preset_uses_default_name(self):
        self.assertFalse(
            os.path.exists(get_preset_path("Foo Device", DEFAULT_PRESET_NAME))
        )

        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        data_manager.load_group("Foo Device 2")

        controller.add_preset()
        self.assertTrue(os.path.exists(get_preset_path("Foo Device", "new preset")))

    def test_on_add_preset_uses_provided_name(self):
        self.assertFalse(os.path.exists(get_preset_path("Foo Device", "foo")))

        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        data_manager.load_group("Foo Device 2")

        controller.add_preset(name="foo")
        self.assertTrue(os.path.exists(get_preset_path("Foo Device", "foo")))

    def test_on_add_preset_shows_permission_error_status(self):
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        data_manager.load_group("Foo Device 2")

        msg = None

        def f(data):
            nonlocal msg
            msg = data

        data_bus.subscribe(MessageType.status, f)
        mock = MagicMock(side_effect=PermissionError)
        with patch("inputremapper.configs.preset.Preset.save", mock):
            controller.add_preset("foo")

        mock.assert_called()
        self.assertIsNotNone(msg)
        self.assertIn("Permission denied", msg.msg)

    def test_on_update_mapping(self):
        """update_mapping should call data_manager.update_mapping
        this ensures mapping_changed is emitted
        """
        prepare_presets()
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        data_manager.load_mapping(combination=EventCombination("1,4,1"))

        def f(**_):
            raise TestError()

        data_manager.update_mapping = f
        self.assertRaises(
            TestError,
            controller.update_mapping,
            name="foo",
            output_symbol="f",
            release_timeout=0.3,
        )

    def test_create_mapping_will_load_the_created_mapping(self):
        prepare_presets()
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")

        calls: List[MappingData] = []

        def f(data):
            calls.append(data)

        data_bus.subscribe(MessageType.mapping, f)
        controller.create_mapping()

        self.assertEqual(calls[-1], UIMapping(**MAPPING_DEFAULTS))

    def test_create_mapping_should_not_create_multiple_empty_mappings(self):
        prepare_presets()
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        controller.create_mapping()  # create a first empty mapping

        calls = []

        def f(data):
            calls.append(data)

        data_bus.subscribe(MessageType.mapping, f)
        data_bus.subscribe(MessageType.preset, f)

        controller.create_mapping()  # try to create a second one
        self.assertEqual(len(calls), 0)

    def test_delete_mapping_asks_for_confirmation(self):
        prepare_presets()
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        def f(*_):
            raise TestError()

        user_interface.confirm_delete = f

        data_bus.signal(MessageType.init)
        self.assertRaises(TestError, controller.delete_mapping)

    def test_deletes_mapping_when_confirmed(self):
        prepare_presets()
        self.assertTrue(os.path.isfile(get_preset_path("Foo Device", "preset2")))
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        data_manager.load_mapping(EventCombination("1,3,1"))
        user_interface.confirm_delete_ret = Gtk.ResponseType.ACCEPT

        controller.delete_mapping()
        controller.save()

        preset = Preset(get_preset_path("Foo Device", "preset2"))
        preset.load()
        self.assertIsNone(preset.get_mapping(EventCombination("1,3,1")))

    def test_does_not_delete_mapping_when_not_confirmed(self):
        prepare_presets()
        self.assertTrue(os.path.isfile(get_preset_path("Foo Device", "preset2")))
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        data_manager.load_mapping(EventCombination("1,3,1"))
        user_interface.confirm_delete_ret = Gtk.ResponseType.CANCEL

        controller.delete_mapping()
        controller.save()

        preset = Preset(get_preset_path("Foo Device", "preset2"))
        preset.load()
        self.assertIsNotNone(preset.get_mapping(EventCombination("1,3,1")))

    def test_should_update_combination(self):
        """when combination is free"""
        prepare_presets()
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        data_manager.load_mapping(EventCombination.from_string("1,3,1"))

        calls: List[CombinationUpdate] = []

        def f(data):
            calls.append(data)

        data_bus.subscribe(MessageType.combination_update, f)
        controller.update_combination(EventCombination.from_string("1,10,1"))
        self.assertEqual(
            calls[0],
            CombinationUpdate(
                EventCombination.from_string("1,3,1"),
                EventCombination.from_string("1,10,1"),
            ),
        )

    def test_should_not_update_combination(self):
        """when combination is already used"""
        prepare_presets()
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        data_manager.load_mapping(EventCombination.from_string("1,3,1"))

        calls: List[CombinationUpdate] = []

        def f(data):
            calls.append(data)

        data_bus.subscribe(MessageType.combination_update, f)
        controller.update_combination(EventCombination.from_string("1,4,1"))
        self.assertEqual(len(calls), 0)

    def test_key_recording_disables_gui_shortcuts(self):
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        self.assertEqual(user_interface.disconnect_calls, 0)
        controller.start_key_recording()
        self.assertEqual(user_interface.disconnect_calls, 1)

    def test_key_recording_enables_gui_shortcuts_when_finished(self):
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        controller.start_key_recording()

        self.assertEqual(user_interface.connect_calls, 0)
        data_bus.signal(MessageType.recording_finished)
        self.assertEqual(user_interface.connect_calls, 1)

    def test_key_recording_enables_gui_shortcuts_when_stopped(self):
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        controller.start_key_recording()

        self.assertEqual(user_interface.connect_calls, 0)
        controller.stop_key_recording()
        self.assertEqual(user_interface.connect_calls, 1)

    def test_key_recording_updates_mapping_combination(self):
        prepare_presets()
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        data_manager.load_mapping(EventCombination.from_string("1,3,1"))

        calls: List[CombinationUpdate] = []

        def f(data):
            calls.append(data)

        data_bus.subscribe(MessageType.combination_update, f)

        controller.start_key_recording()
        data_bus.send(CombinationRecorded(EventCombination.from_string("1,10,1")))
        self.assertEqual(
            calls[0],
            CombinationUpdate(
                EventCombination.from_string("1,3,1"),
                EventCombination.from_string("1,10,1"),
            ),
        )
        data_bus.send(CombinationRecorded(EventCombination.from_string("1,10,1+1,3,1")))
        self.assertEqual(
            calls[1],
            CombinationUpdate(
                EventCombination.from_string("1,10,1"),
                EventCombination.from_string("1,10,1+1,3,1"),
            ),
        )

    def test_no_key_recording_when_not_started(self):
        prepare_presets()
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        data_manager.load_mapping(EventCombination.from_string("1,3,1"))

        calls: List[CombinationUpdate] = []

        def f(data):
            calls.append(data)

        data_bus.subscribe(MessageType.combination_update, f)

        data_bus.send(CombinationRecorded(EventCombination.from_string("1,10,1")))
        self.assertEqual(len(calls), 0)

    def test_key_recording_stops_when_finished(self):
        prepare_presets()
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        data_manager.load_mapping(EventCombination.from_string("1,3,1"))

        calls: List[CombinationUpdate] = []

        def f(data):
            calls.append(data)

        data_bus.subscribe(MessageType.combination_update, f)

        controller.start_key_recording()
        data_bus.send(CombinationRecorded(EventCombination.from_string("1,10,1")))
        data_bus.signal(MessageType.recording_finished)
        data_bus.send(CombinationRecorded(EventCombination.from_string("1,10,1+1,3,1")))

        self.assertEqual(len(calls), 1)  # only the first was processed

    def test_key_recording_stops_when_stopped(self):
        prepare_presets()
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        data_manager.load_mapping(EventCombination.from_string("1,3,1"))

        calls: List[CombinationUpdate] = []

        def f(data):
            calls.append(data)

        data_bus.subscribe(MessageType.combination_update, f)

        controller.start_key_recording()
        data_bus.send(CombinationRecorded(EventCombination.from_string("1,10,1")))
        controller.stop_key_recording()
        data_bus.send(CombinationRecorded(EventCombination.from_string("1,10,1+1,3,1")))

        self.assertEqual(len(calls), 1)  # only the first was processed

    def test_start_injecting_shows_status_when_preset_empty(self):
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        data_manager.load_group("Foo Device 2")
        data_manager.create_preset("foo")
        data_manager.load_preset("foo")
        calls: List[StatusData] = []

        def f(data):
            calls.append(data)

        data_bus.subscribe(MessageType.status, f)

        def f2():
            raise AssertionError("Injection started unexpectedly")

        data_manager.start_injecting = f2
        controller.start_injecting()

        self.assertEqual(
            calls[-1], StatusData(CTX_ERROR, _("You need to add keys and save first"))
        )

    def test_start_injecting_warns_about_btn_left(self):
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        data_manager.load_group("Foo Device 2")
        data_manager.create_preset("foo")
        data_manager.load_preset("foo")
        data_manager.create_mapping()
        data_manager.update_mapping(
            event_combination=EventCombination(InputEvent.btn_left()),
            target_uinput="keyboard",
            output_symbol="a",
        )
        calls: List[StatusData] = []

        def f(data):
            calls.append(data)

        data_bus.subscribe(MessageType.status, f)

        def f2():
            raise AssertionError("Injection started unexpectedly")

        data_manager.start_injecting = f2
        controller.start_injecting()

        self.assertEqual(calls[-1].ctx_id, CTX_ERROR)
        self.assertIn("BTN_LEFT", calls[-1].tooltip)

    def test_start_injecting_starts_with_btn_left_on_second_try(self):
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        data_manager.load_group("Foo Device 2")
        data_manager.create_preset("foo")
        data_manager.load_preset("foo")
        data_manager.create_mapping()
        data_manager.update_mapping(
            event_combination=EventCombination(InputEvent.btn_left()),
            target_uinput="keyboard",
            output_symbol="a",
        )

        def f2():
            raise TestError()

        data_manager.start_injecting = f2
        controller.start_injecting()
        self.assertRaises(TestError, controller.start_injecting)

    def test_start_injecting_starts_with_btn_left_when_mapped_to_other_button(self):
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        data_manager.load_group("Foo Device 2")
        data_manager.create_preset("foo")
        data_manager.load_preset("foo")
        data_manager.create_mapping()
        data_manager.update_mapping(
            event_combination=EventCombination(InputEvent.btn_left()),
            target_uinput="keyboard",
            output_symbol="a",
        )
        data_manager.create_mapping()
        data_manager.load_mapping(EventCombination.empty_combination())
        data_manager.update_mapping(
            event_combination=EventCombination.from_string("1,5,1"),
            target_uinput="mouse",
            output_symbol="BTN_LEFT",
        )

        mock = MagicMock(return_value=True)
        data_manager.start_injecting = mock
        controller.start_injecting()
        mock.assert_called()

    def test_start_injecting_shows_status(self):
        prepare_presets()
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        calls: List[StatusData] = []

        def f(data):
            calls.append(data)

        data_bus.subscribe(MessageType.status, f)
        mock = MagicMock(return_value=True)
        data_manager.start_injecting = mock
        controller.start_injecting()

        mock.assert_called()
        self.assertEqual(calls[0], StatusData(CTX_APPLY, _("Starting injection...")))

    def test_start_injecting_shows_failure_status(self):
        prepare_presets()
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        calls: List[StatusData] = []

        def f(data):
            calls.append(data)

        data_bus.subscribe(MessageType.status, f)
        mock = MagicMock(return_value=False)
        data_manager.start_injecting = mock
        controller.start_injecting()

        mock.assert_called()
        self.assertEqual(
            calls[0],
            StatusData(
                CTX_APPLY,
                _("Failed to apply preset %s") % data_manager.active_preset.name,
            ),
        )

    def test_start_injecting_adds_timeout_to_update_injector_status(self):
        prepare_presets()
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")

        with patch("inputremapper.gui.controller.GLib.timeout_add") as mock:
            controller.start_injecting()
            mock.assert_called_with(100, controller.show_injection_result)

    def test_stop_injecting_shows_status(self):
        prepare_presets()
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        calls: List[StatusData] = []

        def f(data):
            calls.append(data)

        data_bus.subscribe(MessageType.status, f)
        mock = MagicMock()
        data_manager.stop_injecting = mock
        controller.stop_injecting()

        mock.assert_called()
        self.assertEqual(
            calls[-1], StatusData(CTX_APPLY, _("Applied the system default"))
        )

    def test_show_injection_result(self):
        prepare_presets()
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        controller.start_injecting()

        mock = MagicMock(return_value=RUNNING)
        data_manager.get_state = mock
        calls: List[StatusData] = []

        def f(data):
            calls.append(data)

        data_bus.subscribe(MessageType.status, f)

        assert not controller.show_injection_result()
        self.assertEqual(calls[-1].msg, _("Applied preset %s") % "preset2")

        mock.return_value = FAILED
        assert not controller.show_injection_result()
        self.assertEqual(calls[-1].msg, _("Failed to apply preset %s") % "preset2")

        mock.return_value = NO_GRAB
        assert not controller.show_injection_result()
        self.assertEqual(calls[-1].msg, "The device was not grabbed")

        mock.return_value = UPGRADE_EVDEV
        assert not controller.show_injection_result()
        self.assertEqual(calls[-1].msg, "Upgrade python-evdev")

        mock.return_value = UNKNOWN
        assert controller.show_injection_result()

    def test_close(self):
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        mock_save = MagicMock()
        listener = MagicMock()
        data_bus.subscribe(MessageType.terminate, listener)
        data_manager.save = mock_save

        controller.close()
        mock_save.assert_called()
        listener.assert_called()

    def test_set_autoload_refreshes_service_config(self):
        prepare_presets()
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")

        with patch.object(data_manager, "refresh_service_config_path") as mock:
            controller.set_autoload(True)
            mock.assert_called()
