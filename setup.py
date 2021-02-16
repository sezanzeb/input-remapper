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
import os
import re
from setuptools import setup
from setuptools.command.install import install


class Install(install):
    """Add the current commit hash to logger.py."""
    def run(self):
        commit = os.popen('git rev-parse HEAD').read().strip()
        if re.match(r'^([a-z]|[0-9])+$', commit):
            with open('keymapper/logger.py', 'r') as f:
                contents = f.read()
                contents = re.sub(
                    r"COMMIT_HASH = '.*?'",
                    f"COMMIT_HASH = '{commit}'",
                    contents
                )

            with open('keymapper/logger.py', 'w') as f:
                f.write(contents)

        install.run(self)


setup(
    name='key-mapper',
    version='0.6.1',
    description='A tool to change the mapping of your input device buttons',
    author='Sezanzeb',
    author_email='proxima@hip70890b.de',
    url='https://github.com/sezanzeb/key-mapper',
    license='GPL-3.0',
    packages=[
        'keymapper',
        'keymapper.gui',
        'keymapper.injection'
    ],
    data_files=[
        # see development.md#files
        ('/usr/share/key-mapper/', glob.glob('data/*')),
        ('/usr/share/applications/', ['data/key-mapper.desktop']),
        ('/usr/share/polkit-1/actions/', ['data/key-mapper.policy']),
        ('/usr/lib/systemd/system', ['data/key-mapper.service']),
        ('/etc/dbus-1/system.d/', ['data/keymapper.Control.conf']),
        ('/etc/xdg/autostart/', ['data/key-mapper-autoload.desktop']),
        ('/etc/udev/rules.d', ['data/key-mapper.rules']),
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
    cmdclass={
        'install': Install,
    },
)
