#!/usr/bin/python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2023 sezanzeb <proxima@sezanzeb.de>
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


from tests.test import tmp, quick_cleanup

import os
import unittest
import json
from unittest.mock import patch

from evdev.ecodes import EV_KEY, EV_ABS, KEY_A
from inputremapper.input_event import InputEvent

from inputremapper.configs.preset import Preset
from inputremapper.configs.system_mapping import SystemMapping, XMODMAP_FILENAME
from inputremapper.configs.global_config import global_config
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


class TestMapping(unittest.TestCase):
    def setUp(self):
        self.preset = Preset()
        self.assertFalse(self.preset.has_unsaved_changes())

    def tearDown(self):
        quick_cleanup()

    def test_config(self):
        self.preset.save(get_preset_path("foo", "bar2"))

        self.assertEqual(self.preset.get("a"), None)

        self.assertFalse(self.preset.has_unsaved_changes())

        self.preset.set("a", 1)
        self.assertEqual(self.preset.get("a"), 1)
        self.assertTrue(self.preset.has_unsaved_changes())

        self.preset.remove("a")
        self.preset.set("a.b", 2)
        self.assertEqual(self.preset.get("a.b"), 2)
        self.assertEqual(self.preset._config["a"]["b"], 2)

        self.preset.remove("a.b")
        self.preset.set("a.b.c", 3)
        self.assertEqual(self.preset.get("a.b.c"), 3)
        self.assertEqual(self.preset._config["a"]["b"]["c"], 3)

        # setting preset.whatever does not overwrite the preset
        # after saving. It should be ignored.
        self.preset.change(EventCombination([EV_KEY, 81, 1]), "keyboard", " a ")
        self.preset.set("mapping.a", 2)
        self.assertEqual(self.preset.num_saved_keys, 0)
        self.preset.save(get_preset_path("foo", "bar"))
        self.assertEqual(self.preset.num_saved_keys, len(self.preset))
        self.assertFalse(self.preset.has_unsaved_changes())
        self.preset.load(get_preset_path("foo", "bar"))
        self.assertEqual(
            self.preset.get_mapping(EventCombination([EV_KEY, 81, 1])),
            ("a", "keyboard"),
        )
        self.assertIsNone(self.preset.get("mapping.a"))
        self.assertFalse(self.preset.has_unsaved_changes())

        # loading a different preset also removes the configs from memory
        self.preset.remove("a")
        self.assertTrue(self.preset.has_unsaved_changes())
        self.preset.set("a.b.c", 6)
        self.preset.load(get_preset_path("foo", "bar2"))
        self.assertIsNone(self.preset.get("a.b.c"))

    def test_fallback(self):
        global_config.set("d.e.f", 5)
        self.assertEqual(self.preset.get("d.e.f"), 5)
        self.preset.set("d.e.f", 3)
        self.assertEqual(self.preset.get("d.e.f"), 3)

    def test_save_load(self):
        one = InputEvent.from_tuple((EV_KEY, 10, 1))
        two = InputEvent.from_tuple((EV_KEY, 11, 1))
        three = InputEvent.from_tuple((EV_KEY, 12, 1))

        self.preset.change(EventCombination(one), "keyboard", "1")
        self.preset.change(EventCombination(two), "keyboard", "2")
        self.preset.change(EventCombination(two, three), "keyboard", "3")
        self.preset._config["foo"] = "bar"
        self.preset.save(get_preset_path("Foo Device", "test"))

        path = os.path.join(tmp, "presets", "Foo Device", "test.json")
        self.assertTrue(os.path.exists(path))

        loaded = Preset()
        self.assertEqual(len(loaded), 0)
        loaded.load(get_preset_path("Foo Device", "test"))

        self.assertEqual(len(loaded), 3)
        self.assertRaises(TypeError, loaded.get_mapping, one)
        self.assertEqual(loaded.get_mapping(EventCombination(one)), ("1", "keyboard"))
        self.assertEqual(loaded.get_mapping(EventCombination(two)), ("2", "keyboard"))
        self.assertEqual(
            loaded.get_mapping(EventCombination(two, three)), ("3", "keyboard")
        )
        self.assertEqual(loaded._config["foo"], "bar")

    def test_change(self):
        # the reader would not report values like 111 or 222, only 1 or -1.
        # the preset just does what it is told, so it accepts them.
        ev_1 = EventCombination((EV_KEY, 1, 111))
        ev_2 = EventCombination((EV_KEY, 1, 222))
        ev_3 = EventCombination((EV_KEY, 2, 111))
        ev_4 = EventCombination((EV_ABS, 1, 111))

        self.assertRaises(
            TypeError, self.preset.change, [(EV_KEY, 10, 1), "keyboard", "a", ev_2]
        )
        self.assertRaises(
            TypeError, self.preset.change, [ev_1, "keyboard", "a", (EV_KEY, 1, 222)]
        )

        # 1 is not assigned yet, ignore it
        self.preset.change(ev_1, "keyboard", "a", ev_2)
        self.assertTrue(self.preset.has_unsaved_changes())
        self.assertIsNone(self.preset.get_mapping(ev_2))
        self.assertEqual(self.preset.get_mapping(ev_1), ("a", "keyboard"))
        self.assertEqual(len(self.preset), 1)

        # change ev_1 to ev_3 and change a to b
        self.preset.change(ev_3, "keyboard", "b", ev_1)
        self.assertIsNone(self.preset.get_mapping(ev_1))
        self.assertEqual(self.preset.get_mapping(ev_3), ("b", "keyboard"))
        self.assertEqual(len(self.preset), 1)

        # add 4
        self.preset.change(ev_4, "keyboard", "c", None)
        self.assertEqual(self.preset.get_mapping(ev_3), ("b", "keyboard"))
        self.assertEqual(self.preset.get_mapping(ev_4), ("c", "keyboard"))
        self.assertEqual(len(self.preset), 2)

        # change the preset of 4 to d
        self.preset.change(ev_4, "keyboard", "d", None)
        self.assertEqual(self.preset.get_mapping(ev_4), ("d", "keyboard"))
        self.assertEqual(len(self.preset), 2)

        # this also works in the same way
        self.preset.change(ev_4, "keyboard", "e", ev_4)
        self.assertEqual(self.preset.get_mapping(ev_4), ("e", "keyboard"))
        self.assertEqual(len(self.preset), 2)

        self.assertEqual(self.preset.num_saved_keys, 0)

    def test_rejects_empty(self):
        key = EventCombination([EV_KEY, 1, 111])
        self.assertEqual(len(self.preset), 0)
        self.assertRaises(
            ValueError, lambda: self.preset.change(key, "keyboard", " \n ")
        )
        self.assertRaises(ValueError, lambda: self.preset.change(key, " \n ", "b"))
        self.assertEqual(len(self.preset), 0)

    def test_avoids_redundant_changes(self):
        # to avoid logs that don't add any value
        def clear(*_):
            # should not be called
            raise AssertionError

        key = EventCombination([EV_KEY, 987, 1])
        target = "keyboard"
        symbol = "foo"

        self.preset.change(key, target, symbol)
        with patch.object(self.preset, "clear", clear):
            self.preset.change(key, target, symbol)
            self.preset.change(key, target, symbol, previous_combination=key)

    def test_combinations(self):
        ev_1 = InputEvent.from_tuple((EV_KEY, 1, 111))
        ev_2 = InputEvent.from_tuple((EV_KEY, 1, 222))
        ev_3 = InputEvent.from_tuple((EV_KEY, 2, 111))
        ev_4 = InputEvent.from_tuple((EV_ABS, 1, 111))
        combi_1 = EventCombination(ev_1, ev_2, ev_3)
        combi_2 = EventCombination(ev_2, ev_1, ev_3)
        combi_3 = EventCombination(ev_1, ev_2, ev_4)

        self.preset.change(combi_1, "keyboard", "a")
        self.assertEqual(self.preset.get_mapping(combi_1), ("a", "keyboard"))
        self.assertEqual(self.preset.get_mapping(combi_2), ("a", "keyboard"))
        # since combi_1 and combi_2 are equivalent, a changes to b
        self.preset.change(combi_2, "keyboard", "b")
        self.assertEqual(self.preset.get_mapping(combi_1), ("b", "keyboard"))
        self.assertEqual(self.preset.get_mapping(combi_2), ("b", "keyboard"))

        self.preset.change(combi_3, "keyboard", "c")
        self.assertEqual(self.preset.get_mapping(combi_1), ("b", "keyboard"))
        self.assertEqual(self.preset.get_mapping(combi_2), ("b", "keyboard"))
        self.assertEqual(self.preset.get_mapping(combi_3), ("c", "keyboard"))

        self.preset.change(combi_3, "keyboard", "c", combi_1)
        self.assertIsNone(self.preset.get_mapping(combi_1))
        self.assertIsNone(self.preset.get_mapping(combi_2))
        self.assertEqual(self.preset.get_mapping(combi_3), ("c", "keyboard"))

    def test_clear(self):
        # does nothing
        ev_1 = EventCombination((EV_KEY, 40, 1))
        ev_2 = EventCombination((EV_KEY, 30, 1))
        ev_3 = EventCombination((EV_KEY, 20, 1))
        ev_4 = EventCombination((EV_KEY, 10, 1))

        self.assertRaises(TypeError, self.preset.clear, (EV_KEY, 10, 1))
        self.preset.clear(ev_1)
        self.assertFalse(self.preset.has_unsaved_changes())
        self.assertEqual(len(self.preset), 0)

        self.preset._mapping[ev_1] = "b"
        self.assertEqual(len(self.preset), 1)
        self.preset.clear(ev_1)
        self.assertEqual(len(self.preset), 0)
        self.assertTrue(self.preset.has_unsaved_changes())

        self.preset.change(ev_4, "keyboard", "KEY_KP1", None)
        self.assertTrue(self.preset.has_unsaved_changes())
        self.preset.change(ev_3, "keyboard", "KEY_KP2", None)
        self.preset.change(ev_2, "keyboard", "KEY_KP3", None)
        self.assertEqual(len(self.preset), 3)
        self.preset.clear(ev_3)
        self.assertEqual(len(self.preset), 2)
        self.assertEqual(self.preset.get_mapping(ev_4), ("KEY_KP1", "keyboard"))
        self.assertIsNone(self.preset.get_mapping(ev_3))
        self.assertEqual(self.preset.get_mapping(ev_2), ("KEY_KP3", "keyboard"))

    def test_empty(self):
        self.preset.change(EventCombination([EV_KEY, 10, 1]), "keyboard", "1")
        self.preset.change(EventCombination([EV_KEY, 11, 1]), "keyboard", "2")
        self.preset.change(EventCombination([EV_KEY, 12, 1]), "keyboard", "3")
        self.assertEqual(len(self.preset), 3)
        self.preset.empty()
        self.assertEqual(len(self.preset), 0)

    def test_dangerously_mapped_btn_left(self):
        self.preset.change(EventCombination(InputEvent.btn_left()), "keyboard", "1")
        self.assertTrue(self.preset.dangerously_mapped_btn_left())

        self.preset.change(EventCombination([EV_KEY, 41, 1]), "keyboard", "2")
        self.assertTrue(self.preset.dangerously_mapped_btn_left())

        self.preset.change(EventCombination([EV_KEY, 42, 1]), "gamepad", "btn_left")
        self.assertFalse(self.preset.dangerously_mapped_btn_left())

        self.preset.change(EventCombination([EV_KEY, 42, 1]), "gamepad", "BTN_Left")
        self.assertFalse(self.preset.dangerously_mapped_btn_left())

        self.preset.change(EventCombination([EV_KEY, 42, 1]), "keyboard", "3")
        self.assertTrue(self.preset.dangerously_mapped_btn_left())


if __name__ == "__main__":
    unittest.main()
