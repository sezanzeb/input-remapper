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
import unittest
from unittest.mock import patch

from evdev.ecodes import EV_KEY, EV_ABS

from inputremapper.configs.mapping import Mapping
from inputremapper.configs.mapping import UIMapping
from inputremapper.configs.paths import get_preset_path, get_config_path, CONFIG_PATH
from inputremapper.configs.preset import Preset
from inputremapper.configs.input_config import InputCombination, InputConfig
from tests.lib.cleanup import quick_cleanup
from tests.lib.fixtures import get_combination_config


class TestPreset(unittest.TestCase):
    def setUp(self):
        self.preset = Preset(get_preset_path("foo", "bar2"))
        self.assertFalse(self.preset.has_unsaved_changes())

    def tearDown(self):
        quick_cleanup()

    def test_is_mapped_multiple_times(self):
        combination = InputCombination(
            get_combination_config((1, 1, 1), (2, 2, 2), (3, 3, 3), (4, 4, 4))
        )
        permutations = combination.get_permutations()
        self.assertEqual(len(permutations), 6)

        self.preset._mappings[permutations[0]] = Mapping(
            input_combination=permutations[0],
            target_uinput="keyboard",
            output_symbol="a",
        )
        self.assertFalse(self.preset._is_mapped_multiple_times(permutations[2]))

        self.preset._mappings[permutations[1]] = Mapping(
            input_combination=permutations[1],
            target_uinput="keyboard",
            output_symbol="a",
        )
        self.assertTrue(self.preset._is_mapped_multiple_times(permutations[2]))

    def test_has_unsaved_changes(self):
        self.preset.path = get_preset_path("foo", "bar2")
        self.preset.add(Mapping.from_combination())
        self.assertTrue(self.preset.has_unsaved_changes())
        self.preset.save()
        self.assertFalse(self.preset.has_unsaved_changes())

        self.preset.empty()
        self.assertEqual(len(self.preset), 0)
        # empty preset but non-empty file
        self.assertTrue(self.preset.has_unsaved_changes())

        # load again from the disc
        self.preset.load()
        self.assertEqual(
            self.preset.get_mapping(InputCombination.empty_combination()),
            Mapping.from_combination(),
        )
        self.assertFalse(self.preset.has_unsaved_changes())

        # change the path to a non exiting file
        self.preset.path = get_preset_path("bar", "foo")
        # the preset has a mapping, the file has not
        self.assertTrue(self.preset.has_unsaved_changes())

        # change back to the original path
        self.preset.path = get_preset_path("foo", "bar2")
        # no difference between file and memory
        self.assertFalse(self.preset.has_unsaved_changes())

        # modify the mapping
        mapping = self.preset.get_mapping(InputCombination.empty_combination())
        mapping.gain = 0.5
        self.assertTrue(self.preset.has_unsaved_changes())
        self.preset.load()

        self.preset.path = get_preset_path("bar", "foo")
        self.preset.remove(Mapping.from_combination().input_combination)
        # empty preset and empty file
        self.assertFalse(self.preset.has_unsaved_changes())

        self.preset.path = get_preset_path("foo", "bar2")
        # empty preset, but non-empty file
        self.assertTrue(self.preset.has_unsaved_changes())
        self.preset.load()
        self.assertEqual(len(self.preset), 1)
        self.assertFalse(self.preset.has_unsaved_changes())

        # delete the preset from the system:
        self.preset.empty()
        self.preset.save()
        self.preset.load()
        self.assertFalse(self.preset.has_unsaved_changes())
        self.assertEqual(len(self.preset), 0)

    def test_save_load(self):
        one = InputConfig(type=EV_KEY, code=10)
        two = InputConfig(type=EV_KEY, code=11)
        three = InputConfig(type=EV_KEY, code=12)

        self.preset.add(
            Mapping.from_combination(InputCombination([one]), "keyboard", "1")
        )
        self.preset.add(
            Mapping.from_combination(InputCombination([two]), "keyboard", "2")
        )
        self.preset.add(
            Mapping.from_combination(InputCombination((two, three)), "keyboard", "3"),
        )
        self.preset.path = get_preset_path("Foo Device", "test")
        self.preset.save()

        path = os.path.join(CONFIG_PATH, "presets", "Foo Device", "test.json")
        self.assertTrue(os.path.exists(path))

        loaded = Preset(get_preset_path("Foo Device", "test"))
        self.assertEqual(len(loaded), 0)
        loaded.load()

        self.assertEqual(len(loaded), 3)
        self.assertRaises(TypeError, loaded.get_mapping, one)
        self.assertEqual(
            loaded.get_mapping(InputCombination([one])),
            Mapping.from_combination(InputCombination([one]), "keyboard", "1"),
        )
        self.assertEqual(
            loaded.get_mapping(InputCombination([two])),
            Mapping.from_combination(InputCombination([two]), "keyboard", "2"),
        )
        self.assertEqual(
            loaded.get_mapping(InputCombination([two, three])),
            Mapping.from_combination(InputCombination([two, three]), "keyboard", "3"),
        )

        # load missing file
        preset = Preset(get_config_path("missing_file.json"))
        self.assertRaises(FileNotFoundError, preset.load)

    def test_modify_mapping(self):
        ev_1 = InputCombination([InputConfig(type=EV_KEY, code=1)])
        ev_3 = InputCombination([InputConfig(type=EV_KEY, code=2)])
        # only values between -99 and 99 are allowed as mapping for EV_ABS or EV_REL
        ev_4 = InputCombination([InputConfig(type=EV_ABS, code=1, analog_threshold=99)])

        # add the first mapping
        self.preset.add(Mapping.from_combination(ev_1, "keyboard", "a"))
        self.assertTrue(self.preset.has_unsaved_changes())
        self.assertEqual(len(self.preset), 1)

        # change ev_1 to ev_3 and change a to b
        mapping = self.preset.get_mapping(ev_1)
        mapping.input_combination = ev_3
        mapping.output_symbol = "b"
        self.assertIsNone(self.preset.get_mapping(ev_1))
        self.assertEqual(
            self.preset.get_mapping(ev_3),
            Mapping.from_combination(ev_3, "keyboard", "b"),
        )
        self.assertEqual(len(self.preset), 1)

        # add 4
        self.preset.add(Mapping.from_combination(ev_4, "keyboard", "c"))
        self.assertEqual(
            self.preset.get_mapping(ev_3),
            Mapping.from_combination(ev_3, "keyboard", "b"),
        )
        self.assertEqual(
            self.preset.get_mapping(ev_4),
            Mapping.from_combination(ev_4, "keyboard", "c"),
        )
        self.assertEqual(len(self.preset), 2)

        # change the preset of 4 to d
        mapping = self.preset.get_mapping(ev_4)
        mapping.output_symbol = "d"
        self.assertEqual(
            self.preset.get_mapping(ev_4),
            Mapping.from_combination(ev_4, "keyboard", "d"),
        )
        self.assertEqual(len(self.preset), 2)

        # try to change combination of 4 to 3
        mapping = self.preset.get_mapping(ev_4)
        with self.assertRaises(KeyError):
            mapping.input_combination = ev_3

        self.assertEqual(
            self.preset.get_mapping(ev_3),
            Mapping.from_combination(ev_3, "keyboard", "b"),
        )
        self.assertEqual(
            self.preset.get_mapping(ev_4),
            Mapping.from_combination(ev_4, "keyboard", "d"),
        )
        self.assertEqual(len(self.preset), 2)

    def test_avoids_redundant_saves(self):
        with patch.object(self.preset, "has_unsaved_changes", lambda: False):
            self.preset.path = get_preset_path("foo", "bar2")
            self.preset.add(Mapping.from_combination())
            self.preset.save()

        with open(get_preset_path("foo", "bar2"), "r") as f:
            content = f.read()

        self.assertFalse(content)

    def test_combinations(self):
        ev_1 = InputConfig(type=EV_KEY, code=1, analog_threshold=111)
        ev_2 = InputConfig(type=EV_KEY, code=1, analog_threshold=222)
        ev_3 = InputConfig(type=EV_KEY, code=2, analog_threshold=111)
        ev_4 = InputConfig(type=EV_ABS, code=1, analog_threshold=99)
        combi_1 = InputCombination((ev_1, ev_2, ev_3))
        combi_2 = InputCombination((ev_2, ev_1, ev_3))
        combi_3 = InputCombination((ev_1, ev_2, ev_4))

        self.preset.add(Mapping.from_combination(combi_1, "keyboard", "a"))
        self.assertEqual(
            self.preset.get_mapping(combi_1),
            Mapping.from_combination(combi_1, "keyboard", "a"),
        )
        self.assertEqual(
            self.preset.get_mapping(combi_2),
            Mapping.from_combination(combi_1, "keyboard", "a"),
        )
        # since combi_1 and combi_2 are equivalent, this raises a KeyError
        self.assertRaises(
            KeyError,
            self.preset.add,
            Mapping.from_combination(combi_2, "keyboard", "b"),
        )
        self.assertEqual(
            self.preset.get_mapping(combi_1),
            Mapping.from_combination(combi_1, "keyboard", "a"),
        )
        self.assertEqual(
            self.preset.get_mapping(combi_2),
            Mapping.from_combination(combi_1, "keyboard", "a"),
        )

        self.preset.add(Mapping.from_combination(combi_3, "keyboard", "c"))
        self.assertEqual(
            self.preset.get_mapping(combi_1),
            Mapping.from_combination(combi_1, "keyboard", "a"),
        )
        self.assertEqual(
            self.preset.get_mapping(combi_2),
            Mapping.from_combination(combi_1, "keyboard", "a"),
        )
        self.assertEqual(
            self.preset.get_mapping(combi_3),
            Mapping.from_combination(combi_3, "keyboard", "c"),
        )

        mapping = self.preset.get_mapping(combi_1)
        mapping.output_symbol = "c"
        with self.assertRaises(KeyError):
            mapping.input_combination = combi_3

        self.assertEqual(
            self.preset.get_mapping(combi_1),
            Mapping.from_combination(combi_1, "keyboard", "c"),
        )
        self.assertEqual(
            self.preset.get_mapping(combi_2),
            Mapping.from_combination(combi_1, "keyboard", "c"),
        )
        self.assertEqual(
            self.preset.get_mapping(combi_3),
            Mapping.from_combination(combi_3, "keyboard", "c"),
        )

    def test_remove(self):
        # does nothing
        ev_1 = InputCombination([InputConfig(type=EV_KEY, code=40)])
        ev_2 = InputCombination([InputConfig(type=EV_KEY, code=30)])
        ev_3 = InputCombination([InputConfig(type=EV_KEY, code=20)])
        ev_4 = InputCombination([InputConfig(type=EV_KEY, code=10)])

        self.assertRaises(TypeError, self.preset.remove, (EV_KEY, 10, 1))
        self.preset.remove(ev_1)
        self.assertFalse(self.preset.has_unsaved_changes())
        self.assertEqual(len(self.preset), 0)

        self.preset.add(Mapping.from_combination(input_combination=ev_1))
        self.assertEqual(len(self.preset), 1)
        self.preset.remove(ev_1)
        self.assertEqual(len(self.preset), 0)

        self.preset.add(Mapping.from_combination(ev_4, "keyboard", "KEY_KP1"))
        self.assertTrue(self.preset.has_unsaved_changes())
        self.preset.add(Mapping.from_combination(ev_3, "keyboard", "KEY_KP2"))
        self.preset.add(Mapping.from_combination(ev_2, "keyboard", "KEY_KP3"))
        self.assertEqual(len(self.preset), 3)
        self.preset.remove(ev_3)
        self.assertEqual(len(self.preset), 2)
        self.assertEqual(
            self.preset.get_mapping(ev_4),
            Mapping.from_combination(ev_4, "keyboard", "KEY_KP1"),
        )
        self.assertIsNone(self.preset.get_mapping(ev_3))
        self.assertEqual(
            self.preset.get_mapping(ev_2),
            Mapping.from_combination(ev_2, "keyboard", "KEY_KP3"),
        )

    def test_empty(self):
        self.preset.add(
            Mapping.from_combination(
                InputCombination([InputConfig(type=EV_KEY, code=10)]),
                "keyboard",
                "1",
            ),
        )
        self.preset.add(
            Mapping.from_combination(
                InputCombination([InputConfig(type=EV_KEY, code=11)]),
                "keyboard",
                "2",
            ),
        )
        self.preset.add(
            Mapping.from_combination(
                InputCombination([InputConfig(type=EV_KEY, code=12)]),
                "keyboard",
                "3",
            ),
        )
        self.assertEqual(len(self.preset), 3)
        self.preset.path = get_config_path("test.json")
        self.preset.save()
        self.assertFalse(self.preset.has_unsaved_changes())

        self.preset.empty()
        self.assertEqual(self.preset.path, get_config_path("test.json"))
        self.assertTrue(self.preset.has_unsaved_changes())
        self.assertEqual(len(self.preset), 0)

    def test_clear(self):
        self.preset.add(
            Mapping.from_combination(
                InputCombination([InputConfig(type=EV_KEY, code=10)]),
                "keyboard",
                "1",
            ),
        )
        self.preset.add(
            Mapping.from_combination(
                InputCombination([InputConfig(type=EV_KEY, code=11)]),
                "keyboard",
                "2",
            ),
        )
        self.preset.add(
            Mapping.from_combination(
                InputCombination([InputConfig(type=EV_KEY, code=12)]),
                "keyboard",
                "3",
            ),
        )
        self.assertEqual(len(self.preset), 3)
        self.preset.path = get_config_path("test.json")
        self.preset.save()
        self.assertFalse(self.preset.has_unsaved_changes())

        self.preset.clear()
        self.assertFalse(self.preset.has_unsaved_changes())
        self.assertIsNone(self.preset.path)
        self.assertEqual(len(self.preset), 0)

    def test_dangerously_mapped_btn_left(self):
        # btn left is mapped
        self.preset.add(
            Mapping.from_combination(
                InputCombination([InputConfig.btn_left()]),
                "keyboard",
                "1",
            )
        )
        self.assertTrue(self.preset.dangerously_mapped_btn_left())
        self.preset.add(
            Mapping.from_combination(
                InputCombination([InputConfig(type=EV_KEY, code=41)]),
                "keyboard",
                "2",
            )
        )
        self.assertTrue(self.preset.dangerously_mapped_btn_left())

        # another mapping maps to btn_left
        self.preset.add(
            Mapping.from_combination(
                InputCombination([InputConfig(type=EV_KEY, code=42)]),
                "mouse",
                "btn_left",
            )
        )
        self.assertFalse(self.preset.dangerously_mapped_btn_left())

        mapping = self.preset.get_mapping(
            InputCombination([InputConfig(type=EV_KEY, code=42)])
        )
        mapping.output_symbol = "BTN_Left"
        self.assertFalse(self.preset.dangerously_mapped_btn_left())

        mapping.target_uinput = "keyboard"
        mapping.output_symbol = "3"
        self.assertTrue(self.preset.dangerously_mapped_btn_left())

        # btn_left is not mapped
        self.preset.remove(InputCombination([InputConfig.btn_left()]))
        self.assertFalse(self.preset.dangerously_mapped_btn_left())

    def test_save_load_with_invalid_mappings(self):
        ui_preset = Preset(get_config_path("test.json"), mapping_factory=UIMapping)

        ui_preset.add(UIMapping())
        self.assertFalse(ui_preset.is_valid())

        # make the mapping valid
        m = ui_preset.get_mapping(InputCombination.empty_combination())
        m.output_symbol = "a"
        m.target_uinput = "keyboard"
        self.assertTrue(ui_preset.is_valid())

        m2 = UIMapping(
            input_combination=InputCombination([InputConfig(type=1, code=2)])
        )
        ui_preset.add(m2)
        self.assertFalse(ui_preset.is_valid())
        ui_preset.save()

        # only the valid preset is loaded
        preset = Preset(get_config_path("test.json"))
        preset.load()
        self.assertEqual(len(preset), 1)

        a = preset.get_mapping(m.input_combination).dict()
        b = m.dict()
        a.pop("mapping_type")
        b.pop("mapping_type")
        self.assertEqual(a, b)
        # self.assertEqual(preset.get_mapping(m.input_combination), m)

        # both presets load
        ui_preset.clear()
        ui_preset.path = get_config_path("test.json")
        ui_preset.load()
        self.assertEqual(len(ui_preset), 2)

        a = ui_preset.get_mapping(m.input_combination).dict()
        b = m.dict()
        a.pop("mapping_type")
        b.pop("mapping_type")
        self.assertEqual(a, b)
        # self.assertEqual(ui_preset.get_mapping(m.input_combination), m)
        self.assertEqual(ui_preset.get_mapping(m2.input_combination), m2)


if __name__ == "__main__":
    unittest.main()
