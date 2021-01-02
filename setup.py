#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@hip70890b.de>
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


setup(
    name='key-mapper',
    version='0.5.0',
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
        # see development.md#files
        ('/usr/share/key-mapper/', glob.glob('data/*')),
        ('/usr/share/applications/', ['data/key-mapper.desktop']),
        ('/usr/share/polkit-1/actions/', ['data/key-mapper.policy']),
        ('/usr/lib/systemd/system', ['data/key-mapper.service']),
        ('/etc/dbus-1/system.d/', ['data/keymapper.Control.conf']),
        ('/etc/xdg/autostart/', ['data/key-mapper-autoload.desktop']),
        ('/usr/bin/', ['bin/key-mapper-gtk']),
        ('/usr/bin/', ['bin/key-mapper-gtk-pkexec']),
        ('/usr/bin/', ['bin/key-mapper-service']),
        ('/usr/bin/', ['bin/key-mapper-control']),
    ],
    install_requires=[
        'setuptools',
        'evdev',
        'pydbus'
    ],
)
