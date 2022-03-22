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

from tests.test import tmp, quick_cleanup, get_key_mapping

import os
import unittest
import json
from unittest.mock import patch

from evdev.ecodes import EV_KEY, EV_ABS, KEY_A
from inputremapper.input_event import InputEvent

from inputremapper.configs.preset import Preset
from inputremapper.configs.system_mapping import SystemMapping, XMODMAP_FILENAME
from inputremapper.configs.paths import get_preset_path
from inputremapper.event_combination import EventCombination


class TestSystemMapping(unittest.TestCase):
    def tearDown(self):
        quick_cleanup()

    def test_update(self):
        system_mapping = SystemMapping()
        system_mapping.update({"foo1": 101, "bar1": 102})
        system_mapping.update({"foo2": 201, "bar2": 202})
        self.assertEqual(system_mapping.get("foo1"), 101)
        self.assertEqual(system_mapping.get("bar2"), 202)

    def test_xmodmap_file(self):
        system_mapping = SystemMapping()
        path = os.path.join(tmp, XMODMAP_FILENAME)
        os.remove(path)

        system_mapping.populate()
        self.assertTrue(os.path.exists(path))
        with open(path, "r") as file:
            content = json.load(file)
            self.assertEqual(content["a"], KEY_A)
            # only xmodmap stuff should be present
            self.assertNotIn("key_a", content)
            self.assertNotIn("KEY_A", content)
            self.assertNotIn("disable", content)

    def test_correct_case(self):
        system_mapping = SystemMapping()
        system_mapping.clear()
        system_mapping._set("A", 31)
        system_mapping._set("a", 32)
        system_mapping._set("abcd_B", 33)

        self.assertEqual(system_mapping.correct_case("a"), "a")
        self.assertEqual(system_mapping.correct_case("A"), "A")
        self.assertEqual(system_mapping.correct_case("ABCD_b"), "abcd_B")
        # unknown stuff is returned as is
        self.assertEqual(system_mapping.correct_case("FOo"), "FOo")

        self.assertEqual(system_mapping.get("A"), 31)
        self.assertEqual(system_mapping.get("a"), 32)
        self.assertEqual(system_mapping.get("ABCD_b"), 33)
        self.assertEqual(system_mapping.get("abcd_B"), 33)

    def test_system_mapping(self):
        system_mapping = SystemMapping()
        system_mapping.populate()
        self.assertGreater(len(system_mapping._mapping), 100)

        # this is case-insensitive
        self.assertEqual(system_mapping.get("1"), 2)
        self.assertEqual(system_mapping.get("KeY_1"), 2)

        self.assertEqual(system_mapping.get("AlT_L"), 56)
        self.assertEqual(system_mapping.get("KEy_LEFtALT"), 56)

        self.assertEqual(system_mapping.get("kEY_LeFTSHIFT"), 42)
        self.assertEqual(system_mapping.get("ShiFt_L"), 42)

        self.assertEqual(system_mapping.get("BTN_left"), 272)

        self.assertIsNotNone(system_mapping.get("KEY_KP4"))
        self.assertEqual(system_mapping.get("KP_Left"), system_mapping.get("KEY_KP4"))

        # this only lists the correct casing,
        # includes linux constants and xmodmap symbols
        names = system_mapping.list_names()
        self.assertIn("2", names)
        self.assertIn("c", names)
        self.assertIn("KEY_3", names)
        self.assertNotIn("key_3", names)
        self.assertIn("KP_Down", names)
        self.assertNotIn("kp_down", names)
        names = system_mapping._mapping.keys()
        self.assertIn("F4", names)
        self.assertNotIn("f4", names)
        self.assertIn("BTN_RIGHT", names)
        self.assertNotIn("btn_right", names)
        self.assertIn("KEY_KP7", names)
        self.assertIn("KP_Home", names)
        self.assertNotIn("kp_home", names)

        self.assertEqual(system_mapping.get("disable"), -1)


class TestPreset(unittest.TestCase):
    def setUp(self):
        self.preset = Preset(get_preset_path("foo", "bar2"))
        self.assertFalse(self.preset.has_unsaved_changes())

    def tearDown(self):
        quick_cleanup()

    def test_has_unsaved_changes(self):
        self.preset.path = get_preset_path("foo", "bar2")
        self.preset.add(get_key_mapping())
        self.assertTrue(self.preset.has_unsaved_changes())
        self.preset.save()
        self.assertFalse(self.preset.has_unsaved_changes())

        self.preset.empty()
        self.assertEqual(len(self.preset), 0)
        self.assertTrue(self.preset.has_unsaved_changes())  # empty preset but non-empty file

        # load again from the disc
        self.preset.load()
        self.assertEqual(
            self.preset.get_mapping(EventCombination([99, 99, 99])),
            get_key_mapping(),
        )
        self.assertFalse(self.preset.has_unsaved_changes())

        # change the path to a non exiting file
        self.preset.path = get_preset_path("bar", "foo")
        self.assertTrue(self.preset.has_unsaved_changes())  # the preset has a mapping, the file has not

        # change back to the original path
        self.preset.path = get_preset_path("foo", "bar2")
        self.assertFalse(self.preset.has_unsaved_changes())  # no difference between file and memory

        # modify the mapping
        mapping = self.preset.get_mapping(EventCombination([99, 99, 99]))
        mapping.gain = 0.5
        self.assertTrue(self.preset.has_unsaved_changes())
        self.preset.load()

        self.preset.path = get_preset_path("bar", "foo")
        self.preset.remove(get_key_mapping().event_combination)
        self.assertFalse(self.preset.has_unsaved_changes())  # empty preset and empty file

        self.preset.path = get_preset_path("foo", "bar2")
        self.assertTrue(self.preset.has_unsaved_changes())  # empty preset, but non-empty file
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
        one = InputEvent.from_tuple((EV_KEY, 10, 1))
        two = InputEvent.from_tuple((EV_KEY, 11, 1))
        three = InputEvent.from_tuple((EV_KEY, 12, 1))

        self.preset.add(get_key_mapping(EventCombination(one), "keyboard", "1"))
        self.preset.add(get_key_mapping(EventCombination(two), "keyboard", "2"))
        self.preset.add(get_key_mapping(EventCombination(two, three), "keyboard", "3"))
        self.preset.path = get_preset_path("Foo Device", "test")
        self.preset.save()

        path = os.path.join(tmp, "presets", "Foo Device", "test.json")
        self.assertTrue(os.path.exists(path))

        loaded = Preset(get_preset_path("Foo Device", "test"))
        self.assertEqual(len(loaded), 0)
        loaded.load()

        self.assertEqual(len(loaded), 3)
        self.assertRaises(TypeError, loaded.get_mapping, one)
        self.assertEqual(loaded.get_mapping(EventCombination(one)),
                         get_key_mapping(EventCombination(one), "keyboard", "1"))
        self.assertEqual(loaded.get_mapping(EventCombination(two)),
                         get_key_mapping(EventCombination(two), "keyboard", "2"))
        self.assertEqual(
            loaded.get_mapping(EventCombination(two, three)),
            get_key_mapping(EventCombination(two, three), "keyboard", "3")
        )

    def test_modify_mapping(self):
        # the reader would not report values like 111 or 222, only 1 or -1.
        # the preset just does what it is told, so it accepts them.
        ev_1 = EventCombination((EV_KEY, 1, 111))
        ev_2 = EventCombination((EV_KEY, 1, 222))
        ev_3 = EventCombination((EV_KEY, 2, 111))
        # only values between -99 and 99 are allowed as mapping for EV_ABS or EV_REL
        ev_4 = EventCombination((EV_ABS, 1, 99))

        # add the first mapping
        self.preset.add(get_key_mapping(ev_1, "keyboard", "a"))
        self.assertTrue(self.preset.has_unsaved_changes())
        self.assertEqual(len(self.preset), 1)

        # change ev_1 to ev_3 and change a to b
        mapping = self.preset.get_mapping(ev_1)
        mapping.event_combination = ev_3
        mapping.output_symbol = "b"
        self.assertIsNone(self.preset.get_mapping(ev_1))
        self.assertEqual(self.preset.get_mapping(ev_3),
                         get_key_mapping(ev_3, "keyboard", "b"))
        self.assertEqual(len(self.preset), 1)

        # add 4
        self.preset.add(get_key_mapping(ev_4, "keyboard", "c"))
        self.assertEqual(self.preset.get_mapping(ev_3),
                         get_key_mapping(ev_3, "keyboard", "b"))
        self.assertEqual(self.preset.get_mapping(ev_4),
                         get_key_mapping(ev_4, "keyboard", "c"))
        self.assertEqual(len(self.preset), 2)

        # change the preset of 4 to d
        mapping = self.preset.get_mapping(ev_4)
        mapping.output_symbol = "d"
        self.assertEqual(self.preset.get_mapping(ev_4),
                         get_key_mapping(ev_4, "keyboard", "d"))
        self.assertEqual(len(self.preset), 2)

        # try to change combination of 4 to 3
        mapping = self.preset.get_mapping(ev_4)
        with self.assertRaises(KeyError):
            mapping.event_combination = ev_3

        self.assertEqual(self.preset.get_mapping(ev_3),
                         get_key_mapping(ev_3, "keyboard", "b"))
        self.assertEqual(self.preset.get_mapping(ev_4),
                         get_key_mapping(ev_4, "keyboard", "d"))
        self.assertEqual(len(self.preset), 2)

    def test_avoids_redundant_saves(self):
        with patch.object(self.preset, "has_unsaved_changes", lambda: False):
            self.preset.path = get_preset_path("foo", "bar2")
            self.preset.add(get_key_mapping())
            self.preset.save()

        with open(get_preset_path("foo", "bar2"), "r") as f:
            content = f.read()

        self.assertFalse(content)

    def test_combinations(self):
        ev_1 = InputEvent.from_tuple((EV_KEY, 1, 111))
        ev_2 = InputEvent.from_tuple((EV_KEY, 1, 222))
        ev_3 = InputEvent.from_tuple((EV_KEY, 2, 111))
        ev_4 = InputEvent.from_tuple((EV_ABS, 1, 99))
        combi_1 = EventCombination(ev_1, ev_2, ev_3)
        combi_2 = EventCombination(ev_2, ev_1, ev_3)
        combi_3 = EventCombination(ev_1, ev_2, ev_4)

        self.preset.add(get_key_mapping(combi_1, "keyboard", "a"))
        self.assertEqual(self.preset.get_mapping(combi_1), get_key_mapping(combi_1, "keyboard", "a"))
        self.assertEqual(self.preset.get_mapping(combi_2), get_key_mapping(combi_1, "keyboard", "a"))
        # since combi_1 and combi_2 are equivalent, this raises an KeyError
        self.assertRaises(KeyError, self.preset.add, get_key_mapping(combi_2, "keyboard", "b"))
        self.assertEqual(self.preset.get_mapping(combi_1), get_key_mapping(combi_1, "keyboard", "a"))
        self.assertEqual(self.preset.get_mapping(combi_2), get_key_mapping(combi_1, "keyboard", "a"))

        self.preset.add(get_key_mapping(combi_3, "keyboard", "c"))
        self.assertEqual(self.preset.get_mapping(combi_1), get_key_mapping(combi_1, "keyboard", "a"))
        self.assertEqual(self.preset.get_mapping(combi_2), get_key_mapping(combi_1, "keyboard", "a"))
        self.assertEqual(self.preset.get_mapping(combi_3), get_key_mapping(combi_3, "keyboard", "c"))

        mapping = self.preset.get_mapping(combi_1)
        mapping.output_symbol = "c"
        with self.assertRaises(KeyError):
            mapping.event_combination = combi_3

        self.assertEqual(self.preset.get_mapping(combi_1), get_key_mapping(combi_1, "keyboard", "c"))
        self.assertEqual(self.preset.get_mapping(combi_2), get_key_mapping(combi_1, "keyboard", "c"))
        self.assertEqual(self.preset.get_mapping(combi_3), get_key_mapping(combi_3, "keyboard", "c"))

    def test_remove(self):
        # does nothing
        ev_1 = EventCombination((EV_KEY, 40, 1))
        ev_2 = EventCombination((EV_KEY, 30, 1))
        ev_3 = EventCombination((EV_KEY, 20, 1))
        ev_4 = EventCombination((EV_KEY, 10, 1))

        self.assertRaises(TypeError, self.preset.remove, (EV_KEY, 10, 1))
        self.preset.remove(ev_1)
        self.assertFalse(self.preset.has_unsaved_changes())
        self.assertEqual(len(self.preset), 0)

        self.preset.add(get_key_mapping(combination=ev_1))
        self.assertEqual(len(self.preset), 1)
        self.preset.remove(ev_1)
        self.assertEqual(len(self.preset), 0)

        self.preset.add(get_key_mapping(ev_4, "keyboard", "KEY_KP1"))
        self.assertTrue(self.preset.has_unsaved_changes())
        self.preset.add(get_key_mapping(ev_3, "keyboard", "KEY_KP2"))
        self.preset.add(get_key_mapping(ev_2, "keyboard", "KEY_KP3"))
        self.assertEqual(len(self.preset), 3)
        self.preset.remove(ev_3)
        self.assertEqual(len(self.preset), 2)
        self.assertEqual(self.preset.get_mapping(ev_4), get_key_mapping(ev_4, "keyboard", "KEY_KP1"))
        self.assertIsNone(self.preset.get_mapping(ev_3))
        self.assertEqual(self.preset.get_mapping(ev_2), get_key_mapping(ev_2, "keyboard", "KEY_KP3"))

    def test_empty(self):
        self.preset.add(get_key_mapping(EventCombination([EV_KEY, 10, 1]), "keyboard", "1"))
        self.preset.add(get_key_mapping(EventCombination([EV_KEY, 11, 1]), "keyboard", "2"))
        self.preset.add(get_key_mapping(EventCombination([EV_KEY, 12, 1]), "keyboard", "3"))
        self.assertEqual(len(self.preset), 3)
        self.preset.empty()
        self.assertEqual(len(self.preset), 0)

    def test_dangerously_mapped_btn_left(self):
        self.preset.add(get_key_mapping(EventCombination(InputEvent.btn_left()), "keyboard", "1"))
        self.assertTrue(self.preset.dangerously_mapped_btn_left())

        self.preset.add(get_key_mapping(EventCombination([EV_KEY, 41, 1]), "keyboard", "2"))
        self.assertTrue(self.preset.dangerously_mapped_btn_left())

        self.preset.add(get_key_mapping(EventCombination([EV_KEY, 42, 1]), "gamepad", "btn_left"))
        self.assertFalse(self.preset.dangerously_mapped_btn_left())

        mapping = self.preset.get_mapping(EventCombination([EV_KEY, 42, 1]))
        mapping.output_symbol = "BTN_Left"
        self.assertFalse(self.preset.dangerously_mapped_btn_left())

        mapping.target_uinput = "keyboard"
        mapping.output_symbol = "3"
        self.assertTrue(self.preset.dangerously_mapped_btn_left())


if __name__ == "__main__":
    unittest.main()
