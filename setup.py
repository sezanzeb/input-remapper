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


import DistUtilsExtra.auto


DistUtilsExtra.auto.setup(
    name='key-mapper',
    version='0.1.0',
    description='GUI for device specific keyboard mappings',
    license='GPL-3.0',
    data_files=[
        ('share/applications/', ['data/key-mapper.desktop']),
        ('share/key-mapper/', ['data/xkb_symbols_template']),
    ],
)
