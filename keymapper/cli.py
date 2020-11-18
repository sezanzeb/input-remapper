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


def apply_symbols(device, name=None, keycodes=None):
    """Apply a symbols configuration to the device.

    Parameters
    ----------
    device : string
        A device, should be a key of get_devices
    name : string
        This is the name of the symbols to apply. For example "de",
        "key-mapper-empty" or "key-mapper-dev"
    keycodes : string
        This is the name of the keycodes file needed for that. If you don't
        provide the correct one, X will crash. For example "key-mapper",
        which is the "identity mapping", or "de"
    """
    if get_devices().get(device) is None:
        # maybe you should run refresh_devices
        logger.error('Tried to apply symbols on unknown device "%s"', device)
        return

    if name is None:
        name = get_system_layout_locale()

    logger.debug('Applying symbols "%s" to device "%s"', name, device)

    # sanity check one
    symbols_path = os.path.join('/usr/share/X11/xkb/symbols', name)
    if not os.path.exists(symbols_path):
        logger.error('Symbols file "%s" doesn\'t exist', symbols_path)
        return
    with open(symbols_path, 'r') as f:
        if f.read() == '':
            logger.error('Tried to load empty symbols %s', symbols_path)
            return

    if keycodes is not None:
        # sanity check two
        keycodes_path = os.path.join('/usr/share/X11/xkb/keycodes', keycodes)
        if not os.path.exists(keycodes_path):
            logger.error('keycodes "%s" don\'t exist', keycodes_path)
            return
        with open(keycodes_path, 'r') as f:
            if f.read() == '':
                logger.error('Found empty keycodes "%s"', keycodes_path)
                return

    cmd = ['setxkbmap', '-layout', name]
    if keycodes is not None:
        cmd += ['-keycodes', keycodes]

    # apply it to every device that hangs on the same usb port, because I
    # have no idea how to figure out which one of those 3 devices that are
    # all named after my mouse to use.
    group = get_devices()[device]
    for xinput_name, xinput_id in get_xinput_id_mapping():
        if xinput_name not in group['devices']:
            # only all virtual devices of the same hardware device
            continue

        device_cmd = cmd + ['-device', str(xinput_id)]
        logger.debug('Running `%s`', ' '.join(device_cmd))
        output = subprocess.run(device_cmd, capture_output=True)
        output = output.stderr.decode().strip()
        if output != '':
            logger.debug2(output)


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


def parse_xmodmap(mapping):
    """Read the output of xmodmap into a mapping."""
    xmodmap = subprocess.check_output(['xmodmap', '-pke']).decode() + '\n'
    mappings = re.findall(r'(\d+) = (.+)\n', xmodmap)
    # TODO is this tested?
    for keycode, characters in mappings:
        # this is the "array" format needed for symbols files
        character = ', '.join(characters.split())
        mapping.change(
            previous_keycode=None,
            new_keycode=int(keycode),
            character=character
        )
