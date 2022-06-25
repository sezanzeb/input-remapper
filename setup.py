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


import glob
import os
import re
import subprocess
from os.path import basename, splitext, join
from setuptools import setup
from setuptools.command.install import install


PO_FILES = "po/*.po"


class Install(install):
    """Add the commit hash and build .mo translations."""

    def run(self):
        try:
            commit = os.popen("git rev-parse HEAD").read().strip()
            if re.match(r"^([a-z]|[0-9])+$", commit):
                # for whatever reason different systems have different paths here
                build_dir = ""
                if os.path.exists("build/lib/inputremapper"):
                    build_dir = "build/lib/"
                with open(f"{build_dir}inputremapper/commit_hash.py", "w+") as f:
                    f.write(f"COMMIT_HASH = '{commit}'\n")
        except Exception as e:
            print("Failed to save the commit hash:", e)

        # generate .mo files
        make_lang()

        install.run(self)


def get_packages(base="inputremapper"):
    """Return all modules used in input-remapper.

    For example 'inputremapper.gui' or 'inputremapper.injection.mapping_handlers'
    """
    if not os.path.exists(os.path.join(base, "__init__.py")):
        # only python modules
        return []

    result = [base.replace("/", ".")]
    for name in os.listdir(base):
        if not os.path.isdir(os.path.join(base, name)):
            continue

        if name == "__pycache__":
            continue

        # find more python submodules in that directory
        result += get_packages(os.path.join(base, name))

    return result


def make_lang():
    """Build po files into mo/."""
    os.makedirs("mo", exist_ok=True)
    for po_file in glob.glob(PO_FILES):
        lang = splitext(basename(po_file))[0]
        os.makedirs(join("mo", lang), exist_ok=True)
        print(f"generating translation for {lang}")
        subprocess.run(
            ["msgfmt", "-o", join("mo", lang, "input-remapper.mo"), str(po_file)],
            check=True,
        )


lang_data = []
for po_file in glob.glob(PO_FILES):
    lang = splitext(basename(po_file))[0]
    lang_data.append(
        (
            f"/usr/share/input-remapper/lang/{lang}/LC_MESSAGES",
            [f"mo/{lang}/input-remapper.mo"],
        )
    )


setup(
    name="input-remapper",
    version="1.6.0-beta",
    description="A tool to change the mapping of your input device buttons",
    author="Sezanzeb",
    author_email="proxima@sezanzeb.de",
    url="https://github.com/sezanzeb/input-remapper",
    license="GPL-3.0",
    packages=get_packages(),
    include_package_data=True,
    data_files=[
        # see development.md#files
        *lang_data,
        ("/usr/share/input-remapper/", glob.glob("data/*")),
        ("/usr/share/applications/", ["data/input-remapper.desktop"]),
        ("/usr/share/polkit-1/actions/", ["data/input-remapper.policy"]),
        ("/usr/lib/systemd/system", ["data/input-remapper.service"]),
        ("/etc/dbus-1/system.d/", ["data/inputremapper.Control.conf"]),
        ("/etc/xdg/autostart/", ["data/input-remapper-autoload.desktop"]),
        ("/usr/lib/udev/rules.d", ["data/99-input-remapper.rules"]),
        ("/usr/bin/", ["bin/input-remapper-gtk"]),
        ("/usr/bin/", ["bin/input-remapper-service"]),
        ("/usr/bin/", ["bin/input-remapper-control"]),
        ("/usr/bin/", ["bin/input-remapper-helper"]),
        # those will be deleted at some point:
        ("/usr/bin/", ["bin/key-mapper-gtk"]),
        ("/usr/bin/", ["bin/key-mapper-service"]),
        ("/usr/bin/", ["bin/key-mapper-control"]),
    ],
    install_requires=["setuptools", "evdev", "pydbus", "pygobject", "pydantic"],
    cmdclass={
        "install": Install,
    },
)
