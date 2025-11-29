#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2025 sezanzeb <b8x45ygc9@mozmail.com>
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

"""Figure out where the python module needs to be placed in order to reliable import it.

Dealing with varying sys.paths is frustrating. The paths in /usr and /usr/local are
inconsistently listed in sys.path. meson uses /usr/local/python3, which ubuntus python3
does not import from. /usr/local is ignored in arch and by udev. When in doubt, do not
install into /usr/local. I do not want to deal with ModuleNotFoundErrors. I don't care
if it should be in /usr/local by convention. I don't know how much this varies across
ubuntu versions and other debian based distributions. I want my .deb to install
reliably.

Samples:
endeavouros  user: ['', '/usr/lib/python313.zip', '/usr/lib/python3.13', '/usr/lib/python3.13/lib-dynload', '/usr/lib/python3.13/site-packages']
endeavouros  root: ['', '/usr/lib/python313.zip', '/usr/lib/python3.13', '/usr/lib/python3.13/lib-dynload', '/usr/lib/python3.13/site-packages']
ubuntu 25.04 user: ['', '/usr/lib/python313.zip', '/usr/lib/python3.13', '/usr/lib/python3.13/lib-dynload', '/home/mango/.local/lib/python3.13/site-packages', '/usr/local/lib/python3.13/dist-packages', '/usr/lib/python3/dist-packages']
ubuntu 25.04 root: ['', '/usr/lib/python313.zip', '/usr/lib/python3.13', '/usr/lib/python3.13/lib-dynload', '/usr/local/lib/python3.13/dist-packages', '/usr/lib/python3/dist-packages']

Getting input-remapper to reliably install is torture. And meson does not help.
"""

import sys
import os
import subprocess
import shutil


def _key(path) -> int:
    # sorted from desired to undesired

    if path.startswith('/usr/lib/python3/') or path == '/usr/lib/python3':
        # Paths that work independent of the python version, yes please
        return -1

    if path.startswith('/usr/local'):
        return 1

    if not path.startswith('/usr'):
        # Editable package paths, not system-wide, user installations which don't work
        # for input-remapper.
        return 2

    if not os.path.isdir(path):
        return 3

    return 0


def _get_packages_dir():
    """Where to install the input-remapper module to.

    For example "/usr/lib/python3.13
    """
    packages_dir = sorted(sys.path, key=_key)[0]
    return packages_dir


def _get_commit_hash():
    git_call = subprocess.check_output(['git', 'rev-parse', 'HEAD'])
    commit = git_call.decode().strip()
    return commit


def _fill_templates(target: str):
    path = os.path.join(target, 'inputremapper', 'installation_info.py')
    print("Writing", path)
    assert os.path.exists(path)
    with open(path, 'w') as f:
        lines = [
            f"COMMIT_HASH = '{_get_commit_hash()}'",
            "VERSION = '2.2.0'",
            "DATA_DIR = '/usr/share/inputremapper'",
        ]

        f.write('\n'.join(lines))


def build_input_remapper_module():
    # I'd use --prefix and --root, but
    # `pip install . --root ./build --prefix usr`
    # makes it end up in ./build/usr/local

    # get_packages_dir is an absolute path, so os.path.join can't be used.
    target = f"./build{_get_packages_dir()}"
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            ".",
            "--target",
            target,
            "--no-deps"
        ]
    )

    # pip puts its own leftovers into ./build that we don't need.'
    shutil.rmtree('./build/lib/')

    _fill_templates(target)
