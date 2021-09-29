#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@sezanzeb.de>
#
# This file is part of key-mapper.
#
# key-mapper is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# key-mapper is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with key-mapper.  If not, see <https://www.gnu.org/licenses/>.


import os
import unittest
import json

from evdev.ecodes import EV_KEY, EV_ABS, ABS_HAT0X, KEY_A

from keymapper.mapping import Mapping, split_key
from keymapper.system_mapping import SystemMapping, XMODMAP_FILENAME
from keymapper.config import config
from keymapper.paths import get_preset_path
from keymapper.key import Key

from tests.test import tmp, quick_cleanup


class TestSystemMapping(unittest.TestCase):
    def tearDown(self):
        quick_cleanup()

    def test_split_key(self):
        self.assertEqual(split_key("1,2,3"), (1, 2, 3))
        self.assertEqual(split_key("1,2"), (1, 2, 1))
        self.assertIsNone(split_key("1"))
        self.assertIsNone(split_key("1,a,2"))
        self.assertIsNone(split_key("1,a"))

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
        self.mapping = Mapping()
        self.assertFalse(self.mapping.changed)

    def tearDown(self):
        quick_cleanup()

    def test_config(self):
        self.mapping.save(get_preset_path("foo", "bar2"))

        self.assertEqual(self.mapping.get("a"), None)

        self.assertFalse(self.mapping.changed)

        self.mapping.set("a", 1)
        self.assertEqual(self.mapping.get("a"), 1)
        self.assertTrue(self.mapping.changed)

        self.mapping.remove("a")
        self.mapping.set("a.b", 2)
        self.assertEqual(self.mapping.get("a.b"), 2)
        self.assertEqual(self.mapping._config["a"]["b"], 2)

        self.mapping.remove("a.b")
        self.mapping.set("a.b.c", 3)
        self.assertEqual(self.mapping.get("a.b.c"), 3)
        self.assertEqual(self.mapping._config["a"]["b"]["c"], 3)

        # setting mapping.whatever does not overwrite the mapping
        # after saving. It should be ignored.
        self.mapping.change(Key(EV_KEY, 81, 1), " a ")
        self.mapping.set("mapping.a", 2)
        self.assertEqual(self.mapping.num_saved_keys, 0)
        self.mapping.save(get_preset_path("foo", "bar"))
        self.assertEqual(self.mapping.num_saved_keys, len(self.mapping))
        self.assertFalse(self.mapping.changed)
        self.mapping.load(get_preset_path("foo", "bar"))
        self.assertEqual(self.mapping.get_symbol(Key(EV_KEY, 81, 1)), "a")
        self.assertIsNone(self.mapping.get("mapping.a"))
        self.assertFalse(self.mapping.changed)

        # loading a different preset also removes the configs from memory
        self.mapping.remove("a")
        self.assertTrue(self.mapping.changed)
        self.mapping.set("a.b.c", 6)
        self.mapping.load(get_preset_path("foo", "bar2"))
        self.assertIsNone(self.mapping.get("a.b.c"))

    def test_fallback(self):
        config.set("d.e.f", 5)
        self.assertEqual(self.mapping.get("d.e.f"), 5)
        self.mapping.set("d.e.f", 3)
        self.assertEqual(self.mapping.get("d.e.f"), 3)

    def test_clone(self):
        ev_1 = Key(EV_KEY, 1, 1)
        ev_2 = Key(EV_KEY, 2, 0)

        mapping1 = Mapping()
        mapping1.change(ev_1, " a")
        mapping2 = mapping1.clone()
        mapping1.change(ev_2, "b ")

        self.assertEqual(mapping1.get_symbol(ev_1), "a")
        self.assertEqual(mapping1.get_symbol(ev_2), "b")

        self.assertEqual(mapping2.get_symbol(ev_1), "a")
        self.assertIsNone(mapping2.get_symbol(ev_2))

        self.assertIsNone(mapping2.get_symbol(Key(EV_KEY, 2, 3)))
        self.assertIsNone(mapping2.get_symbol(Key(EV_KEY, 1, 3)))

    def test_save_load(self):
        one = Key(EV_KEY, 10, 1)
        two = Key(EV_KEY, 11, 1)
        three = Key(EV_KEY, 12, 1)

        self.mapping.change(one, "1")
        self.mapping.change(two, "2")
        self.mapping.change(Key(two, three), "3")
        self.mapping._config["foo"] = "bar"
        self.mapping.save(get_preset_path("Foo Device", "test"))

        path = os.path.join(tmp, "presets", "Foo Device", "test.json")
        self.assertTrue(os.path.exists(path))

        loaded = Mapping()
        self.assertEqual(len(loaded), 0)
        loaded.load(get_preset_path("Foo Device", "test"))

        self.assertEqual(len(loaded), 3)
        self.assertEqual(loaded.get_symbol(one), "1")
        self.assertEqual(loaded.get_symbol(two), "2")
        self.assertEqual(loaded.get_symbol(Key(two, three)), "3")
        self.assertEqual(loaded._config["foo"], "bar")

    def test_save_load_2(self):
        # loads mappings with only (type, code) as the key by using 1 as value,
        # loads combinations chained with +
        path = os.path.join(tmp, "presets", "Foo Device", "test.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as file:
            json.dump(
                {
                    "mapping": {
                        f"{EV_KEY},3": "a",
                        f"{EV_ABS},{ABS_HAT0X},-1": "b",
                        f"{EV_ABS},1,1+{EV_ABS},2,-1+{EV_ABS},3,1": "c",
                        # ignored because broken
                        f"3,1,1,2": "e",
                        f"3": "e",
                        f",,+3,1,2": "g",
                        f"": "h",
                    }
                },
                file,
            )

        loaded = Mapping()
        self.assertEqual(loaded.num_saved_keys, 0)
        loaded.load(get_preset_path("Foo Device", "test"))
        self.assertEqual(len(loaded), 3)
        self.assertEqual(loaded.num_saved_keys, 3)
        self.assertEqual(loaded.get_symbol(Key(EV_KEY, 3, 1)), "a")
        self.assertEqual(loaded.get_symbol(Key(EV_ABS, ABS_HAT0X, -1)), "b")
        self.assertEqual(
            loaded.get_symbol(Key((EV_ABS, 1, 1), (EV_ABS, 2, -1), Key(EV_ABS, 3, 1))),
            "c",
        )

    def test_change(self):
        # the reader would not report values like 111 or 222, only 1 or -1.
        # the mapping just does what it is told, so it accepts them.
        ev_1 = Key(EV_KEY, 1, 111)
        ev_2 = Key(EV_KEY, 1, 222)
        ev_3 = Key(EV_KEY, 2, 111)
        ev_4 = Key(EV_ABS, 1, 111)

        # 1 is not assigned yet, ignore it
        self.mapping.change(ev_1, "a", ev_2)
        self.assertTrue(self.mapping.changed)
        self.assertIsNone(self.mapping.get_symbol(ev_2))
        self.assertEqual(self.mapping.get_symbol(ev_1), "a")
        self.assertEqual(len(self.mapping), 1)

        # change ev_1 to ev_3 and change a to b
        self.mapping.change(ev_3, "b", ev_1)
        self.assertIsNone(self.mapping.get_symbol(ev_1))
        self.assertEqual(self.mapping.get_symbol(ev_3), "b")
        self.assertEqual(len(self.mapping), 1)

        # add 4
        self.mapping.change(ev_4, "c", None)
        self.assertEqual(self.mapping.get_symbol(ev_3), "b")
        self.assertEqual(self.mapping.get_symbol(ev_4), "c")
        self.assertEqual(len(self.mapping), 2)

        # change the mapping of 4 to d
        self.mapping.change(ev_4, "d", None)
        self.assertEqual(self.mapping.get_symbol(ev_4), "d")
        self.assertEqual(len(self.mapping), 2)

        # this also works in the same way
        self.mapping.change(ev_4, "e", ev_4)
        self.assertEqual(self.mapping.get_symbol(ev_4), "e")
        self.assertEqual(len(self.mapping), 2)

        self.assertEqual(self.mapping.num_saved_keys, 0)

    def test_combinations(self):
        ev_1 = Key(EV_KEY, 1, 111)
        ev_2 = Key(EV_KEY, 1, 222)
        ev_3 = Key(EV_KEY, 2, 111)
        ev_4 = Key(EV_ABS, 1, 111)
        combi_1 = Key(ev_1, ev_2, ev_3)
        combi_2 = Key(ev_2, ev_1, ev_3)
        combi_3 = Key(ev_1, ev_2, ev_4)

        self.mapping.change(combi_1, "a")
        self.assertEqual(self.mapping.get_symbol(combi_1), "a")
        self.assertEqual(self.mapping.get_symbol(combi_2), "a")
        # since combi_1 and combi_2 are equivalent, a changes to b
        self.mapping.change(combi_2, "b")
        self.assertEqual(self.mapping.get_symbol(combi_1), "b")
        self.assertEqual(self.mapping.get_symbol(combi_2), "b")

        self.mapping.change(combi_3, "c")
        self.assertEqual(self.mapping.get_symbol(combi_1), "b")
        self.assertEqual(self.mapping.get_symbol(combi_2), "b")
        self.assertEqual(self.mapping.get_symbol(combi_3), "c")

        self.mapping.change(combi_3, "c", combi_1)
        self.assertIsNone(self.mapping.get_symbol(combi_1))
        self.assertIsNone(self.mapping.get_symbol(combi_2))
        self.assertEqual(self.mapping.get_symbol(combi_3), "c")

    def test_clear(self):
        # does nothing
        ev_1 = Key(EV_KEY, 40, 1)
        ev_2 = Key(EV_KEY, 30, 1)
        ev_3 = Key(EV_KEY, 20, 1)
        ev_4 = Key(EV_KEY, 10, 1)

        self.mapping.clear(ev_1)
        self.assertFalse(self.mapping.changed)
        self.assertEqual(len(self.mapping), 0)

        self.mapping._mapping[ev_1] = "b"
        self.assertEqual(len(self.mapping), 1)
        self.mapping.clear(ev_1)
        self.assertEqual(len(self.mapping), 0)
        self.assertTrue(self.mapping.changed)

        self.mapping.change(ev_4, "KEY_KP1", None)
        self.assertTrue(self.mapping.changed)
        self.mapping.change(ev_3, "KEY_KP2", None)
        self.mapping.change(ev_2, "KEY_KP3", None)
        self.assertEqual(len(self.mapping), 3)
        self.mapping.clear(ev_3)
        self.assertEqual(len(self.mapping), 2)
        self.assertEqual(self.mapping.get_symbol(ev_4), "KEY_KP1")
        self.assertIsNone(self.mapping.get_symbol(ev_3))
        self.assertEqual(self.mapping.get_symbol(ev_2), "KEY_KP3")

    def test_empty(self):
        self.mapping.change(Key(EV_KEY, 10, 1), "1")
        self.mapping.change(Key(EV_KEY, 11, 1), "2")
        self.mapping.change(Key(EV_KEY, 12, 1), "3")
        self.assertEqual(len(self.mapping), 3)
        self.mapping.empty()
        self.assertEqual(len(self.mapping), 0)

    def test_dangerously_mapped_btn_left(self):
        self.mapping.change(Key.btn_left(), "1")
        self.assertTrue(self.mapping.dangerously_mapped_btn_left())

        self.mapping.change(Key(EV_KEY, 41, 1), "2")
        self.assertTrue(self.mapping.dangerously_mapped_btn_left())

        self.mapping.change(Key(EV_KEY, 42, 1), "btn_left")
        self.assertFalse(self.mapping.dangerously_mapped_btn_left())

        self.mapping.change(Key(EV_KEY, 42, 1), "BTN_Left")
        self.assertFalse(self.mapping.dangerously_mapped_btn_left())

        self.mapping.change(Key(EV_KEY, 42, 1), "3")
        self.assertTrue(self.mapping.dangerously_mapped_btn_left())


if __name__ == "__main__":
    unittest.main()
