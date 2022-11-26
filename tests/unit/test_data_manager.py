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
import os
import time
import unittest
from itertools import permutations
from typing import List
from unittest.mock import MagicMock, call

from inputremapper.configs.global_config import global_config
from inputremapper.configs.mapping import UIMapping, MappingData
from inputremapper.configs.system_mapping import system_mapping
from inputremapper.input_configuration import InputCombination, InputConfig
from inputremapper.exceptions import DataManagementError
from inputremapper.groups import _Groups
from inputremapper.gui.messages.message_broker import (
    MessageBroker,
    MessageType,
)
from inputremapper.gui.messages.message_data import (
    GroupData,
    CombinationUpdate,
)
from inputremapper.gui.reader_client import ReaderClient
from inputremapper.injection.global_uinputs import GlobalUInputs
from inputremapper.input_event import InputEvent
from tests.lib.cleanup import quick_cleanup
from tests.lib.patches import FakeDaemonProxy
from tests.lib.fixtures import prepare_presets, get_combination_config

from inputremapper.configs.paths import get_preset_path
from inputremapper.configs.preset import Preset
from inputremapper.gui.data_manager import DataManager, DEFAULT_PRESET_NAME


class Listener:
    def __init__(self):
        self.calls: List = []

    def __call__(self, data):
        self.calls.append(data)


class TestDataManager(unittest.TestCase):
    def setUp(self) -> None:
        self.message_broker = MessageBroker()
        self.reader = ReaderClient(self.message_broker, _Groups())
        self.uinputs = GlobalUInputs()
        self.uinputs.prepare_all()
        self.data_manager = DataManager(
            self.message_broker,
            global_config,
            self.reader,
            FakeDaemonProxy(),
            self.uinputs,
            system_mapping,
        )

    def tearDown(self) -> None:
        quick_cleanup()

    def test_load_group_provides_presets(self):
        """we should get all preset of a group, when loading it"""
        prepare_presets()
        response: List[GroupData] = []

        def listener(data: GroupData):
            response.append(data)

        self.message_broker.subscribe(MessageType.group, listener)
        self.data_manager.load_group("Foo Device 2")

        for preset_name in response[0].presets:
            self.assertIn(
                preset_name,
                (
                    "preset1",
                    "preset2",
                    "preset3",
                ),
            )

        self.assertEqual(response[0].group_key, "Foo Device 2")

    def test_load_group_without_presets_provides_none(self):
        """We should get no presets when loading a group without presets."""
        response: List[GroupData] = []

        def listener(data: GroupData):
            response.append(data)

        self.message_broker.subscribe(MessageType.group, listener)

        self.data_manager.load_group(group_key="Foo Device 2")
        self.assertEqual(len(response[0].presets), 0)

    def test_load_non_existing_group(self):
        """we should not be able to load an unknown group"""
        with self.assertRaises(DataManagementError):
            self.data_manager.load_group(group_key="Some Unknown Device")

    def test_cannot_load_preset_without_group(self):
        """Loading a preset without a loaded group raises a DataManagementError."""
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
        self.message_broker.subscribe(MessageType.preset, listener)
        self.data_manager.load_preset(name="preset1")
        mappings = listener.calls[0].mappings
        preset_name = listener.calls[0].name

        expected_preset = Preset(get_preset_path("Foo Device", "preset1"))
        expected_preset.load()
        expected_mappings = list(expected_preset)

        self.assertEqual(preset_name, "preset1")
        for mapping in expected_mappings:
            self.assertIn(mapping, mappings)

    def test_cannot_load_non_existing_preset(self):
        """Loading a non-existing preset should raise a KeyError."""
        prepare_presets()

        self.data_manager.load_group(group_key="Foo Device")
        self.assertRaises(
            FileNotFoundError,
            self.data_manager.load_preset,
            name="unknownPreset",
        )

    def test_save_preset(self):
        """Modified preses should be saved to the disc."""
        prepare_presets()
        # make sure the correct preset is loaded
        self.data_manager.load_group(group_key="Foo Device")
        self.data_manager.load_preset(name="preset1")
        listener = Listener()
        self.message_broker.subscribe(MessageType.mapping, listener)
        self.data_manager.load_mapping(
            combination=InputCombination(InputConfig(type=1, code=1))
        )

        mapping: MappingData = listener.calls[0]
        control_preset = Preset(get_preset_path("Foo Device", "preset1"))
        control_preset.load()
        self.assertEqual(
            control_preset.get_mapping(
                InputCombination(InputConfig(type=1, code=1))
            ).output_symbol,
            mapping.output_symbol,
        )

        # change the mapping provided with the mapping_changed event and save
        self.data_manager.update_mapping(output_symbol="key(a)")
        self.data_manager.save()

        # reload the control_preset
        control_preset.empty()
        control_preset.load()
        self.assertEqual(
            control_preset.get_mapping(
                InputCombination(InputConfig(type=1, code=1))
            ).output_symbol,
            "key(a)",
        )

    def test_copy_preset(self):
        prepare_presets()
        self.data_manager.load_group(group_key="Foo Device 2")
        self.data_manager.load_preset(name="preset2")
        listener = Listener()
        self.message_broker.subscribe(MessageType.group, listener)
        self.message_broker.subscribe(MessageType.preset, listener)

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
        self.message_broker.subscribe(MessageType.group, listener)
        self.message_broker.subscribe(MessageType.preset, listener)

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
        self.message_broker.subscribe(MessageType.preset, listener)
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
        self.message_broker.subscribe(MessageType.group, listener)

        # should emit group_changed
        self.data_manager.create_preset(name="new preset")

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
            self.data_manager.create_preset,
            name="preset3",
        )

    def test_cannot_add_preset_without_group(self):
        self.assertRaises(
            DataManagementError,
            self.data_manager.create_preset,
            name="foo",
        )

    def test_delete_preset(self):
        """should be able to delete the current preset"""
        prepare_presets()
        self.data_manager.load_group(group_key="Foo Device 2")
        self.data_manager.load_preset(name="preset2")
        listener = Listener()
        self.message_broker.subscribe(MessageType.group, listener)
        self.message_broker.subscribe(MessageType.preset, listener)
        self.message_broker.subscribe(MessageType.mapping, listener)

        # should emit only group_changed
        self.data_manager.delete_preset()

        presets_in_group = [preset for preset in listener.calls[0].presets]
        self.assertEqual(len(presets_in_group), 2)
        self.assertNotIn("preset2", presets_in_group)
        self.assertEqual(len(listener.calls), 1)

    def test_delete_preset_sanitized(self):
        """should be able to delete the current preset"""
        Preset(get_preset_path("Qux/Device?", "bla")).save()
        Preset(get_preset_path("Qux/Device?", "foo")).save()
        self.assertTrue(os.path.exists(get_preset_path("Qux/Device?", "bla")))

        self.data_manager.load_group(group_key="Qux/Device?")
        self.data_manager.load_preset(name="bla")
        listener = Listener()
        self.message_broker.subscribe(MessageType.group, listener)
        self.message_broker.subscribe(MessageType.preset, listener)
        self.message_broker.subscribe(MessageType.mapping, listener)

        # should emit only group_changed
        self.data_manager.delete_preset()

        presets_in_group = [preset for preset in listener.calls[0].presets]
        self.assertEqual(len(presets_in_group), 1)
        self.assertNotIn("bla", presets_in_group)
        self.assertIn("foo", presets_in_group)
        self.assertEqual(len(listener.calls), 1)

        self.assertFalse(os.path.exists(get_preset_path("Qux/Device?", "bla")))

    def test_load_mapping(self):
        """should be able to load a mapping"""
        preset, _, _ = prepare_presets()
        expected_mapping = preset.get_mapping(
            InputCombination(InputConfig(type=1, code=1))
        )

        self.data_manager.load_group(group_key="Foo Device")
        self.data_manager.load_preset(name="preset1")
        listener = Listener()
        self.message_broker.subscribe(MessageType.mapping, listener)
        self.data_manager.load_mapping(
            combination=InputCombination(InputConfig(type=1, code=1))
        )
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
            combination=InputCombination(InputConfig(type=1, code=1)),
        )

    def test_cannot_load_mapping_without_preset(self):
        """loading a mapping if no preset is loaded
        should raise an DataManagementError"""
        prepare_presets()

        self.assertRaises(
            DataManagementError,
            self.data_manager.load_mapping,
            combination=InputCombination(InputConfig(type=1, code=1)),
        )
        self.data_manager.load_group("Foo Device")
        self.assertRaises(
            DataManagementError,
            self.data_manager.load_mapping,
            combination=InputCombination(InputConfig(type=1, code=1)),
        )

    def test_load_event(self):
        prepare_presets()
        mock = MagicMock()
        self.message_broker.subscribe(MessageType.selected_event, mock)
        self.data_manager.load_group("Foo Device")
        self.data_manager.load_preset("preset1")
        self.data_manager.load_mapping(InputCombination(InputConfig(type=1, code=1)))
        self.data_manager.load_input_config(InputConfig(type=1, code=1))
        mock.assert_called_once_with(InputConfig(type=1, code=1))
        self.assertEqual(
            self.data_manager.active_input_config, InputConfig(type=1, code=1)
        )

    def test_cannot_load_event_when_mapping_not_set(self):
        prepare_presets()
        self.data_manager.load_group("Foo Device")
        self.data_manager.load_preset("preset1")
        with self.assertRaises(DataManagementError):
            self.data_manager.load_input_config(InputConfig(type=1, code=1))

    def test_cannot_load_event_when_not_in_mapping_combination(self):
        prepare_presets()
        self.data_manager.load_group("Foo Device")
        self.data_manager.load_preset("preset1")
        self.data_manager.load_mapping(InputCombination(InputConfig(type=1, code=1)))
        with self.assertRaises(ValueError):
            self.data_manager.load_input_config(InputConfig(type=1, code=5))

    def test_update_event(self):
        prepare_presets()
        self.data_manager.load_group("Foo Device")
        self.data_manager.load_preset("preset1")
        self.data_manager.load_mapping(InputCombination(InputConfig(type=1, code=1)))
        self.data_manager.load_input_config(InputConfig(type=1, code=1))
        self.data_manager.update_input_config(InputConfig(type=1, code=5))
        self.assertEqual(
            self.data_manager.active_input_config, InputConfig(type=1, code=5)
        )

    def test_update_event_sends_messages(self):
        prepare_presets()
        self.data_manager.load_group("Foo Device")
        self.data_manager.load_preset("preset1")
        self.data_manager.load_mapping(InputCombination(InputConfig(type=1, code=1)))
        self.data_manager.load_input_config(InputConfig(type=1, code=1))

        mock = MagicMock()
        self.message_broker.subscribe(MessageType.selected_event, mock)
        self.message_broker.subscribe(MessageType.combination_update, mock)
        self.message_broker.subscribe(MessageType.mapping, mock)
        self.data_manager.update_input_config(InputConfig(type=1, code=5))
        expected = [
            call(
                CombinationUpdate(
                    InputCombination(InputConfig(type=1, code=1)),
                    InputCombination(InputConfig(type=1, code=5)),
                )
            ),
            call(self.data_manager.active_mapping.get_bus_message()),
            call(InputConfig(type=1, code=5)),
        ]
        mock.assert_has_calls(expected, any_order=False)

    def test_cannot_update_event_when_resulting_combination_exists(self):
        prepare_presets()
        self.data_manager.load_group("Foo Device")
        self.data_manager.load_preset("preset1")
        self.data_manager.load_mapping(InputCombination(InputConfig(type=1, code=1)))
        self.data_manager.load_input_config(InputConfig(type=1, code=1))
        with self.assertRaises(KeyError):
            self.data_manager.update_input_config(InputConfig(type=1, code=2))

    def test_cannot_update_event_when_not_loaded(self):
        prepare_presets()
        self.data_manager.load_group("Foo Device")
        self.data_manager.load_preset("preset1")
        self.data_manager.load_mapping(InputCombination(InputConfig(type=1, code=1)))
        with self.assertRaises(DataManagementError):
            self.data_manager.update_input_config(InputConfig(type=1, code=2))

    def test_update_mapping_emits_mapping_changed(self):
        """update mapping should emit a mapping_changed event"""
        prepare_presets()
        self.data_manager.load_group(group_key="Foo Device 2")
        self.data_manager.load_preset(name="preset2")
        self.data_manager.load_mapping(
            combination=InputCombination(InputConfig(type=1, code=4))
        )

        listener = Listener()
        self.message_broker.subscribe(MessageType.mapping, listener)
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
        self.data_manager.load_mapping(
            combination=InputCombination(InputConfig(type=1, code=4))
        )

        self.data_manager.update_mapping(
            name="foo",
            output_symbol="f",
            release_timeout=0.3,
        )
        self.data_manager.save()

        preset = Preset(get_preset_path("Foo Device", "preset2"), UIMapping)
        preset.load()
        mapping = preset.get_mapping(InputCombination(InputConfig(type=1, code=4)))
        self.assertEqual(mapping.format_name(), "foo")
        self.assertEqual(mapping.output_symbol, "f")
        self.assertEqual(mapping.release_timeout, 0.3)

    def test_updated_mapping_saves_invalid_mapping(self):
        """make sure that updated changes can be saved even if they are not valid"""
        prepare_presets()
        self.data_manager.load_group(group_key="Foo Device 2")
        self.data_manager.load_preset(name="preset2")
        self.data_manager.load_mapping(
            combination=InputCombination(InputConfig(type=1, code=4))
        )

        self.data_manager.update_mapping(
            output_symbol="bar",  # not a macro and not a valid symbol
        )
        self.data_manager.save()

        preset = Preset(get_preset_path("Foo Device", "preset2"), UIMapping)
        preset.load()
        mapping = preset.get_mapping(InputCombination(InputConfig(type=1, code=4)))
        self.assertIsNotNone(mapping.get_error())
        self.assertEqual(mapping.output_symbol, "bar")

    def test_update_mapping_combination_sends_massage(self):
        prepare_presets()

        self.data_manager.load_group(group_key="Foo Device 2")
        self.data_manager.load_preset(name="preset2")
        self.data_manager.load_mapping(
            combination=InputCombination(InputConfig(type=1, code=4))
        )
        listener = Listener()
        self.message_broker.subscribe(MessageType.mapping, listener)
        self.message_broker.subscribe(MessageType.combination_update, listener)

        # we expect a message for combination update first, and then for mapping
        self.data_manager.update_mapping(
            event_combination=InputCombination(get_combination_config((1, 5), (1, 6)))
        )
        self.assertEqual(listener.calls[0].message_type, MessageType.combination_update)
        self.assertEqual(
            listener.calls[0].old_combination,
            InputCombination(InputConfig(type=1, code=4)),
        )
        self.assertEqual(
            listener.calls[0].new_combination,
            InputCombination(get_combination_config((1, 5), (1, 6))),
        )
        self.assertEqual(listener.calls[1].message_type, MessageType.mapping)
        self.assertEqual(
            listener.calls[1].event_combination,
            InputCombination(get_combination_config((1, 5), (1, 6))),
        )

    def test_cannot_update_mapping_combination(self):
        """updating a mapping with an already existing combination
        should raise a KeyError"""
        prepare_presets()
        self.data_manager.load_group(group_key="Foo Device 2")
        self.data_manager.load_preset(name="preset2")
        self.data_manager.load_mapping(
            combination=InputCombination(InputConfig(type=1, code=4))
        )

        self.assertRaises(
            KeyError,
            self.data_manager.update_mapping,
            event_combination=InputCombination(InputConfig(type=1, code=3)),
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
        self.message_broker.subscribe(MessageType.mapping, listener)
        self.message_broker.subscribe(MessageType.preset, listener)
        self.data_manager.create_mapping()  # emits preset_changed

        self.data_manager.load_mapping(combination=InputCombination.empty_combination())

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

        old_preset = Preset(get_preset_path("Foo Device", "preset2"))
        old_preset.load()

        self.data_manager.load_group(group_key="Foo Device 2")
        self.data_manager.load_preset(name="preset2")
        self.data_manager.load_mapping(
            combination=InputCombination(InputConfig(type=1, code=3))
        )

        listener = Listener()
        self.message_broker.subscribe(MessageType.preset, listener)
        self.message_broker.subscribe(MessageType.mapping, listener)

        self.data_manager.delete_mapping()  # emits preset
        self.data_manager.save()

        deleted_mapping = old_preset.get_mapping(
            InputCombination(InputConfig(type=1, code=3))
        )
        mappings = listener.calls[0].mappings
        preset_name = listener.calls[0].name
        expected_preset = Preset(get_preset_path("Foo Device", "preset2"))
        expected_preset.load()
        expected_mappings = list(expected_preset)

        self.assertEqual(preset_name, "preset2")
        for mapping in expected_mappings:
            self.assertIn(mapping, mappings)

        self.assertNotIn(deleted_mapping, mappings)

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
        self.message_broker.subscribe(MessageType.preset, listener)
        self.data_manager.load_preset(name="preset1")  # sends updated preset data
        self.data_manager.set_autoload(True)  # sends updated preset data
        self.data_manager.set_autoload(False)  # sends updated preset data

        self.assertFalse(listener.calls[0].autoload)
        self.assertTrue(listener.calls[1].autoload)
        self.assertFalse(listener.calls[2].autoload)

    def test_each_device_can_have_autoload(self):
        prepare_presets()
        self.data_manager.load_group("Foo Device 2")
        self.data_manager.load_preset("preset1")
        self.data_manager.set_autoload(True)

        # switch to another device
        self.data_manager.load_group("Foo Device")
        self.data_manager.load_preset("preset1")
        self.data_manager.set_autoload(True)

        # now check that both are set to autoload
        self.data_manager.load_group("Foo Device 2")
        self.data_manager.load_preset("preset1")
        self.assertTrue(self.data_manager.get_autoload())

        self.data_manager.load_group("Foo Device")
        self.data_manager.load_preset("preset1")
        self.assertTrue(self.data_manager.get_autoload())

    def test_cannot_set_autoload_without_preset(self):
        prepare_presets()
        self.assertRaises(
            DataManagementError,
            self.data_manager.set_autoload,
            True,
        )
        self.data_manager.load_group(group_key="Foo Device 2")
        self.assertRaises(
            DataManagementError,
            self.data_manager.set_autoload,
            True,
        )

    def test_finds_newest_group(self):
        Preset(get_preset_path("Foo Device", "preset 1")).save()
        time.sleep(0.01)
        Preset(get_preset_path("Bar Device", "preset 2")).save()
        self.assertEqual(self.data_manager.get_newest_group_key(), "Bar Device")

    def test_finds_newest_preset(self):
        Preset(get_preset_path("Foo Device", "preset 1")).save()
        time.sleep(0.01)
        Preset(get_preset_path("Foo Device", "preset 2")).save()
        self.data_manager.load_group("Foo Device")
        self.assertEqual(self.data_manager.get_newest_preset_name(), "preset 2")

    def test_newest_group_ignores_unknown_filetypes(self):
        Preset(get_preset_path("Foo Device", "preset 1")).save()
        time.sleep(0.01)
        Preset(get_preset_path("Bar Device", "preset 2")).save()

        # not a preset, ignore
        time.sleep(0.01)
        path = os.path.join(get_preset_path("Foo Device"), "picture.png")
        os.mknod(path)

        self.assertEqual(self.data_manager.get_newest_group_key(), "Bar Device")

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

        self.assertEqual(self.data_manager.get_newest_preset_name(), "preset 3")

    def test_newest_group_ignores_unknon_groups(self):
        Preset(get_preset_path("Bar Device", "preset 1")).save()
        time.sleep(0.01)
        Preset(get_preset_path("unknown_group", "preset 2")).save()  # not a known group

        self.assertEqual(self.data_manager.get_newest_group_key(), "Bar Device")

    def test_newest_group_and_preset_raises_file_not_found(self):
        """should raise file not found error when all preset folders are empty"""
        self.assertRaises(FileNotFoundError, self.data_manager.get_newest_group_key)
        os.makedirs(get_preset_path("Bar Device"))
        self.assertRaises(FileNotFoundError, self.data_manager.get_newest_group_key)
        self.data_manager.load_group("Bar Device")
        self.assertRaises(FileNotFoundError, self.data_manager.get_newest_preset_name)

    def test_newest_preset_raises_data_management_error(self):
        """should raise data management error without an active group"""
        self.assertRaises(DataManagementError, self.data_manager.get_newest_preset_name)

    def test_newest_preset_only_searches_active_group(self):
        Preset(get_preset_path("Foo Device", "preset 1")).save()
        time.sleep(0.01)
        Preset(get_preset_path("Foo Device", "preset 3")).save()
        time.sleep(0.01)
        Preset(get_preset_path("Bar Device", "preset 2")).save()

        self.data_manager.load_group("Foo Device")
        self.assertEqual(self.data_manager.get_newest_preset_name(), "preset 3")

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

    def test_available_preset_name_sanitized(self):
        self.data_manager.load_group("Qux/Device?")
        self.assertEqual(
            self.data_manager.get_available_preset_name(), DEFAULT_PRESET_NAME
        )

        Preset(get_preset_path("Qux/Device?", DEFAULT_PRESET_NAME)).save()
        self.assertEqual(
            self.data_manager.get_available_preset_name(), f"{DEFAULT_PRESET_NAME} 2"
        )

        Preset(get_preset_path("Qux/Device?", "foo")).save()
        self.assertEqual(self.data_manager.get_available_preset_name("foo"), "foo 2")

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

    def test_should_publish_groups(self):
        listener = Listener()
        self.message_broker.subscribe(MessageType.groups, listener)

        self.data_manager.publish_groups()
        data = listener.calls[0]

        # we expect a list of tuples with the group key and their device types
        self.assertEqual(
            data.groups,
            {
                "Foo Device": ["keyboard"],
                "Foo Device 2": ["gamepad", "keyboard", "mouse"],
                "Bar Device": ["keyboard"],
                "gamepad": ["gamepad"],
                "Qux/Device?": ["keyboard"],
            },
        )

    def test_should_load_group(self):
        prepare_presets()
        listener = Listener()
        self.message_broker.subscribe(MessageType.group, listener)

        self.data_manager.load_group("Foo Device 2")

        self.assertEqual(self.data_manager.active_group.key, "Foo Device 2")
        data = (
            GroupData("Foo Device 2", (p1, p2, p3))
            for p1, p2, p3 in permutations(("preset3", "preset2", "preset1"))
        )
        self.assertIn(listener.calls[0], data)

    def test_should_start_reading_active_group(self):
        def f(*_):
            raise AssertionError()

        self.reader.set_group = f
        self.assertRaises(AssertionError, self.data_manager.load_group, "Foo Device")

    def test_should_send_uinputs(self):
        listener = Listener()
        self.message_broker.subscribe(MessageType.uinputs, listener)

        self.data_manager.publish_uinputs()
        data = listener.calls[0]

        # we expect a list of tuples with the group key and their device types
        self.assertEqual(
            data.uinputs,
            {
                "gamepad": self.uinputs.get_uinput("gamepad").capabilities(),
                "keyboard": self.uinputs.get_uinput("keyboard").capabilities(),
                "mouse": self.uinputs.get_uinput("mouse").capabilities(),
                "keyboard + mouse": self.uinputs.get_uinput(
                    "keyboard + mouse"
                ).capabilities(),
            },
        )

    def test_cannot_stop_injecting_without_group(self):
        self.assertRaises(DataManagementError, self.data_manager.stop_injecting)

    def test_cannot_start_injecting_without_preset(self):
        self.data_manager.load_group("Foo Device")
        self.assertRaises(DataManagementError, self.data_manager.start_injecting)

    def test_cannot_get_injector_state_without_group(self):
        self.assertRaises(DataManagementError, self.data_manager.get_state)
