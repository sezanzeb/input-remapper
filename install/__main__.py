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

"""Build input-remapper including its translations and system-files.

pip, in many cases, fails to install data files, which need to go into system paths,
and instead puts them (despite them being absolute paths) into
/usr/lib/python3/inputremapper/usr/share/...

python3 setup.py install is deprecated

meson fails to install the module into a path that can actually be imported, and
its python features require one to specify each individual file of the module.

So instead, input-remapper uses a custom python solution. Hopefulls this works well
enough to prevent all ModuleNotFoundErrors in the future.
"""

import shutil
import os
import sys

from install.check_dependencies import check_dependencies
from install.data_files import build_data_files
from install.module import build_input_remapper_module
from install.language import make_lang

import argparse


def parse_args():
    parser = argparse.ArgumentParser(description="Tool to install input-remapper with.")
    parser.add_argument(
        "--root",
        type=str,
        help=(
            "Where to install input-remapper to. For example ./build to prepare a "
            "package archive or for debugging, or / to install it to the system."
        ),
        required=True,
    )
    args = parser.parse_args()
    return args


def ask(msg):
    answer = ""
    while answer not in ["y", "n"]:
        answer = input(f"{msg} [y/n] ").lower()
    return answer == "y"


def main():
    args = parse_args()

    if os.path.exists(args.root) and not args.root.startswith("/"):
        delete = ask(f"{args.root} already exists. Delete?")
        if delete:
            shutil.rmtree(args.root)
        else:
            sys.exit(3)

    check_dependencies()
    print()
    build_data_files(args.root)
    print()
    make_lang(args.root)
    print()
    build_input_remapper_module(args.root)


if __name__ == "__main__":
    main()
