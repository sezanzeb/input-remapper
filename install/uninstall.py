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

"""Remove a system-wide input-remapper installation."""

import os
import sys
import shutil
import subprocess

from install.data_files import get_data_files


def uninstall() -> None:
    # remove data files
    for directory, files in get_data_files():
        for file_ in files:
            filename = os.path.basename(file_)
            path = os.path.join("/", directory, filename)

            # Removing files from system directories is risky. Low propability, very
            # high damage. To avoid accidentally removing system directories due to
            # a bug, assert that this is an input-remapper path.
            # If this happens, urgently create a new issue on github!
            assert "input" in path and "remapper" in path

            try:
                os.unlink(path)
                print("Removed", path)
            except FileNotFoundError:
                print(path, "not found")

    # language files are not in data_files
    data_path = "/usr/share/input-remapper/"
    try:
        shutil.rmtree(data_path)
        print("Removed", data_path)
    except FileNotFoundError:
        print(data_path, "not found")

    # remove pip module
    command = [
        sys.executable,
        "-m",
        "pip",
        "uninstall",
        "input-remapper",
        "--break-system-packages",
    ]
    print("Running", " ".join(command))
    # Fix the stdout ordering in github workflows
    sys.stdout.flush()
    subprocess.check_call(command)

    os.system("sudo systemctl stop input-remapper")
    os.system("sudo systemctl daemon-reload")


if __name__ == "__main__":
    uninstall()
