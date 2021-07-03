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


import glob
import os
import re
import subprocess
from os.path import basename, splitext, join
from setuptools import setup
from setuptools.command.install import install


PO_FILES = 'po/*.po'


class Install(install):
    """Add the commit hash and build .mo translations."""
    def run(self):
        commit = os.popen('git rev-parse HEAD').read().strip()
        if re.match(r'^([a-z]|[0-9])+$', commit):
            with open('keymapper/commit_hash.py', 'w') as f:
                f.write(f"COMMIT_HASH = '{commit}'\n")

        # generate .mo files
        make_lang()

        install.run(self)


def get_packages():
    """Return all modules used in key-mapper.

    For example 'keymapper.gui'.
    """
    result = ['keymapper']
    for name in os.listdir('keymapper'):
        if not os.path.isdir(f'keymapper/{name}'):
            continue

        if name == '__pycache__':
            continue

        result.append(f'keymapper.{name}')

    return result


def make_lang():
    """Build po files into mo/."""
    os.makedirs('mo', exist_ok=True)
    for po_file in glob.glob(PO_FILES):
        lang = splitext(basename(po_file))[0]
        os.makedirs(join('mo', lang), exist_ok=True)
        print(f'generating translation for {lang}')
        subprocess.run(['msgfmt', '-o', join('mo', lang, 'key-mapper.mo'), str(po_file)], check=True)


lang_data = []
for po_file in glob.glob(PO_FILES):
    lang = splitext(basename(po_file))[0]
    lang_data.append((
        f'/usr/share/key-mapper/lang/{lang}/LC_MESSAGES',
        [f'mo/{lang}/key-mapper.mo']
    ))


setup(
    name='key-mapper',
    version='1.0.0',
    description='A tool to change the mapping of your input device buttons',
    author='Sezanzeb',
    author_email='proxima@sezanzeb.de',
    url='https://github.com/sezanzeb/key-mapper',
    license='GPL-3.0',
    packages=get_packages(),
    include_package_data=True,
    data_files=[
        # see development.md#files
        *lang_data,
        ('/usr/share/key-mapper/', glob.glob('data/*')),
        ('/usr/share/applications/', ['data/key-mapper.desktop']),
        ('/usr/share/polkit-1/actions/', ['data/key-mapper.policy']),
        ('/usr/lib/systemd/system', ['data/key-mapper.service']),
        ('/etc/dbus-1/system.d/', ['data/keymapper.Control.conf']),
        ('/etc/xdg/autostart/', ['data/key-mapper-autoload.desktop']),
        ('/usr/lib/udev/rules.d', ['data/key-mapper.rules']),
        ('/usr/bin/', ['bin/key-mapper-gtk']),
        ('/usr/bin/', ['bin/key-mapper-service']),
        ('/usr/bin/', ['bin/key-mapper-control']),
        ('/usr/bin/', ['bin/key-mapper-helper']),
    ],
    install_requires=[
        'setuptools',
        'evdev',
        'pydbus',
        'pygobject',
    ],
    cmdclass={
        'install': Install,
    },
)
