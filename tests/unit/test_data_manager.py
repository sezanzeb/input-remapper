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
import unittest
from typing import List, Dict, Any

from inputremapper.configs.global_config import global_config
from inputremapper.configs.mapping import UIMapping
from inputremapper.event_combination import EventCombination
from inputremapper.exceptions import DataManagementError
from tests.test import get_key_mapping, quick_cleanup

from inputremapper.configs.paths import get_preset_path, get_config_path
from inputremapper.configs.preset import Preset
from inputremapper.gui.data_manager import DataManager
from inputremapper.gui.event_handler import EventHandler, EventEnum


class Listener:
    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)


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


class TestDataManager(unittest.TestCase):
    def setUp(self) -> None:
        self.event_handler = EventHandler()
        self.data_manager = DataManager(self.event_handler)

    def tearDown(self) -> None:
        quick_cleanup()

    def test_load_group_provides_presets(self):
        """we should get all preset of a group, when loading it"""
        prepare_presets()
        listener = Listener()
        self.event_handler.subscribe(EventEnum.group_loaded, listener)

        self.event_handler.emit(EventEnum.load_group, group_key="Foo Device 2")
        response = listener.calls[0]

        for preset_name in response["presets"]:
            self.assertIn(
                preset_name,
                (
                    "preset2",
                    "preset3",
                ),
            )

    def test_load_group_without_presets_provides_none(self):
        """we should get no presets when loading a group without presets"""
        listener = Listener()
        self.event_handler.subscribe(EventEnum.group_loaded, listener)

        self.event_handler.emit(EventEnum.load_group, group_key="Foo Device 2")
        response = listener.calls[0]
        self.assertEqual(len(response["presets"]), 0)

    def test_load_non_existing_group_succeeds(self):
        """we should be able to load whatever group we want"""
        listener = Listener()
        self.event_handler.subscribe(EventEnum.group_loaded, listener)

        self.event_handler.emit(EventEnum.load_group, group_key="Some Unknown Device")
        response = listener.calls[0]
        self.assertEqual(len(response["presets"]), 0)

    def test_cannot_load_preset_without_group(self):
        """loading a preset without a loaded group should
        raise a DataManagementError"""
        prepare_presets()
        self.assertRaises(
            DataManagementError,
            self.event_handler.emit,
            EventEnum.load_preset,
            name="preset1",
        )

    def test_load_preset(self):
        """loading an existing preset should be possible"""
        prepare_presets()
        listener = Listener()
        self.event_handler.subscribe(EventEnum.preset_loaded, listener)

        self.event_handler.emit(EventEnum.load_group, group_key="Foo Device")
        self.event_handler.emit(EventEnum.load_preset, name="preset1")
        mappings = listener.calls[0]["mappings"]
        preset_name = listener.calls[0]["name"]

        expected_preset = Preset(get_preset_path("Foo Device", "preset1"))
        expected_preset.load()
        expected_mappings = [
            (mapping.name, mapping.event_combination) for mapping in expected_preset
        ]

        self.assertEqual(preset_name, "preset1")
        for mapping in expected_mappings:
            self.assertIn(mapping, mappings)

    def test_cannot_load_non_existing_preset(self):
        """loading a non-existing preset should raise an KeyError"""
        prepare_presets()

        self.event_handler.emit(EventEnum.load_group, group_key="Foo Device")
        self.assertRaises(
            FileNotFoundError,
            self.event_handler.emit,
            EventEnum.load_preset,
            name="unknownPreset",
        )

    def test_save_preset(self):
        """modified preses should be saved to the disc"""
        prepare_presets()
        listener = Listener()
        self.event_handler.subscribe(EventEnum.mapping_loaded, listener)
        # make sure the correct preset is loaded
        self.event_handler.emit(EventEnum.load_group, group_key="Foo Device")
        self.event_handler.emit(EventEnum.load_preset, name="preset1")
        self.event_handler.emit(
            EventEnum.load_mapping, combination=EventCombination("1,1,1")
        )

        mapping = listener.calls[0]["mapping"]
        control_preset = Preset(get_preset_path("Foo Device", "preset1"))
        control_preset.load()
        self.assertEqual(
            control_preset.get_mapping(EventCombination("1,1,1")).output_symbol,
            mapping["output_symbol"],
        )

        # change the mapping provided with the mapping_loaded event and save
        self.event_handler.emit(EventEnum.update_mapping, output_symbol="key(a)")
        self.event_handler.emit(EventEnum.save)

        # reload the control_preset
        control_preset.empty()
        control_preset.load()
        self.assertEqual(
            control_preset.get_mapping(EventCombination("1,1,1")).output_symbol,
            "key(a)",
        )

    def test_rename_preset(self):
        """should be able to rename a preset"""
        prepare_presets()
        self.event_handler.emit(EventEnum.load_group, group_key="Foo Device 2")
        self.event_handler.emit(EventEnum.load_preset, name="preset2")
        listener = Listener()
        self.event_handler.subscribe(EventEnum.preset_loaded, listener)
        self.event_handler.subscribe(EventEnum.group_loaded, listener)

        self.event_handler.emit(EventEnum.rename_preset, new_name="new preset")

        self.event_handler.emit(EventEnum.load_preset, name="new preset")
        self.event_handler.emit(EventEnum.load_group, group_key="Foo Device 2")

        presets_in_group = [preset for preset in listener.calls[1]["presets"]]
        self.assertNotIn("preset2", presets_in_group)
        self.assertIn("new preset", presets_in_group)

        # this should pass witout error:
        self.event_handler.emit(EventEnum.load_preset, name="new preset")
        self.event_handler.emit(EventEnum.rename_preset, new_name="new preset")

    def test_cannot_rename_preset(self):
        """rename preset should raise a DataManagementError if a preset
        with the new name already exists in the current group"""
        prepare_presets()
        self.event_handler.emit(EventEnum.load_group, group_key="Foo Device 2")
        self.event_handler.emit(EventEnum.load_preset, name="preset2")

        self.assertRaises(
            DataManagementError,
            self.event_handler.emit,
            EventEnum.rename_preset,
            new_name="preset3",
        )

    def test_cannot_rename_preset_when_preset_not_loaded(self):
        prepare_presets()

        self.assertRaises(
            DataManagementError,
            self.event_handler.emit,
            EventEnum.rename_preset,
            new_name="foo",
        )
        self.event_handler.emit(EventEnum.load_group, group_key="Foo Device 2")
        self.assertRaises(
            DataManagementError,
            self.event_handler.emit,
            EventEnum.rename_preset,
            new_name="foo",
        )

    def test_add_preset(self):
        """should be able to add a preset"""
        prepare_presets()
        self.event_handler.emit(EventEnum.load_group, group_key="Foo Device 2")
        listener = Listener()
        self.event_handler.subscribe(EventEnum.group_loaded, listener)

        self.event_handler.emit(EventEnum.add_preset, name="new preset")
        self.event_handler.emit(EventEnum.load_group, group_key="Foo Device 2")

        presets_in_group = [preset for preset in listener.calls[0]["presets"]]
        self.assertIn("preset2", presets_in_group)
        self.assertIn("preset3", presets_in_group)
        self.assertIn("new preset", presets_in_group)

    def test_cannot_add_preset(self):
        """adding a preset with the same name as an already existing
        preset (of the current group) should raise a DataManagementError"""
        prepare_presets()
        self.event_handler.emit(EventEnum.load_group, group_key="Foo Device 2")
        self.event_handler.emit(EventEnum.load_preset, name="preset2")

        self.assertRaises(
            DataManagementError,
            self.event_handler.emit,
            EventEnum.add_preset,
            name="preset3",
        )

    def test_cannot_add_preset_without_group(self):
        self.assertRaises(
            DataManagementError,
            self.event_handler.emit,
            EventEnum.add_preset,
            name="foo",
        )

    def test_delete_preset(self):
        """should be able to delete the current preset"""
        prepare_presets()
        self.event_handler.emit(EventEnum.load_group, group_key="Foo Device 2")
        self.event_handler.emit(EventEnum.load_preset, name="preset2")
        listener = Listener()
        self.event_handler.subscribe(EventEnum.group_loaded, listener)

        self.event_handler.emit(EventEnum.delete_preset)
        self.event_handler.emit(EventEnum.load_group, group_key="Foo Device 2")

        presets_in_group = [preset for preset in listener.calls[0]["presets"]]
        self.assertEqual(len(presets_in_group), 1)
        self.assertNotIn("preset2", presets_in_group)

    def test_load_mapping(self):
        """should be able to load a mapping"""
        preset, _, _ = prepare_presets()
        expected_mapping = preset.get_mapping(EventCombination("1,1,1"))
        listener = Listener()
        self.event_handler.subscribe(EventEnum.mapping_loaded, listener)

        self.event_handler.emit(EventEnum.load_group, group_key="Foo Device")
        self.event_handler.emit(EventEnum.load_preset, name="preset1")
        self.event_handler.emit(
            EventEnum.load_mapping, combination=EventCombination("1,1,1")
        )
        mapping = listener.calls[0]["mapping"]

        self.assertEqual(mapping, expected_mapping)

    def test_cannot_load_non_existing_mapping(self):
        """loading a mapping tha is not present in the preset should raise a KeyError"""
        prepare_presets()

        self.event_handler.emit(EventEnum.load_group, group_key="Foo Device 2")
        self.event_handler.emit(EventEnum.load_preset, name="preset2")
        self.assertRaises(
            KeyError,
            self.event_handler.emit,
            EventEnum.load_mapping,
            combination=EventCombination("1,1,1"),
        )

    def test_cannot_load_mapping_without_preset(self):
        """loading a mapping if no preset is loaded
        should raise an DataManagementError"""
        prepare_presets()

        self.assertRaises(
            DataManagementError,
            self.event_handler.emit,
            EventEnum.load_mapping,
            combination=EventCombination("1,1,1"),
        )
        self.event_handler.emit(EventEnum.load_group, group_key="Foo Device")
        self.assertRaises(
            DataManagementError,
            self.event_handler.emit,
            EventEnum.load_mapping,
            combination=EventCombination("1,1,1"),
        )

    def test_update_mapping(self):
        prepare_presets()
        self.event_handler.emit(EventEnum.load_group, group_key="Foo Device 2")
        self.event_handler.emit(EventEnum.load_preset, name="preset2")
        self.event_handler.emit(
            EventEnum.load_mapping, combination=EventCombination("1,4,1")
        )
        self.event_handler.emit(
            EventEnum.update_mapping,
            name="foo",
            output_symbol="f",
            release_timeout=0.3,
        )

        listener = Listener()
        self.event_handler.subscribe(EventEnum.mapping_loaded, listener)
        self.event_handler.emit(
            EventEnum.load_mapping, combination=EventCombination("1,4,1")
        )
        response = listener.calls[0]["mapping"]
        self.assertEqual(response["name"], "foo")
        self.assertEqual(response["output_symbol"], "f")
        self.assertEqual(response["release_timeout"], 0.3)

    def test_cannot_update_mapping(self):
        """updating a mapping should not be possible if the mapping was not loaded"""
        prepare_presets()
        self.assertRaises(
            DataManagementError,
            self.event_handler.emit,
            EventEnum.update_mapping,
            name="foo",
        )
        self.event_handler.emit(EventEnum.load_group, group_key="Foo Device 2")
        self.assertRaises(
            DataManagementError,
            self.event_handler.emit,
            EventEnum.update_mapping,
            name="foo",
        )
        self.event_handler.emit(EventEnum.load_preset, name="preset2")
        self.assertRaises(
            DataManagementError,
            self.event_handler.emit,
            EventEnum.update_mapping,
            name="foo",
        )

    def test_create_mapping(self):
        """should be able to add a mapping to the current preset"""
        prepare_presets()
        listener = Listener()
        self.event_handler.subscribe(EventEnum.mapping_loaded, listener)

        self.event_handler.emit(EventEnum.load_group, group_key="Foo Device 2")
        self.event_handler.emit(EventEnum.load_preset, name="preset2")
        self.event_handler.emit(EventEnum.create_mapping)

        self.event_handler.emit(EventEnum.load_mapping)

        self.assertEqual(listener.calls[0]["mapping"], UIMapping().dict())

    def test_cannot_create_mapping_without_preset(self):
        """adding a mapping if not preset is loaded
        should raise an DataManagementError"""
        prepare_presets()

        self.assertRaises(
            DataManagementError, self.event_handler.emit, EventEnum.create_mapping
        )
        self.event_handler.emit(EventEnum.load_group, group_key="Foo Device 2")
        self.assertRaises(
            DataManagementError, self.event_handler.emit, EventEnum.create_mapping
        )

    def test_delete_mapping(self):
        """should be able to delete a mapping"""
        prepare_presets()
        listener = Listener()

        old_preset = Preset(get_preset_path("Foo Device 2", "preset2"))
        old_preset.load()

        self.event_handler.emit(EventEnum.load_group, group_key="Foo Device 2")
        self.event_handler.emit(EventEnum.load_preset, name="preset2")
        self.event_handler.emit(
            EventEnum.load_mapping, combination=EventCombination("1,3,1")
        )

        self.event_handler.emit(EventEnum.delete_mapping)
        self.event_handler.emit(EventEnum.save)
        self.event_handler.subscribe(EventEnum.preset_loaded, listener)
        self.event_handler.emit(EventEnum.load_preset, name="preset2")

        deleted_mapping = old_preset.get_mapping(EventCombination("1,3,1"))
        mappings = listener.calls[0]["mappings"]
        preset_name = listener.calls[0]["name"]

        expected_preset = Preset(get_preset_path("Foo Device 2", "preset2"))
        expected_preset.load()
        expected_mappings = [
            (mapping.name, mapping.event_combination) for mapping in expected_preset
        ]

        self.assertEqual(preset_name, "preset2")
        for mapping in expected_mappings:
            self.assertIn(mapping, mappings)

        self.assertNotIn(
            (deleted_mapping.name, deleted_mapping.event_combination), mappings
        )

    def test_cannot_delete_mapping(self):
        """deleting a mapping should not be possible if the mapping was not loaded"""
        prepare_presets()
        self.assertRaises(
            DataManagementError,
            self.event_handler.emit,
            EventEnum.delete_mapping
        )
        self.event_handler.emit(EventEnum.load_group, group_key="Foo Device 2")
        self.assertRaises(
            DataManagementError,
            self.event_handler.emit,
            EventEnum.delete_mapping
        )
        self.event_handler.emit(EventEnum.load_preset, name="preset2")
        self.assertRaises(
            DataManagementError,
            self.event_handler.emit,
            EventEnum.delete_mapping
        )

    def test_get_autoload(self):
        """get the correct autoload status for all presets"""
        prepare_presets()
        listener = Listener()
        self.event_handler.subscribe(EventEnum.autoload_status, listener)
        (
            self.event_handler.emit(EventEnum.load_group, group_key="Foo Device")
            .emit(EventEnum.load_preset, name="preset1")
            .emit(EventEnum.get_autoload)
            .emit(EventEnum.load_group, group_key="Foo Device 2")
            .emit(EventEnum.load_preset, name="preset2")
            .emit(EventEnum.get_autoload)
            .emit(EventEnum.load_preset, name="preset3")
            .emit(EventEnum.get_autoload)
        )
        self.assertFalse(listener.calls[0]["autoload"])
        self.assertTrue(listener.calls[1]["autoload"])
        self.assertFalse(listener.calls[2]["autoload"])

    def test_cannot_get_autoload_without_preset(self):
        """getting the autoload status should not be possible without a preset"""
        prepare_presets()

        self.assertRaises(
            DataManagementError, self.event_handler.emit, EventEnum.get_autoload
        )
        self.event_handler.emit(EventEnum.load_group, group_key="Foo Device 2")
        self.assertRaises(
            DataManagementError, self.event_handler.emit, EventEnum.get_autoload
        )

    def test_set_autoload(self):
        """should be able to set the autoload status"""
        prepare_presets()
        listener = Listener()
        self.event_handler.subscribe(EventEnum.autoload_status, listener)
        (
            self.event_handler.emit(EventEnum.load_group, group_key="Foo Device")
            .emit(EventEnum.load_preset, name="preset1")
            .emit(EventEnum.set_autoload, autoload=True)
            .emit(EventEnum.get_autoload)
            .emit(EventEnum.set_autoload, autoload=False)
            .emit(EventEnum.get_autoload)
        )

        self.assertTrue(listener.calls[0]["autoload"])
        self.assertFalse(listener.calls[1]["autoload"])

    def test_cannot_set_autoload_without_preset(self):
        prepare_presets()
        self.assertRaises(
            DataManagementError,
            self.event_handler.emit,
            EventEnum.set_autoload,
            autoload=True
        )
        self.event_handler.emit(EventEnum.load_group, group_key="Foo Device 2")
        self.assertRaises(
            DataManagementError,
            self.event_handler.emit,
            EventEnum.set_autoload,
            autoload=True
        )
