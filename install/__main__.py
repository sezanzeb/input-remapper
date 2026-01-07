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
from enum import Enum

from install.check_dependencies import check_dependencies
from install.data_files import build_data_files
from install.module import build_input_remapper_module
from install.language import make_lang

import argparse


class Components(str, Enum):
    data_files = "data_files"
    python_module = "python_module"


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
    parser.add_argument(
        "--components",
        type=str, nargs='+',
        help=(
            f'A list of components to install. Default: --components '
            f'{Components.python_module.value} {Components.data_files.value}'
        ),
        default=[Components.python_module, Components.data_files],
        metavar="COMPONENT"
    )
    args = parser.parse_args()
    return args


def ask(msg) -> bool:
    answer = ""
    while answer not in ["y", "n"]:
        answer = input(f"{msg} [y/n] ").lower()
    return answer == "y"


def print_headline(message: str) -> None:
    print(f"\033[7m{message}\033[0m")


def main() -> None:
    args = parse_args()

    if os.path.exists(args.root) and not args.root.startswith("/"):
        delete = ask(f"{args.root} already exists. Delete?")
        if delete:
            shutil.rmtree(args.root)
        else:
            sys.exit(3)

    for component in args.components:
        if component not in [Components.data_files, Components.python_module]:
            raise ValueError(f"Unknown component {component}")

    if Components.data_files in args.components:
        print_headline(f'Installing component "{Components.data_files.value}"')
        build_data_files(args.root)
        make_lang(args.root)

    if Components.python_module in args.components:
        print_headline(f'Installing component "{Components.python_module.value}"')
        check_dependencies()
        build_input_remapper_module(args.root)


if __name__ == "__main__":
    main()
