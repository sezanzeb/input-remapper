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


PO_FILES = "po/*.po"


class Install(install):
    """Add the commit hash and build .mo translations."""

    def run(self):
        try:
            commit = os.popen("git rev-parse HEAD").read().strip()
            if re.match(r"^([a-z]|[0-9])+$", commit):
                # for whatever reason different systems have different paths here
                build_dir = ""
                if os.path.exists("build/lib/keymapper"):
                    build_dir = "build/lib/"
                with open(f"{build_dir}keymapper/commit_hash.py", "w+") as f:
                    f.write(f"COMMIT_HASH = '{commit}'\n")
        except Exception as e:
            print("Failed to save the commit hash:", e)

        # generate .mo files
        make_lang()

        install.run(self)


def get_packages(base="keymapper"):
    """Return all modules used in key-mapper.

    For example 'keymapper.gui' or 'keymapper.injection.consumers'
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
            ["msgfmt", "-o", join("mo", lang, "key-mapper.mo"), str(po_file)],
            check=True,
        )


lang_data = []
for po_file in glob.glob(PO_FILES):
    lang = splitext(basename(po_file))[0]
    lang_data.append(
        (f"/usr/share/key-mapper/lang/{lang}/LC_MESSAGES", [f"mo/{lang}/key-mapper.mo"])
    )


setup(
    name="key-mapper",
    version="1.2.2",
    description="A tool to change the mapping of your input device buttons",
    author="Sezanzeb",
    author_email="proxima@sezanzeb.de",
    url="https://github.com/sezanzeb/key-mapper",
    license="GPL-3.0",
    packages=get_packages(),
    include_package_data=True,
    data_files=[
        # see development.md#files
        *lang_data,
        ("/usr/share/key-mapper/", glob.glob("data/*")),
        ("/usr/share/applications/", ["data/key-mapper.desktop"]),
        ("/usr/share/polkit-1/actions/", ["data/key-mapper.policy"]),
        ("/usr/lib/systemd/system", ["data/key-mapper.service"]),
        ("/etc/dbus-1/system.d/", ["data/keymapper.Control.conf"]),
        ("/etc/xdg/autostart/", ["data/key-mapper-autoload.desktop"]),
        ("/usr/lib/udev/rules.d", ["data/99-key-mapper.rules"]),
        ("/usr/bin/", ["bin/key-mapper-gtk"]),
        ("/usr/bin/", ["bin/key-mapper-service"]),
        ("/usr/bin/", ["bin/key-mapper-control"]),
        ("/usr/bin/", ["bin/key-mapper-helper"]),
    ],
    install_requires=[
        "setuptools",
        "evdev",
        "pydbus",
        "pygobject",
    ],
    cmdclass={
        "install": Install,
    },
)
