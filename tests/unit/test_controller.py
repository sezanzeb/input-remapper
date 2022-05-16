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

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GLib", "2.0")
gi.require_version("GtkSource", "4")
from gi.repository import Gtk

from inputremapper.configs.mapping import Mapping
from tests.test import (
    quick_cleanup,
    get_key_mapping,
    FakeDaemonProxy,
    get_backend,
    fixtures,
)

from inputremapper.configs.global_config import global_config, GlobalConfig
from inputremapper.gui.controller import Controller
from inputremapper.gui.data_manager import DataManager
from inputremapper.gui.event_handler import EventHandler, EventEnum
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


def get_controller_objects(event_handler=None, data_manager=None, user_interface=None):
    """useful to supply directly to the Controller.__init__"""
    if not event_handler:
        event_handler = EventHandler()

    if not data_manager:
        backed = get_backend(event_handler=event_handler)
        data_manager = DataManager(event_handler, GlobalConfig(), backed)

    if not user_interface:
        user_interface = DummyGui()
    return event_handler, data_manager, user_interface


class TestController(unittest.TestCase):
    def tearDown(self) -> None:
        quick_cleanup()

    def test_should_get_newest_group(self):
        """get_a_group should the newest group"""

        def f():
            return "foo"

        event_handler, data_manager, user_interface = get_controller_objects()
        controller = Controller(event_handler, data_manager, user_interface)
        data_manager.newest_group = f

        self.assertEqual(controller.get_a_group(), "foo")

    def test_should_get_any_group(self):
        """get_a_group should return a valid group"""

        def f():
            raise FileNotFoundError()

        event_handler, data_manager, user_interface = get_controller_objects()
        controller = Controller(event_handler, data_manager, user_interface)
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

        event_handler, data_manager, user_interface = get_controller_objects()
        controller = Controller(event_handler, data_manager, user_interface)
        data_manager.newest_preset = f
        data_manager.load_group("Foo Device")

        self.assertEqual(controller.get_a_preset(), "bar")

    def test_should_get_any_preset(self):
        """get_a_preset should return a new preset if none exist"""

        event_handler, data_manager, user_interface = get_controller_objects()
        controller = Controller(event_handler, data_manager, user_interface)
        data_manager.load_group("Foo Device")

        self.assertEqual(controller.get_a_preset(), "new preset")  # the default name

    def test_on_init_should_provide_uinputs(self):
        event_handler, data_manager, user_interface = get_controller_objects()
        controller = Controller(event_handler, data_manager, user_interface)
        calls = []

        def f(uinputs):
            calls.append(uinputs)

        event_handler.subscribe(EventEnum.uinputs_changed, f)
        event_handler.emit(EventEnum.init)
        self.assertIsNotNone(calls[-1])

    def test_on_init_should_provide_groups(self):
        event_handler, data_manager, user_interface = get_controller_objects()
        controller = Controller(event_handler, data_manager, user_interface)
        calls = []

        def f(groups):
            calls.append(groups)

        event_handler.subscribe(EventEnum.groups_changed, f)
        event_handler.emit(EventEnum.init)
        self.assertIsNotNone(calls[-1])

    def test_on_init_should_provide_a_group(self):
        event_handler, data_manager, user_interface = get_controller_objects()
        controller = Controller(event_handler, data_manager, user_interface)
        calls = []

        def f(group_key, presets):
            calls.append(group_key)
            calls.append(presets)

        event_handler.subscribe(EventEnum.group_changed, f)
        event_handler.emit(EventEnum.init)
        self.assertIsNotNone(calls[-1])
        self.assertIsNotNone(calls[-2])

    def test_on_init_should_provide_a_preset(self):
        event_handler, data_manager, user_interface = get_controller_objects()
        controller = Controller(event_handler, data_manager, user_interface)
        calls = []

        def f(name=None, mappings=None):
            calls.append(name)
            calls.append(mappings)

        event_handler.subscribe(EventEnum.preset_changed, f)
        event_handler.emit(EventEnum.init)

        self.assertIsNotNone(calls[-1])
        self.assertIsNotNone(calls[-2])

    def test_on_init_should_provide_a_mapping(self):
        """only if there is one"""
        prepare_presets()
        event_handler, data_manager, user_interface = get_controller_objects()
        controller = Controller(event_handler, data_manager, user_interface)
        calls = []

        def f(**kwargs):
            calls.append(kwargs)

        event_handler.subscribe(EventEnum.mapping_loaded, f)
        event_handler.emit(EventEnum.init)

        Mapping(**calls[-1]["mapping"])  # this should not raise a ValidationError

    def test_on_init_should_not_provide_a_mapping(self):
        """if there is none"""
        event_handler, data_manager, user_interface = get_controller_objects()
        controller = Controller(event_handler, data_manager, user_interface)
        calls = []

        def f(name=None, mapping=None):
            calls.append((name, mapping))

        event_handler.subscribe(EventEnum.mapping_loaded, f)
        event_handler.emit(EventEnum.init)
        for t in calls:
            self.assertEqual(t, (None, None))

    def test_on_load_group_should_provide_preset(self):
        def f(*_):
            raise TestError()

        event_handler, data_manager, user_interface = get_controller_objects()
        controller = Controller(event_handler, data_manager, user_interface)
        data_manager.load_preset = f

        self.assertRaises(
            TestError, event_handler.emit, EventEnum.load_group, group_key="Foo Device"
        )

    def test_on_load_group_should_provide_mapping(self):
        """if there is one"""
        prepare_presets()
        event_handler, data_manager, user_interface = get_controller_objects()
        controller = Controller(event_handler, data_manager, user_interface)
        calls = []

        def f(**kwargs):
            calls.append(kwargs)

        event_handler.subscribe(EventEnum.mapping_loaded, f)
        event_handler.emit(EventEnum.load_group, group_key="Foo Device 2")

        Mapping(**calls[-1]["mapping"])  # this should not raise a ValidationError

    def test_on_load_group_should_not_provide_mapping(self):
        """if there is none"""
        event_handler, data_manager, user_interface = get_controller_objects()
        controller = Controller(event_handler, data_manager, user_interface)
        calls = []

        def f(name=None, mapping=None):
            calls.append((name, mapping))

        event_handler.subscribe(EventEnum.mapping_loaded, f)
        event_handler.emit(EventEnum.load_group, group_key="Foo Device")
        for t in calls:
            self.assertEqual(t, (None, None))

    def test_on_load_preset_should_provide_mapping(self):
        """if there is one"""
        prepare_presets()
        event_handler, data_manager, user_interface = get_controller_objects()
        controller = Controller(event_handler, data_manager, user_interface)
        data_manager.load_group("Foo Device 2")
        calls = []

        def f(**kwargs):
            calls.append(kwargs)

        event_handler.subscribe(EventEnum.mapping_loaded, f)
        event_handler.emit(EventEnum.load_preset, name="preset2")

        Mapping(**calls[-1]["mapping"])  # this should not raise a ValidationError

    def test_on_load_preset_should_not_provide_mapping(self):
        """if there is none"""
        Preset(get_preset_path("Foo Device 2", "bar")).save()
        event_handler, data_manager, user_interface = get_controller_objects()
        controller = Controller(event_handler, data_manager, user_interface)
        data_manager.load_group("Foo Device 2")
        calls = []

        def f(name=None, mapping=None):
            calls.append((name, mapping))

        event_handler.subscribe(EventEnum.mapping_loaded, f)
        event_handler.emit(EventEnum.load_preset, name="bar")
        for t in calls:
            self.assertEqual(t, (None, None))

    def test_on_delete_preset_asks_for_confirmation(self):
        prepare_presets()
        event_handler, data_manager, user_interface = get_controller_objects()
        controller = Controller(event_handler, data_manager, user_interface)

        def f(*_):
            raise TestError()

        user_interface.confirm_delete = f

        event_handler.emit(EventEnum.init)
        self.assertRaises(TestError, event_handler.emit, EventEnum.delete_preset)

    def test_deletes_when_confirmed(self):
        prepare_presets()
        self.assertTrue(os.path.isfile(get_preset_path("Foo Device 2", "preset2")))
        event_handler, data_manager, user_interface = get_controller_objects()
        controller = Controller(event_handler, data_manager, user_interface)

        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        user_interface.confirm_delete_ret = Gtk.ResponseType.ACCEPT

        path = get_preset_path("Foo Device 2", "preset2")
        event_handler.emit(EventEnum.delete_preset)
        self.assertFalse(os.path.exists(get_preset_path("Foo Device 2", "preset2")))

    def test_deletes_not_when_not_confirmed(self):
        prepare_presets()
        self.assertTrue(os.path.isfile(get_preset_path("Foo Device 2", "preset2")))
        event_handler, data_manager, user_interface = get_controller_objects()
        controller = Controller(event_handler, data_manager, user_interface)

        data_manager.load_group("Foo Device 2")
        data_manager.load_preset("preset2")
        user_interface.confirm_delete_ret = Gtk.ResponseType.CANCEL

        path = get_preset_path("Foo Device 2", "preset2")
        event_handler.emit(EventEnum.delete_preset)
        self.assertTrue(os.path.isfile(get_preset_path("Foo Device 2", "preset2")))
