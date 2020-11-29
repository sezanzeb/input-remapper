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


import glob
from setuptools import setup

with open('README.md', 'r') as f:
    long_description = f.read()

setup(
    name='key-mapper',
    version='0.1.0',
    description='A tool to change the mapping of your input device buttons',
    author='Sezanzeb',
    author_email='proxima@hip70890b.de',
    url='https://github.com/sezanzeb/key-mapper',
    license='GPL-3.0',
    packages=[
        'keymapper',
        'keymapper.dev',
        'keymapper.gtk'
    ],
    data_files=[
        ('share/key-mapper/', glob.glob('data/*')),
        ('share/applications/', ['data/key-mapper.desktop']),
        ('/etc/xdg/autostart/', ['data/key-mapper-service.desktop']),
    ],
    scripts=[
        'bin/key-mapper-gtk',
        'bin/key-mapper-service'
    ],
    long_description=long_description,
    long_description_content_type='text/markdown'
)
