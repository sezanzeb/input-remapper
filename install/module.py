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

Dealing with varying sys.paths is frustrating. The sys.paths in /usr are not mirrored
in /usr/local consistently. Meson uses /usr/local/python3, which ubuntus python3 does
not import from. /usr/local is ignored by python within udev. Arch does not import
from /usr/local. When in doubt, do not install into /usr/local. I do not want to deal
with ModuleNotFoundErrors. I don't care if it should be in /usr/local by convention.
I don't know how much this varies across ubuntu versions and other debian based
distributions. I want the .deb to install reliably.

sys.path samples:
endeavouros  user: ['', '/usr/lib/python313.zip', '/usr/lib/python3.13', '/usr/lib/python3.13/lib-dynload', '/usr/lib/python3.13/site-packages']
endeavouros  root: ['', '/usr/lib/python313.zip', '/usr/lib/python3.13', '/usr/lib/python3.13/lib-dynload', '/usr/lib/python3.13/site-packages']
endeavouros  udev: ['/usr/bin', '/lib/python313.zip', '/lib/python3.13', '/lib/python3.13/lib-dynload', '/lib/python3.13/site-packages']
ubuntu 25.04 user: ['', '/usr/lib/python313.zip', '/usr/lib/python3.13', '/usr/lib/python3.13/lib-dynload', '/home/mango/.local/lib/python3.13/site-packages', '/usr/local/lib/python3.13/dist-packages', '/usr/lib/python3/dist-packages']
ubuntu 25.04 root: ['', '/usr/lib/python313.zip', '/usr/lib/python3.13', '/usr/lib/python3.13/lib-dynload', '/usr/local/lib/python3.13/dist-packages', '/usr/lib/python3/dist-packages']
ubuntu 25.04 udev: ['/usr/bin', '/lib/python313.zip', '/lib/python3.13', '/lib/python3.13/lib-dynload', '/lib/python3/dist-packages']
"""

import sys
import os
import subprocess
import shutil
import re
import tomllib

from install.data_files import DATA_DIR


def _key(path) -> int:
    favorability = 0

    # Good
    if re.match(r".*/lib/python3/.+-packages", path):
        # Independent of the installed python version, so it probably just continues
        # to be importable after a python version upgrade.
        favorability = 5
    elif re.match(r".*/lib/python3.+?/.+-packages", path):
        favorability = 4

    # Not meant for python code, but it probably works flawlessly
    elif re.match(r".*/lib/python3.+?/lib-dynload", path):
        favorability = 3

    # pip refuses to uninstall from standard-library directories once installed there
    elif re.match(r".*/lib/python3", path):
        favorability = 2
    elif re.match(r".*/lib/python3.+?", path):
        favorability = 1

    # udev does not import from /usr/local
    if path.startswith("/usr/local"):
        favorability -= 5

    if not os.path.exists(path):
        # If it doesn't exist yet, pip will apparently create it
        favorability -= 2
    elif not os.path.isdir(path):
        # If it exists but is not a dir, do not use it
        favorability -= 99

    return -favorability


def _get_packages_dir():
    """Where to install the input-remapper module to.

    For example "/usr/lib/python3.13
    """
    packages_dirs = sorted(sys.path, key=_key)
    packages_dir = packages_dirs[0]
    print(f'Picked "{packages_dir}" from {packages_dirs}')
    return packages_dir


def _get_commit_hash():
    git_call = subprocess.check_output(["git", "rev-parse", "HEAD"])
    commit = git_call.decode().strip()
    return commit


def _set_variables(target: str):
    path = os.path.join(target, "inputremapper", "installation_info.py")
    assert os.path.exists(path)

    with open(path, "r") as f:
        contents = f.read()

    with open("pyproject.toml", "rb") as f:
        version = tomllib.load(f)["project"]["version"]

    values = {
        "COMMIT_HASH": _get_commit_hash(),
        "VERSION": version,
        "DATA_DIR": f"/{DATA_DIR}",
    }

    print("Setting", values, "in", path)

    with open(path, "w") as f:
        for variable_name, value in values.items():
            contents = re.sub(
                rf"{variable_name}\s*=.+",
                f"{variable_name} = '{value}'",
                contents,
            )

        f.write(contents)


def build_input_remapper_module(root: str):
    # I'd use --prefix and --root, but
    # `pip install . --root ./build --prefix usr`
    # makes it end up in ./build/usr/local

    # if root is not /, then input-remapper is built into some other directory for the
    # purpose of merging it into / later. So regardless of root, we use the same
    # package_dir.
    package_dir = _get_packages_dir()
    if package_dir.startswith("/"):
        package_dir = package_dir[1:]

    target = os.path.join(root, package_dir)

    # Make sure we don't install input-remapper twice on that system into two different
    # paths, which commonly causes unexpected behavior. Also, we need to specifically
    # tell pip to replace an existing installation, or uninstall it beforehand.
    if root == "/":
        print("Uninstalling existing input-remapper installation")
        os.system("pip uninstall input-remapper --break-system-packages -y")

    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        ".",
        "--target",
        target,
        "--no-deps",
    ]

    print("Running", " ".join(command))

    # Fix the stdout ordering in github workflows
    sys.stdout.flush()

    subprocess.check_call(command)

    # pip puts its own leftovers into ./build that we don't need.
    # This only happens, when root is set to "build".
    if "build" in root:
        if os.path.exists("./build/lib/"):
            shutil.rmtree("./build/lib/")
        if os.path.exists("./build/bdist.linux-x86_64/"):
            shutil.rmtree("./build/bdist.linux-x86_64/")

    _set_variables(target)
