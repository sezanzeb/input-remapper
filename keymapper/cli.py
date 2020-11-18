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


"""Parsing and running CLI tools."""


import os
import re
import subprocess

from keymapper.logger import logger, is_debug
from keymapper.getdevices import get_devices
from keymapper.mapping import system_mapping


def get_system_layout_locale():
    """Get the system wide configured default keyboard layout locale."""
    localectl = subprocess.check_output(
        ['localectl', 'status']
    ).decode().split('\n')
    # example:
    # System Locale: LANG=en_GB.UTF-8
    # VC Keymap: tmp
    # X11 Layout: de
    # X11 Model: pc105
    return [
        line for line in localectl
        if 'X11 Layout' in line
    ][0].split(': ')[-1]


def setxkbmap(device, layout):
    """Apply a preset to the device.

    Parameters
    ----------
    device : string
    layout : string or None
        For example 'de', passed to setxkbmap unmodified. If None, will
        load the system default
    """
    if layout is not None:
        path = os.path.join('/usr/share/X11/xkb/symbols', layout)
        if not os.path.exists(path):
            logger.error('Symbols %s don\'t exist', path)
            return
        with open(path, 'r') as f:
            if f.read() == '':
                logger.error('Tried to load empty symbols %s', path)
                return

    logger.info('Applying layout "%s" on device %s', layout, device)
    group = get_devices()[device]

    if layout is None:
        cmd = ['setxkbmap', '-layout', get_system_layout_locale()]
    else:
        cmd = ['setxkbmap', '-layout', layout, '-keycodes', 'key-mapper']

    # apply it to every device that hangs on the same usb port, because I
    # have no idea how to figure out which one of those 3 devices that are
    # all named after my mouse to use.
    for xinput_name, xinput_id in get_xinput_id_mapping():
        if xinput_name not in group['devices']:
            # only all virtual devices of the same hardware device
            continue

        device_cmd = cmd + ['-device', str(xinput_id)]
        logger.debug('Running `%s`', ' '.join(device_cmd))
        subprocess.run(device_cmd, capture_output=(not is_debug()))


def apply_empty_symbols(device):
    """Make the device not write any character anymore."""
    logger.debug('Applying the empty symbols to %s', device)
    group = get_devices()[device]

    cmd = ['setxkbmap', '-layout', 'key-mapper/empty']

    # apply it to every device that hangs on the same usb port, because I
    # have no idea how to figure out which one of those 3 devices that are
    # all named after my mouse to use.
    for xinput_name, xinput_id in get_xinput_id_mapping():
        if xinput_name not in group['devices']:
            # only all virtual devices of the same hardware device
            continue

        device_cmd = cmd + ['-device', str(xinput_id)]
        logger.debug('Running `%s`', ' '.join(device_cmd))
        subprocess.run(device_cmd, capture_output=(not is_debug()))


def get_xinput_id_mapping():
    """Run xinput and get a list of name, id tuplies.

    The ids are needed for setxkbmap. There might be duplicate names with
    different ids.
    """
    names = subprocess.check_output(
        ['xinput', 'list', '--name-only']
    ).decode().split('\n')
    ids = subprocess.check_output(
        ['xinput', 'list', '--id-only']
    ).decode().split('\n')

    names = [name for name in names if name != '']
    ids = [int(id) for id in ids if id != '']
    return zip(names, ids)


def parse_xmodmap():
    """Read the output of xmodmap as a Mapping object."""
    xmodmap = subprocess.check_output(['xmodmap', '-pke']).decode() + '\n'
    mappings = re.findall(r'(\d+) = (.+)\n', xmodmap)
    # TODO is this tested?
    for keycode, characters in mappings:
        system_mapping.change(
            previous_keycode=None,
            new_keycode=int(keycode),
            character=characters.split()
        )


# TODO verify that this is the system default and not changed when I
#  setxkbmap my mouse
parse_xmodmap()
