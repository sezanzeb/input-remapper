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


def find_devices():
    """Return a mapping of {name: [ids]} for each input device.

    Evtest listing is really slow, query this only once when the
    program starts.
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

    devices = {}
    # there may be multiple entries per device in /dev, because one handles
    # movement while the other handles extra buttons. Remember all of the
    # device ids, so that the input mapping can be applied to all matching
    # ids, one of them is going to be the right one.
    for line in evtest:
        match = re.search(r'event(\d+):\s+(.+)', line)
        if match is None:
            continue

        # the id refers to a file in /dev/input, it is different from
        # the id that `xinput list` can return.
        id = match[1]
        name = match[2]

        if name not in xinput:
            continue

        # there can be
        # 'Logitech USB Keyboard' and
        # 'Logitech USB Keyboard Consumer Control'
        if not devices.get(name):
            devices[name] = []
        devices[name].append(id)

    logger.info('Devices: %s', ', '.join(list(devices.keys())))

    return devices


def get_xinput_list():
    """Run xinput and get the result as list."""
    xinput = subprocess.check_output(['xinput', 'list', f'--name-only'])
    return [line for line in xinput.decode().split('\n') if line != '']
