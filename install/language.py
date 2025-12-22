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

"""Build language files and copy them to the target."""

import glob
import os
import subprocess
from os.path import basename, splitext, join, dirname


def make_lang(root: str) -> None:
    """Build po files as mo files into the expected directory."""
    os.makedirs("mo", exist_ok=True)
    for po_file in glob.glob("po/*.po"):
        lang = splitext(basename(po_file))[0]
        target = join(
            root,
            "usr",
            "share",
            "input-remapper",
            "lang",
            lang,
            "LC_MESSAGES",
            "input-remapper.mo",
        )
        os.makedirs(dirname(target), exist_ok=True)
        print(f"Generating translation {target}")
        subprocess.run(
            [
                "msgfmt",
                "-o",
                target,
                str(po_file),
            ],
            check=True,
        )
