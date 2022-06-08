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
import os
import time
import unittest
from typing import List, Dict, Any

from inputremapper.configs.global_config import global_config
from inputremapper.configs.mapping import UIMapping, MappingData
from inputremapper.event_combination import EventCombination
from inputremapper.exceptions import DataManagementError
from inputremapper.gui.data_bus import DataBus, MessageType, GroupData, PresetData
from tests.test import get_key_mapping, quick_cleanup, get_backend

from inputremapper.configs.paths import get_preset_path, get_config_path
from inputremapper.configs.preset import Preset
from inputremapper.gui.data_manager import DataManager, DEFAULT_PRESET_NAME


class Listener:
    def __init__(self):
        self.calls: List = []

    def __call__(self, data):
        self.calls.append(data)


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
        self.data_bus = DataBus()
        self.backend = get_backend()
        self.data_manager = DataManager(self.data_bus, global_config, self.backend)

    def tearDown(self) -> None:
        quick_cleanup()

    def test_load_group_provides_presets(self):
        """we should get all preset of a group, when loading it"""
        prepare_presets()
        response: List[GroupData] = []

        def listener(data: GroupData):
            response.append(data)

        self.data_bus.subscribe(MessageType.group, listener)
        self.data_manager.load_group("Foo Device 2")

        for preset_name in response[0].presets:
            self.assertIn(
                preset_name,
                (
                    "preset2",
                    "preset3",
                ),
            )

        self.assertEqual(response[0].group_key, "Foo Device 2")

    def test_load_group_without_presets_provides_none(self):
        """we should get no presets when loading a group without presets"""
        response: List[GroupData] = []

        def listener(data: GroupData):
            response.append(data)

        self.data_bus.subscribe(MessageType.group, listener)

        self.data_manager.load_group(group_key="Foo Device 2")
        self.assertEqual(len(response[0].presets), 0)

    def test_load_non_existing_group(self):
        """we should not be able to load an unknown group"""
        with self.assertRaises(DataManagementError):
            self.data_manager.load_group(group_key="Some Unknown Device")

    def test_cannot_load_preset_without_group(self):
        """loading a preset without a loaded group should
        raise a DataManagementError"""
        prepare_presets()
        self.assertRaises(
            DataManagementError,
            self.data_manager.load_preset,
            name="preset1",
        )

    def test_load_preset(self):
        """loading an existing preset should be possible"""
        prepare_presets()

        self.data_manager.load_group(group_key="Foo Device")
        listener = Listener()
        self.data_bus.subscribe(MessageType.preset, listener)
        self.data_manager.load_preset(name="preset1")
        mappings = listener.calls[0].mappings
        preset_name = listener.calls[0].name

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

        self.data_manager.load_group(group_key="Foo Device")
        self.assertRaises(
            FileNotFoundError,
            self.data_manager.load_preset,
            name="unknownPreset",
        )

    def test_save_preset(self):
        """modified preses should be saved to the disc"""
        prepare_presets()
        # make sure the correct preset is loaded
        self.data_manager.load_group(group_key="Foo Device")
        self.data_manager.load_preset(name="preset1")
        listener = Listener()
        self.data_bus.subscribe(MessageType.mapping, listener)
        self.data_manager.load_mapping(combination=EventCombination("1,1,1"))

        mapping: MappingData = listener.calls[0]
        control_preset = Preset(get_preset_path("Foo Device", "preset1"))
        control_preset.load()
        self.assertEqual(
            control_preset.get_mapping(EventCombination("1,1,1")).output_symbol,
            mapping.output_symbol,
        )

        # change the mapping provided with the mapping_changed event and save
        self.data_manager.update_mapping(output_symbol="key(a)")
        self.data_manager.save()

        # reload the control_preset
        control_preset.empty()
        control_preset.load()
        self.assertEqual(
            control_preset.get_mapping(EventCombination("1,1,1")).output_symbol,
            "key(a)",
        )

    def test_copy_preset(self):
        prepare_presets()
        self.data_manager.load_group(group_key="Foo Device 2")
        self.data_manager.load_preset(name="preset2")
        listener = Listener()
        self.data_bus.subscribe(MessageType.group, listener)
        self.data_bus.subscribe(MessageType.preset, listener)

        self.data_manager.copy_preset("foo")

        # we expect the first data to be group data and the second
        # one a preset data of the new copy
        presets_in_group = [preset for preset in listener.calls[0].presets]
        self.assertIn("preset2", presets_in_group)
        self.assertIn("foo", presets_in_group)
        self.assertEqual(listener.calls[1].name, "foo")

        # this should pass without error:
        self.data_manager.load_preset("preset2")
        self.data_manager.copy_preset("preset2")

    def test_cannot_copy_preset(self):
        prepare_presets()

        self.assertRaises(
            DataManagementError,
            self.data_manager.copy_preset,
            "foo",
        )
        self.data_manager.load_group("Foo Device 2")
        self.assertRaises(
            DataManagementError,
            self.data_manager.copy_preset,
            "foo",
        )

    def test_copy_preset_to_existing_name_raises_error(self):
        prepare_presets()
        self.data_manager.load_group(group_key="Foo Device 2")
        self.data_manager.load_preset(name="preset2")

        self.assertRaises(
            ValueError,
            self.data_manager.copy_preset,
            "preset3",
        )

    def test_rename_preset(self):
        """should be able to rename a preset"""
        prepare_presets()
        self.data_manager.load_group(group_key="Foo Device 2")
        self.data_manager.load_preset(name="preset2")
        listener = Listener()
        self.data_bus.subscribe(MessageType.group, listener)
        self.data_bus.subscribe(MessageType.preset, listener)

        self.data_manager.rename_preset(new_name="new preset")

        # we expect the first data to be group data and the second
        # one a preset data
        presets_in_group = [preset for preset in listener.calls[0].presets]
        self.assertNotIn("preset2", presets_in_group)
        self.assertIn("new preset", presets_in_group)
        self.assertEqual(listener.calls[1].name, "new preset")

        # this should pass without error:
        self.data_manager.load_preset(name="new preset")
        self.data_manager.rename_preset(new_name="new preset")

    def test_rename_preset_sets_autoload_correct(self):
        """when renaming a preset the autoload status should still be set correctly"""
        prepare_presets()
        self.data_manager.load_group(group_key="Foo Device 2")
        listener = Listener()
        self.data_bus.subscribe(MessageType.preset, listener)
        self.data_manager.load_preset(name="preset2")  # sends PresetData
        # sends PresetData with updated name, e. e. should be equal
        self.data_manager.rename_preset(new_name="foo")
        self.assertEqual(listener.calls[0].autoload, listener.calls[1].autoload)

    def test_cannot_rename_preset(self):
        """rename preset should raise a DataManagementError if a preset
        with the new name already exists in the current group"""
        prepare_presets()
        self.data_manager.load_group(group_key="Foo Device 2")
        self.data_manager.load_preset(name="preset2")

        self.assertRaises(
            ValueError,
            self.data_manager.rename_preset,
            new_name="preset3",
        )

    def test_cannot_rename_preset_without_preset(self):
        prepare_presets()

        self.assertRaises(
            DataManagementError,
            self.data_manager.rename_preset,
            new_name="foo",
        )
        self.data_manager.load_group(group_key="Foo Device 2")
        self.assertRaises(
            DataManagementError,
            self.data_manager.rename_preset,
            new_name="foo",
        )

    def test_add_preset(self):
        """should be able to add a preset"""
        prepare_presets()
        self.data_manager.load_group(group_key="Foo Device 2")
        listener = Listener()
        self.data_bus.subscribe(MessageType.group, listener)

        # should emit group_changed
        self.data_manager.add_preset(name="new preset")

        presets_in_group = [preset for preset in listener.calls[0].presets]
        self.assertIn("preset2", presets_in_group)
        self.assertIn("preset3", presets_in_group)
        self.assertIn("new preset", presets_in_group)

    def test_cannot_add_preset(self):
        """adding a preset with the same name as an already existing
        preset (of the current group) should raise a DataManagementError"""
        prepare_presets()
        self.data_manager.load_group(group_key="Foo Device 2")
        self.data_manager.load_preset(name="preset2")

        self.assertRaises(
            DataManagementError,
            self.data_manager.add_preset,
            name="preset3",
        )

    def test_cannot_add_preset_without_group(self):
        self.assertRaises(
            DataManagementError,
            self.data_manager.add_preset,
            name="foo",
        )

    def test_delete_preset(self):
        """should be able to delete the current preset"""
        prepare_presets()
        self.data_manager.load_group(group_key="Foo Device 2")
        self.data_manager.load_preset(name="preset2")
        listener = Listener()
        self.data_bus.subscribe(MessageType.group, listener)
        self.data_bus.subscribe(MessageType.preset, listener)
        self.data_bus.subscribe(MessageType.mapping, listener)

        # should emit mapping_changed, preset_changed, group_changed (in that order)
        self.data_manager.delete_preset()

        presets_in_group = [preset for preset in listener.calls[2].presets]
        self.assertEqual(len(presets_in_group), 1)
        self.assertNotIn("preset2", presets_in_group)
        self.assertEqual(listener.calls[1], PresetData(None, None))
        self.assertEqual(listener.calls[0], MappingData())  # the default data

    def test_load_mapping(self):
        """should be able to load a mapping"""
        preset, _, _ = prepare_presets()
        expected_mapping = preset.get_mapping(EventCombination("1,1,1"))

        self.data_manager.load_group(group_key="Foo Device")
        self.data_manager.load_preset(name="preset1")
        listener = Listener()
        self.data_bus.subscribe(MessageType.mapping, listener)
        self.data_manager.load_mapping(combination=EventCombination("1,1,1"))
        mapping = listener.calls[0]

        self.assertEqual(mapping, expected_mapping)

    def test_cannot_load_non_existing_mapping(self):
        """loading a mapping tha is not present in the preset should raise a KeyError"""
        prepare_presets()

        self.data_manager.load_group(group_key="Foo Device 2")
        self.data_manager.load_preset(name="preset2")
        self.assertRaises(
            KeyError,
            self.data_manager.load_mapping,
            combination=EventCombination("1,1,1"),
        )

    def test_cannot_load_mapping_without_preset(self):
        """loading a mapping if no preset is loaded
        should raise an DataManagementError"""
        prepare_presets()

        self.assertRaises(
            DataManagementError,
            self.data_manager.load_mapping,
            combination=EventCombination("1,1,1"),
        )
        self.data_manager.load_group(group_key="Foo Device")
        self.assertRaises(
            DataManagementError,
            self.data_manager.load_mapping,
            combination=EventCombination("1,1,1"),
        )

    def test_update_mapping_emits_mapping_changed(self):
        """update mapping should emit a mapping_changed event"""
        prepare_presets()
        self.data_manager.load_group(group_key="Foo Device 2")
        self.data_manager.load_preset(name="preset2")
        self.data_manager.load_mapping(combination=EventCombination("1,4,1"))

        listener = Listener()
        self.data_bus.subscribe(MessageType.mapping, listener)
        self.data_manager.update_mapping(
            name="foo",
            output_symbol="f",
            release_timeout=0.3,
        )

        response = listener.calls[0]
        self.assertEqual(response.name, "foo")
        self.assertEqual(response.output_symbol, "f")
        self.assertEqual(response.release_timeout, 0.3)

    def test_updated_mapping_can_be_saved(self):
        """make sure that updated changes can be saved"""
        prepare_presets()
        self.data_manager.load_group(group_key="Foo Device 2")
        self.data_manager.load_preset(name="preset2")
        self.data_manager.load_mapping(combination=EventCombination("1,4,1"))

        self.data_manager.update_mapping(
            name="foo",
            output_symbol="f",
            release_timeout=0.3,
        )
        self.data_manager.save()

        preset = Preset(get_preset_path("Foo Device 2", "preset2"), UIMapping)
        preset.load()
        mapping = preset.get_mapping(EventCombination("1,4,1"))
        self.assertEqual(mapping.name, "foo")
        self.assertEqual(mapping.output_symbol, "f")
        self.assertEqual(mapping.release_timeout, 0.3)

    def test_updated_mapping_saves_invalid_mapping(self):
        """make sure that updated changes can be saved even if they are not valid"""
        prepare_presets()
        self.data_manager.load_group(group_key="Foo Device 2")
        self.data_manager.load_preset(name="preset2")
        self.data_manager.load_mapping(combination=EventCombination("1,4,1"))

        self.data_manager.update_mapping(
            output_symbol="bar",  # not a macro and not a valid symbol
        )
        self.data_manager.save()

        preset = Preset(get_preset_path("Foo Device 2", "preset2"), UIMapping)
        preset.load()
        mapping = preset.get_mapping(EventCombination("1,4,1"))
        self.assertIsNotNone(mapping.get_error())
        self.assertEqual(mapping.output_symbol, "bar")

    def test_update_mapping_combination_sends_massage(self):
        prepare_presets()

        self.data_manager.load_group(group_key="Foo Device 2")
        self.data_manager.load_preset(name="preset2")
        self.data_manager.load_mapping(combination=EventCombination("1,4,1"))
        listener = Listener()
        self.data_bus.subscribe(MessageType.mapping, listener)
        self.data_bus.subscribe(MessageType.combination_update, listener)

        # we expect a message for combination update first, and then for mapping
        self.data_manager.update_mapping(
            event_combination=EventCombination.from_string("1,5,1+1,6,1")
        )
        self.assertEqual(listener.calls[0].message_type, MessageType.combination_update)
        self.assertEqual(
            listener.calls[0].old_combination,
            EventCombination.from_string("1,4,1"),
        )
        self.assertEqual(
            listener.calls[0].new_combination,
            EventCombination.from_string("1,5,1+1,6,1"),
        )
        self.assertEqual(listener.calls[1].message_type, MessageType.mapping)
        self.assertEqual(
            listener.calls[1].event_combination,
            EventCombination.from_string("1,5,1+1,6,1"),
        )

    def test_cannot_update_mapping_combination(self):
        """updating a mapping with an already existing combination
        should raise a KeyError"""
        prepare_presets()
        self.data_manager.load_group(group_key="Foo Device 2")
        self.data_manager.load_preset(name="preset2")
        self.data_manager.load_mapping(combination=EventCombination("1,4,1"))

        self.assertRaises(
            KeyError,
            self.data_manager.update_mapping,
            event_combination=EventCombination("1,3,1"),
        )

    def test_cannot_update_mapping(self):
        """updating a mapping should not be possible if the mapping was not loaded"""
        prepare_presets()
        self.assertRaises(
            DataManagementError,
            self.data_manager.update_mapping,
            name="foo",
        )
        self.data_manager.load_group(group_key="Foo Device 2")
        self.assertRaises(
            DataManagementError,
            self.data_manager.update_mapping,
            name="foo",
        )
        self.data_manager.load_preset("preset2")
        self.assertRaises(
            DataManagementError,
            self.data_manager.update_mapping,
            name="foo",
        )

    def test_create_mapping(self):
        """should be able to add a mapping to the current preset"""
        prepare_presets()

        self.data_manager.load_group(group_key="Foo Device 2")
        self.data_manager.load_preset(name="preset2")
        listener = Listener()
        self.data_bus.subscribe(MessageType.mapping, listener)
        self.data_bus.subscribe(MessageType.preset, listener)
        self.data_manager.create_mapping()  # emits preset_changed

        self.data_manager.load_mapping(combination=EventCombination.empty_combination())

        self.assertEqual(listener.calls[0].name, "preset2")
        self.assertEqual(len(listener.calls[0].mappings), 3)
        self.assertEqual(listener.calls[1], UIMapping())

    def test_cannot_create_mapping_without_preset(self):
        """adding a mapping if not preset is loaded
        should raise an DataManagementError"""
        prepare_presets()

        self.assertRaises(DataManagementError, self.data_manager.create_mapping)
        self.data_manager.load_group(group_key="Foo Device 2")
        self.assertRaises(DataManagementError, self.data_manager.create_mapping)

    def test_delete_mapping(self):
        """should be able to delete a mapping"""
        prepare_presets()

        old_preset = Preset(get_preset_path("Foo Device 2", "preset2"))
        old_preset.load()

        self.data_manager.load_group(group_key="Foo Device 2")
        self.data_manager.load_preset(name="preset2")
        self.data_manager.load_mapping(combination=EventCombination("1,3,1"))

        listener = Listener()
        self.data_bus.subscribe(MessageType.preset, listener)
        self.data_bus.subscribe(MessageType.mapping, listener)
        # emits mapping and preset changed
        self.data_manager.delete_mapping()
        self.data_manager.save()

        deleted_mapping = old_preset.get_mapping(EventCombination("1,3,1"))
        mappings = listener.calls[1].mappings
        preset_name = listener.calls[1].name
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
        # first event (mapping_changed) should be without data
        self.assertEqual(listener.calls[0], MappingData())

    def test_cannot_delete_mapping(self):
        """deleting a mapping should not be possible if the mapping was not loaded"""
        prepare_presets()
        self.assertRaises(DataManagementError, self.data_manager.delete_mapping)
        self.data_manager.load_group(group_key="Foo Device 2")
        self.assertRaises(DataManagementError, self.data_manager.delete_mapping)
        self.data_manager.load_preset(name="preset2")
        self.assertRaises(DataManagementError, self.data_manager.delete_mapping)

    def test_set_autoload(self):
        """should be able to set the autoload status"""
        prepare_presets()
        self.data_manager.load_group(group_key="Foo Device")

        listener = Listener()
        self.data_bus.subscribe(MessageType.preset, listener)
        self.data_manager.load_preset(name="preset1")  # sends updated preset data
        self.data_manager.set_autoload(autoload=True)  # sends updated preset data
        self.data_manager.set_autoload(autoload=False)  # sends updated preset data

        self.assertFalse(listener.calls[0].autoload)
        self.assertTrue(listener.calls[1].autoload)
        self.assertFalse(listener.calls[2].autoload)

    def test_cannot_set_autoload_without_preset(self):
        prepare_presets()
        self.assertRaises(
            DataManagementError,
            self.data_manager.set_autoload,
            autoload=True,
        )
        self.data_manager.load_group(group_key="Foo Device 2")
        self.assertRaises(
            DataManagementError,
            self.data_manager.set_autoload,
            autoload=True,
        )

    def test_finds_newest_group(self):
        Preset(get_preset_path("Foo Device", "preset 1")).save()
        time.sleep(0.01)
        Preset(get_preset_path("Bar Device", "preset 2")).save()
        self.assertEqual(self.data_manager.newest_group(), "Bar Device")

    def test_finds_newest_preset(self):
        Preset(get_preset_path("Foo Device", "preset 1")).save()
        time.sleep(0.01)
        Preset(get_preset_path("Foo Device", "preset 2")).save()
        self.data_manager.load_group("Foo Device")
        self.assertEqual(self.data_manager.newest_preset(), "preset 2")

    def test_newest_group_ignores_unknown_filetypes(self):
        Preset(get_preset_path("Foo Device", "preset 1")).save()
        time.sleep(0.01)
        Preset(get_preset_path("Bar Device", "preset 2")).save()

        # not a preset, ignore
        time.sleep(0.01)
        path = os.path.join(get_preset_path("Foo Device"), "picture.png")
        os.mknod(path)

        self.assertEqual(self.data_manager.newest_group(), "Bar Device")

    def test_newest_preset_ignores_unknown_filetypes(self):
        Preset(get_preset_path("Bar Device", "preset 1")).save()
        time.sleep(0.01)
        Preset(get_preset_path("Bar Device", "preset 2")).save()
        time.sleep(0.01)
        Preset(get_preset_path("Bar Device", "preset 3")).save()

        # not a preset, ignore
        time.sleep(0.01)
        path = os.path.join(get_preset_path("Bar Device"), "picture.png")
        os.mknod(path)

        self.data_manager.load_group("Bar Device")

        self.assertEqual(self.data_manager.newest_preset(), "preset 3")

    def test_newest_group_ignores_unknon_groups(self):
        Preset(get_preset_path("Bar Device", "preset 1")).save()
        time.sleep(0.01)
        Preset(get_preset_path("unknown_group", "preset 2")).save()  # not a known group

        self.assertEqual(self.data_manager.newest_group(), "Bar Device")

    def test_newest_group_and_preset_raises_file_not_found(self):
        """should raise file not found error when all preset folders are empty"""
        self.assertRaises(FileNotFoundError, self.data_manager.newest_group)
        os.makedirs(get_preset_path("Bar Device"))
        self.assertRaises(FileNotFoundError, self.data_manager.newest_group)
        self.data_manager.load_group("Bar Device")
        self.assertRaises(FileNotFoundError, self.data_manager.newest_preset)

    def test_newest_preset_raises_data_management_error(self):
        """should raise data management error without a active group"""
        self.assertRaises(DataManagementError, self.data_manager.newest_preset)

    def test_newest_preset_only_searches_active_group(self):
        Preset(get_preset_path("Foo Device", "preset 1")).save()
        time.sleep(0.01)
        Preset(get_preset_path("Foo Device", "preset 3")).save()
        time.sleep(0.01)
        Preset(get_preset_path("Bar Device", "preset 2")).save()

        self.data_manager.load_group("Foo Device")
        self.assertEqual(self.data_manager.newest_preset(), "preset 3")

    def test_available_preset_name_default(self):
        self.data_manager.load_group("Foo Device")
        self.assertEqual(
            self.data_manager.get_available_preset_name(), DEFAULT_PRESET_NAME
        )

    def test_available_preset_name_adds_number_to_default(self):
        Preset(get_preset_path("Foo Device", DEFAULT_PRESET_NAME)).save()
        self.data_manager.load_group("Foo Device")
        self.assertEqual(
            self.data_manager.get_available_preset_name(), f"{DEFAULT_PRESET_NAME} 2"
        )

    def test_available_preset_name_returns_provided_name(self):
        self.data_manager.load_group("Foo Device")
        self.assertEqual(self.data_manager.get_available_preset_name("bar"), "bar")

    def test_available_preset_name__adds_number_to_provided_name(self):
        Preset(get_preset_path("Foo Device", "bar")).save()
        self.data_manager.load_group("Foo Device")
        self.assertEqual(self.data_manager.get_available_preset_name("bar"), "bar 2")

    def test_available_preset_name_raises_data_management_error(self):
        """should raise DataManagementError when group is not set"""
        self.assertRaises(
            DataManagementError, self.data_manager.get_available_preset_name
        )

    def test_available_preset_name_increments_default(self):
        Preset(get_preset_path("Foo Device", DEFAULT_PRESET_NAME)).save()
        Preset(get_preset_path("Foo Device", f"{DEFAULT_PRESET_NAME} 2")).save()
        Preset(get_preset_path("Foo Device", f"{DEFAULT_PRESET_NAME} 3")).save()
        self.data_manager.load_group("Foo Device")
        self.assertEqual(
            self.data_manager.get_available_preset_name(), f"{DEFAULT_PRESET_NAME} 4"
        )

    def test_available_preset_name_increments_provided_name(self):
        Preset(get_preset_path("Foo Device", "foo")).save()
        Preset(get_preset_path("Foo Device", "foo 1")).save()
        Preset(get_preset_path("Foo Device", "foo 2")).save()
        self.data_manager.load_group("Foo Device")
        self.assertEqual(self.data_manager.get_available_preset_name("foo 1"), "foo 3")
