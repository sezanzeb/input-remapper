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


"""Stuff that interacts with the X Server

Resources:
https://wiki.archlinux.org/index.php/Keyboard_input
http://people.uleth.ca/~daniel.odonnell/Blog/custom-keyboard-in-linuxx11
"""


import re
import subprocess

from keymapper.logger import logger


# mapping of key to character
# This depends on the configured keyboard layout.
# example: AC01: "a A a A ae AE ae".
key_mapping = {}


def load_keymapping():
    """Load the current active mapping of keycodes"""
    # to get ASCII codes: xmodmap -pk
    output = subprocess.check_output(['xmodmap', '-p']).decode()
    for line in output.split('\n'):
        search = re.search(r'(\d+) = (.+)', line)
        if search is not None:
            key_mapping[search[0]] = search[1]


def parse_libinput_list():
    """Get a mapping of {name: [paths]} for `libinput list-devices` devices.

    This is grouped by group, so the "Logitech USB Keyboard" and
    "Logitech USB Keyboard Consumer Control" are one key (the shorter one),
    and the paths array for that is therefore 2 entries large.
    """
    stdout = subprocess.check_output(['libinput', 'list-devices'])
    devices = [
        device for device in stdout.decode().split('\n\n')
        if device != ''
    ]

    grouped = {}
    for device in devices:
        info = {}
        for line in device.split('\n'):
            # example:
            # "Kernel:           /dev/input/event0"
            match = re.match(r'(\w+):\s+(.+)', line)
            if match is None:
                continue
            info[match[1]] = match[2]

        name = info['Device']
        group = info['Group']  # int
        dev = info['Kernel']  # /dev/input/event#

        if grouped.get(group) is None:
            grouped[group] = []
        grouped[group].append((name, dev))

    result = {}
    for i in grouped:
        group = grouped[i]
        names = [entry[0] for entry in group]
        devs = [entry[1] for entry in group]
        shortest_name = sorted(names, key=len)[0]
        result[shortest_name] = devs

    return result


def parse_evtest():
    """Get a mapping of {name: [paths]} for each evtest device.

    evtest is quite slow.

    This is grouped by name, so "Logitech USB Keyboard" and
    "Logitech USB Keyboard Consumer Control" are two keys in result. Some
    devices have the same name for each of those entries.

    Use parse_libinput_list instead, which properly groups all of them.
    """
    # It asks for a device afterwads, so just insert garbage into it
    p = subprocess.Popen(
        'echo a | sudo evtest',
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    # the list we are looking for is in stderr
    _, evtest = p.communicate()
    evtest = [
        line
        for line in evtest.decode().split('\n')
        if line.startswith('/dev')
    ]
    logger.debug('evtest devices: \n%s', '\n'.join(evtest))

    # evtest also returns a bunch of other devices, like some audio devices,
    # so check this list against `xinput list` to get keyboards and mice
    xinput = get_xinput_list()
    logger.debug('xinput devices: \n%s', '\n'.join(xinput))

    result = {}
    for line in evtest:
        match = re.search(r'(/dev/input/event\d+):\s+(.+)', line)
        if match is None:
            continue

        # the path refers to a file in /dev/input/event#. Note, that this is
        # different from the id that `xinput list` can return.
        path = match[1]
        name = match[2]
        if name not in xinput:
            continue

        if not result.get(name):
            result[name] = []
        result[name].append(path)
    return result


def find_devices():
    """Return a mapping of {name: [paths]} for each input device."""
    result = parse_libinput_list()
    logger.info('Found %s', ', '.join([f'"{name}"' for name in result]))
    return result


def get_xinput_list():
    """Run xinput and get the resulting device names as list."""
    xinput = subprocess.check_output(['xinput', 'list', f'--name-only'])
    return [line for line in xinput.decode().split('\n') if line != '']
