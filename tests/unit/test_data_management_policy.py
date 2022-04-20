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
import unittest

if False:

    class TestGuiPolicy(unittest.TestCase):
        def test_loads_group_after_delete_preset(self):
            """when the current preset was deleted the group should be reloaded"""
            raise NotImplementedError

        def test_loads_group_after_rename_preset(self):
            """when the current preset was renamed the group should be reloaded"""
            raise NotImplementedError

        def test_loads_group_after_preset_added(self):
            """when a preset was added the group should be reloaded"""
            raise NotImplementedError

        def test_loads_preset_when_group_loaded(self):
            """when a group was loaded, the newest preset of that group
            should be loaded as well"""
            raise NotImplementedError

        def test_create_empty_preset_when_group_loaded(self):
            """when a group without presets was loaded an empty preset should be created"""
            raise NotImplementedError

        def test_loads_preset_when_mapping_added(self):
            raise NotImplementedError

        def test_loads_preset_when_mapping_deleted(self):
            raise NotImplementedError

        def test_loads_mapping_when_preset_loaded(self):
            """when a preset was loaded, a mapping should be loaded as well"""
            raise NotImplementedError
