#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2020 sezanzeb <proxima@hip70890b.de>
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


"""Patch stuff to get reproducible tests."""


from unittest.mock import patch


fake_config_path = '/tmp/keymapper-test-config'


class UseFakes:
    """Provides fake functionality for alsaaudio and some services."""
    def __init__(self):
        self.patches = []

    def patch(self):
        """Replace the functions with various fakes."""
        # self.patches.append(patch.object(keymapper, 'foo', self.foo))
        for p in self.patches:
            p.__enter__()

    def restore(self):
        """Restore functionality."""
        for p in self.patches:
            p.__exit__(None, None, None)
        self.patches = []
