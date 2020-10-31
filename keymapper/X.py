#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2020 sezanzeb <proxima@hip70890b.de>
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


"""Stuff that interacts with the X Server"""


import re
import subprocess


# mapping of keycode to character, e.g. 38 to the 'A' key of the keyboard.
# This depends on the configured keyboard layout.
# example: 38: "a A a A ae AE ae"
key_mapping = {}


def load_keymapping():
    """Load the current active mapping of keycodes"""
    # to get ASCII codes: xmodmap -pk
    output = subprocess.check_output(['xmodmap', '-p']).decode()
    for line in output.split('\n'):
        search = re.search(r'(\d+) = (.+)', line)
        if search is not None:
            key_mapping[search[0]] = search[1]


def get_xinput_list(type):
    """Run xinput and get the result as list.

    Parameters
    ----------
    type : string
        Ine of 'id' or 'name'
    """
    output = subprocess.check_output(['xinput', 'list', f'--{type}-only'])
    return [line for line in output.decode().split('\n') if line != '']


def find_devices():
    """Get a list of (id, name) for each input device."""
    # `xinput list`
    ids = get_xinput_list('id')
    names = get_xinput_list('name')

    # names contains duplicates and "Virtual"-somethings, filter those
    known_names = []
    # TODO remember all IDS? try each one of them for setxkbmap until success?
    result = []
    for (id, name) in zip(ids, names):
        if name not in known_names and not name.startswith('Virtual'):
            known_names.append(name)
            result.append((id, name))
    return result
