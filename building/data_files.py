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

"""Build input-remapper including its translations and system-files."""

import glob
import os
import re
import subprocess
from os.path import basename, splitext, join
import shutil
import sys


def make_lang():
    """Build po files into build/mo/."""
    lang_data = []
    os.makedirs("mo", exist_ok=True)
    for po_file in glob.glob("po/*.po"):
        lang = splitext(basename(po_file))[0]
        lang_data.append(
            (
                f"usr/share/input-remapper/lang/{lang}/LC_MESSAGES",
                [f"mo/{lang}/input-remapper.mo"],
            )
        )

        lang = splitext(basename(po_file))[0]
        os.makedirs(join("mo", lang), exist_ok=True)
        print(f"generating translation for {lang}")
        subprocess.run(
            [
                "msgfmt",
                "-o",
                join("mo", lang, "input-remapper.mo"),
                str(po_file),
            ],
            check=True,
        )

    return lang_data


def build_data_files():
    data_files = [
        # see development.md#files
        *make_lang(),
        ("usr/share/input-remapper/", glob.glob("data/*")),
        ("usr/share/applications/", ["data/input-remapper-gtk.desktop"]),
        (
            "usr/share/metainfo/",
            ["data/io.github.sezanzeb.input_remapper.metainfo.xml"],
        ),
        ("usr/share/icons/hicolor/scalable/apps/", ["data/input-remapper.svg"]),
        ("usr/share/polkit-1/actions/", ["data/input-remapper.policy"]),
        ("usr/lib/systemd/system", ["data/input-remapper.service"]),
        ("usr/share/dbus-1/system.d/", ["data/inputremapper.Control.conf"]),
        ("etc/xdg/autostart/", ["data/input-remapper-autoload.desktop"]),
        ("usr/lib/udev/rules.d", ["data/99-input-remapper.rules"]),
        ("usr/bin/", ["bin/input-remapper-gtk"]),
        ("usr/bin/", ["bin/input-remapper-service"]),
        ("usr/bin/", ["bin/input-remapper-control"]),
        ("usr/bin/", ["bin/input-remapper-reader-service"]),
    ]

    for target_dir, files in data_files:
        # We specify the root via argv instead. Argparse would ignore the first
        # arguments with a leading slash.
        assert not target_dir.startswith("/")
        for file_ in files:
            destination_dir = os.path.join("build", target_dir)
            print("Copying", file_, "to", destination_dir)
            os.makedirs(destination_dir, exist_ok=True)
            shutil.copy(file_, os.path.join(destination_dir, os.path.basename(file_)))

