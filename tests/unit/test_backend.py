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
from typing import List, Dict, Any

from inputremapper.gui.event_handler import EventHandler
from tests.test import quick_cleanup, get_backend


class Listener:
    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)


class TestBackend(unittest.TestCase):
    def setUp(self) -> None:
        self.event_handler = EventHandler()

    def tearDown(self) -> None:
        quick_cleanup()

    def test_should_provide_groups(self):
        backend = get_backend()
