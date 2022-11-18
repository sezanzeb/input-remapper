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


from tests.test import tmp

import os
import unittest
import shutil
import time

from inputremapper.configs.preset import (
    find_newest_preset,
    rename_preset,
    get_any_preset,
    delete_preset,
    get_available_preset_name,
    get_presets,
)
from inputremapper.configs.paths import CONFIG_PATH, get_preset_path, touch
from inputremapper.gui.active_preset import active_preset


def create_preset(group_name, name="new preset"):
    name = get_available_preset_name(group_name, name)
    active_preset.empty()
    active_preset.save(get_preset_path(group_name, name))


PRESETS = os.path.join(CONFIG_PATH, "presets")


class TestPresets(unittest.TestCase):
    def test_get_available_preset_name(self):
        # no filename conflict
        self.assertEqual(get_available_preset_name("_", "qux 2"), "qux 2")

        touch(get_preset_path("_", "qux 5"))
        self.assertEqual(get_available_preset_name("_", "qux 5"), "qux 6")
        touch(get_preset_path("_", "qux"))
        self.assertEqual(get_available_preset_name("_", "qux"), "qux 2")
        touch(get_preset_path("_", "qux1"))
        self.assertEqual(get_available_preset_name("_", "qux1"), "qux1 2")
        touch(get_preset_path("_", "qux 2 3"))
        self.assertEqual(get_available_preset_name("_", "qux 2 3"), "qux 2 4")

        touch(get_preset_path("_", "qux 5"))
        self.assertEqual(get_available_preset_name("_", "qux 5", True), "qux 5 copy")
        touch(get_preset_path("_", "qux 5 copy"))
        self.assertEqual(get_available_preset_name("_", "qux 5", True), "qux 5 copy 2")
        touch(get_preset_path("_", "qux 5 copy 2"))
        self.assertEqual(get_available_preset_name("_", "qux 5", True), "qux 5 copy 3")

        touch(get_preset_path("_", "qux 5copy"))
        self.assertEqual(
            get_available_preset_name("_", "qux 5copy", True), "qux 5copy copy"
        )
        touch(get_preset_path("_", "qux 5copy 2"))
        self.assertEqual(
            get_available_preset_name("_", "qux 5copy 2", True), "qux 5copy 2 copy"
        )
        touch(get_preset_path("_", "qux 5copy 2 copy"))
        self.assertEqual(
            get_available_preset_name("_", "qux 5copy 2 copy", True),
            "qux 5copy 2 copy 2",
        )


class TestCreatePreset(unittest.TestCase):
    def tearDown(self):
        if os.path.exists(tmp):
            shutil.rmtree(tmp)

    def test_create_preset_1(self):
        self.assertEqual(get_any_preset(), ("Foo Device", None))
        create_preset("Foo Device")
        self.assertEqual(get_any_preset(), ("Foo Device", "new preset"))
        self.assertTrue(os.path.exists(f"{PRESETS}/Foo Device/new preset.json"))

    def test_create_preset_2(self):
        create_preset("Foo Device")
        create_preset("Foo Device")
        self.assertTrue(os.path.exists(f"{PRESETS}/Foo Device/new preset.json"))
        self.assertTrue(os.path.exists(f"{PRESETS}/Foo Device/new preset 2.json"))

    def test_create_preset_3(self):
        create_preset("Foo Device", "pre set")
        create_preset("Foo Device", "pre set")
        create_preset("Foo Device", "pre set")
        self.assertTrue(os.path.exists(f"{PRESETS}/Foo Device/pre set.json"))
        self.assertTrue(os.path.exists(f"{PRESETS}/Foo Device/pre set 2.json"))
        self.assertTrue(os.path.exists(f"{PRESETS}/Foo Device/pre set 3.json"))

    def test_create_preset_4(self):
        create_preset("Qux/Device?", "bla")
        self.assertTrue(os.path.exists(f"{PRESETS}/Qux_Device_/bla.json"))


class TestDeletePreset(unittest.TestCase):
    def tearDown(self):
        if os.path.exists(tmp):
            shutil.rmtree(tmp)

    def test_delete_preset(self):
        create_preset("Foo Device")
        create_preset("Foo Device")
        self.assertTrue(os.path.exists(f"{PRESETS}/Foo Device/new preset.json"))
        delete_preset("Foo Device", "new preset")
        self.assertFalse(os.path.exists(f"{PRESETS}/Foo Device/new preset.json"))
        self.assertTrue(os.path.exists(f"{PRESETS}/Foo Device"))
        delete_preset("Foo Device", "new preset 2")
        self.assertFalse(os.path.exists(f"{PRESETS}/Foo Device/new preset.json"))
        self.assertFalse(os.path.exists(f"{PRESETS}/Foo Device/new preset 2.json"))
        # if no preset in the directory, remove the directory
        self.assertFalse(os.path.exists(f"{PRESETS}/Foo Device"))

        create_preset("Qux/Device?", "bla")
        self.assertTrue(os.path.exists(f"{PRESETS}/Qux_Device_/bla.json"))
        delete_preset("Qux/Device?", "bla")
        self.assertFalse(os.path.exists(f"{PRESETS}/Qux_Device_/bla.json"))


class TestRenamePreset(unittest.TestCase):
    def tearDown(self):
        if os.path.exists(tmp):
            shutil.rmtree(tmp)

    def test_rename_preset(self):
        create_preset("Foo Device", "preset 1")
        create_preset("Foo Device", "preset 2")
        create_preset("Foo Device", "foobar")
        create_preset("Qux/Device?", "bla")

        rename_preset("Foo Device", "preset 1", "foobar")
        rename_preset("Foo Device", "preset 2", "foobar")
        rename_preset("Qux/Device?", "bla", "blubb")

        self.assertFalse(os.path.exists(f"{PRESETS}/Foo Device/preset 1.json"))
        self.assertTrue(os.path.exists(f"{PRESETS}/Foo Device/foobar.json"))
        self.assertTrue(os.path.exists(f"{PRESETS}/Foo Device/foobar 2.json"))
        self.assertTrue(os.path.exists(f"{PRESETS}/Foo Device/foobar 3.json"))
        self.assertFalse(os.path.exists(f"{PRESETS}/Qux_Device_/bla.json"))
        self.assertTrue(os.path.exists(f"{PRESETS}/Qux_Device_/blubb.json"))


class TestFindPresets(unittest.TestCase):
    def tearDown(self):
        if os.path.exists(tmp):
            shutil.rmtree(tmp)

    def test_get_presets(self):
        os.makedirs(os.path.join(PRESETS, "1234"))
        os.makedirs(f"{PRESETS}/Qux_Device_")
        os.mknod(f"{PRESETS}/Qux_Device_/blubb.json")
        self.assertEqual(len(get_presets("Qux/Device?")), 1)

        os.mknod(os.path.join(PRESETS, "1234", "picture.png"))
        self.assertEqual(len(get_presets("1234")), 0)

        os.mknod(os.path.join(PRESETS, "1234", "foo bar 1.json"))
        time.sleep(0.01)
        os.mknod(os.path.join(PRESETS, "1234", "foo bar 2.json"))
        # the newest to the front
        self.assertListEqual(get_presets("1234"), ["foo bar 2", "foo bar 1"])

    def test_find_newest_preset_1(self):
        create_preset("Foo Device", "preset 1")
        time.sleep(0.01)
        create_preset("Bar Device", "preset 2")

        # not a preset, ignore
        time.sleep(0.01)
        path = os.path.join(PRESETS, "Bar Device", "picture.png")
        os.mknod(path)

        self.assertEqual(find_newest_preset(), ("Bar Device", "preset 2"))

    def test_find_newest_preset_2(self):
        os.makedirs(f"{PRESETS}/Foo Device")
        time.sleep(0.01)
        os.makedirs(f"{PRESETS}/device_2")
        # takes the first one that the test-fake returns
        self.assertEqual(find_newest_preset(), ("Foo Device", None))

    def test_find_newest_preset_3(self):
        os.makedirs(f"{PRESETS}/Foo Device")
        self.assertEqual(find_newest_preset(), ("Foo Device", None))

    def test_find_newest_preset_4(self):
        create_preset("Foo Device", "preset 1")
        self.assertEqual(find_newest_preset(), ("Foo Device", "preset 1"))

    def test_find_newest_preset_5(self):
        create_preset("Foo Device", "preset 1")
        time.sleep(0.01)
        create_preset("unknown device 3", "preset 3")
        self.assertEqual(find_newest_preset(), ("Foo Device", "preset 1"))

    def test_find_newest_preset_6(self):
        # takes the first one that the test-fake returns
        self.assertEqual(find_newest_preset(), ("Foo Device", None))

    def test_find_newest_preset_7(self):
        self.assertEqual(find_newest_preset("Foo Device"), ("Foo Device", None))

    def test_find_newest_preset_8(self):
        create_preset("Foo Device", "preset 1")
        time.sleep(0.01)
        create_preset("Foo Device", "preset 3")
        time.sleep(0.01)
        create_preset("Bar Device", "preset 2")
        self.assertEqual(find_newest_preset("Foo Device"), ("Foo Device", "preset 3"))


if __name__ == "__main__":
    unittest.main()
