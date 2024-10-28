#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2024 sezanzeb <b8x45ygc9@mozmail.com>
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

from __future__ import annotations

from tests.lib.fixtures import fixtures
from tests.lib.pipes import setup_pipe, close_pipe


def create_fixture_pipes():
    # make sure those pipes exist before any process (the reader-service) gets forked,
    # so that events can be pushed after the fork.
    for _fixture in fixtures:
        setup_pipe(_fixture)


def remove_fixture_pipes():
    for _fixture in fixtures:
        close_pipe(_fixture)
