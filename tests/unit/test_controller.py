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
import json
import os.path
import unittest
from typing import Tuple, List, Any

import gi

from inputremapper.event_combination import EventCombination
from inputremapper.gui.data_bus import (
    DataBus,
    MessageType,
    Signal,
    UInputsData,
    GroupsData,
    GroupData,
    PresetData,
)

gi.require_version("Gtk", "3.0")
gi.require_version("GLib", "2.0")
gi.require_version("GtkSource", "4")
from gi.repository import Gtk

from inputremapper.configs.mapping import Mapping, UIMapping, MappingData
from tests.test import (
    quick_cleanup,
    get_key_mapping,
    FakeDaemonProxy,
    get_backend,
    fixtures,
)

from inputremapper.configs.global_config import global_config, GlobalConfig
from inputremapper.gui.controller import Controller
from inputremapper.gui.data_manager import DataManager, DEFAULT_PRESET_NAME
from inputremapper.configs.paths import get_preset_path, get_config_path
from inputremapper.configs.preset import Preset


def prepare_presets():
    preset1 = Preset(get_preset_path("Foo Device", "preset1"))
    preset1.add(get_key_mapping(combination="1,1,1", output_symbol="b"))
    preset1.add(get_key_mapping(combination="1,2,1"))
    preset1.save()

    preset2 = Preset(get_preset_path("Foo Device 2", "preset2"))
    preset2.add(get_key_mapping(combination="1,3,1"))
    preset2.add(get_key_mapping(combination="1,4,1"))
    preset2.save()

    preset3 = Preset(get_preset_path("Foo Device 2", "preset3"))
    preset3.add(get_key_mapping(combination="1,5,1"))
    preset3.save()

    with open(get_config_path("config.json"), "w") as file:
        json.dump({"autoload": {"Foo Device 2": "preset2"}}, file, indent=4)

    global_config.load_config()

    return preset1, preset2, preset3


class DummyGui:
    confirm_delete_ret = Gtk.ResponseType.ACCEPT

    def confirm_delete(self, msg):
        return self.confirm_delete_ret


class TestError(Exception):
    pass


def get_controller_objects(
    data_bus=None, data_manager=None, user_interface=None
) -> Tuple[DataBus, DataManager, Any]:
    """useful to supply directly to the Controller.__init__"""
    if not data_bus:
        data_bus = DataBus()

    if not data_manager:
        backed = get_backend(data_bus=data_bus)
        data_manager = DataManager(data_bus, GlobalConfig(), backed)

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
        data_manager.newest_group = f

        self.assertEqual(controller.get_a_group(), "foo")

    def test_should_get_any_group(self):
        """get_a_group should return a valid group"""

        def f():
            raise FileNotFoundError()

        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        data_manager.newest_group = f

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
        data_manager.newest_preset = f
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

    def test_on_load_group_should_provide_preset(self):
        def f(*_):
            raise TestError()

        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        data_manager.load_preset = f
        self.assertRaises(TestError, controller.on_load_group, group_key="Foo Device")

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
        controller.on_load_group(group_key="Foo Device 2")
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

        controller.on_load_group(group_key="Foo Device")
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
        controller.on_load_preset(name="preset2")
        self.assertTrue(calls[-1].is_valid())

    def test_on_load_preset_should_provide_default_mapping(self):
        """if there is none"""
        Preset(get_preset_path("Foo Device 2", "bar")).save()
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        data_manager.load_group("Foo Device 2")
        calls: List[MappingData] = []

        def f(data):
            calls.append(data)

        data_bus.subscribe(MessageType.mapping, f)
        controller.on_load_preset(name="bar")
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
        self.assertRaises(TestError, controller.on_delete_preset)

    def test_deletes_preset_when_confirmed(self):
        prepare_presets()
        self.assertTrue(os.path.isfile(get_preset_path("Foo Device 2", "preset2")))
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        user_interface.confirm_delete_ret = Gtk.ResponseType.ACCEPT

        path = get_preset_path("Foo Device 2", "preset2")
        controller.on_delete_preset()
        self.assertFalse(os.path.exists(get_preset_path("Foo Device 2", "preset2")))

    def test_does_not_delete_preset_when_not_confirmed(self):
        prepare_presets()
        self.assertTrue(os.path.isfile(get_preset_path("Foo Device 2", "preset2")))
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        user_interface.confirm_delete_ret = Gtk.ResponseType.CANCEL

        path = get_preset_path("Foo Device 2", "preset2")
        controller.on_delete_preset()
        self.assertTrue(os.path.isfile(get_preset_path("Foo Device 2", "preset2")))

    def test_rename_preset(self):
        prepare_presets()
        self.assertTrue(os.path.isfile(get_preset_path("Foo Device 2", "preset2")))
        self.assertFalse(os.path.exists(get_preset_path("Foo Device 2", "foo")))

        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        controller.on_rename_preset(new_name="foo")

        self.assertFalse(os.path.exists(get_preset_path("Foo Device 2", "preset2")))
        self.assertTrue(os.path.exists(get_preset_path("Foo Device 2", "foo")))

    def test_rename_preset_should_pick_available_name(self):
        prepare_presets()
        self.assertTrue(os.path.exists(get_preset_path("Foo Device 2", "preset2")))
        self.assertTrue(os.path.exists(get_preset_path("Foo Device 2", "preset3")))
        self.assertFalse(os.path.exists(get_preset_path("Foo Device 2", "preset3 2")))

        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        controller.on_rename_preset(new_name="preset3")

        self.assertFalse(os.path.exists(get_preset_path("Foo Device 2", "preset2")))
        self.assertTrue(os.path.exists(get_preset_path("Foo Device 2", "preset3")))
        self.assertTrue(os.path.exists(get_preset_path("Foo Device 2", "preset3 2")))

    def test_on_add_preset_uses_default_name(self):
        self.assertFalse(
            os.path.exists(get_preset_path("Foo Device 2", DEFAULT_PRESET_NAME))
        )

        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        data_manager.load_group("Foo Device 2")

        controller.on_add_preset()
        self.assertTrue(os.path.exists(get_preset_path("Foo Device 2", "new preset")))

    def test_on_add_preset_uses_provided_name(self):
        self.assertFalse(os.path.exists(get_preset_path("Foo Device 2", "foo")))

        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)
        data_manager.load_group("Foo Device 2")

        controller.on_add_preset(name="foo")
        self.assertTrue(os.path.exists(get_preset_path("Foo Device 2", "foo")))

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
            controller.on_update_mapping,
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
        controller.on_create_mapping()

        self.assertEqual(calls[-1], UIMapping())

    def test_delete_mapping_asks_for_confirmation(self):
        prepare_presets()
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        def f(*_):
            raise TestError()

        user_interface.confirm_delete = f

        data_bus.signal(MessageType.init)
        self.assertRaises(TestError, controller.on_delete_mapping)

    def test_deletes_mapping_when_confirmed(self):
        prepare_presets()
        self.assertTrue(os.path.isfile(get_preset_path("Foo Device 2", "preset2")))
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        data_manager.load_mapping(EventCombination("1,3,1"))
        user_interface.confirm_delete_ret = Gtk.ResponseType.ACCEPT

        controller.on_delete_mapping()
        controller.on_save()

        preset = Preset(get_preset_path("Foo Device 2", "preset2"))
        preset.load()
        self.assertIsNone(preset.get_mapping(EventCombination("1,3,1")))

    def test_does_not_delete_mapping_when_not_confirmed(self):
        prepare_presets()
        self.assertTrue(os.path.isfile(get_preset_path("Foo Device 2", "preset2")))
        data_bus, data_manager, user_interface = get_controller_objects()
        controller = Controller(data_bus, data_manager)
        controller.set_gui(user_interface)

        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        data_manager.load_mapping(EventCombination("1,3,1"))
        user_interface.confirm_delete_ret = Gtk.ResponseType.CANCEL

        controller.on_delete_mapping()
        controller.on_save()

        preset = Preset(get_preset_path("Foo Device 2", "preset2"))
        preset.load()
        self.assertIsNotNone(preset.get_mapping(EventCombination("1,3,1")))
