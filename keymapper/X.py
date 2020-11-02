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


"""Stuff that interacts with the X Server, be it commands or config files.

TODO create a base class to standardize the interface if a different
  display server should be supported.

Resources:
[1] https://wiki.archlinux.org/index.php/Keyboard_input
[2] http://people.uleth.ca/~daniel.odonnell/Blog/custom-keyboard-in-linuxx11
[3] https://www.x.org/releases/X11R7.7/doc/xorg-docs/input/XKB-Enhancing.html
"""


import os
import re
import subprocess

from keymapper.paths import CONFIG_PATH, SYMBOLS_PATH
from keymapper.logger import logger


def get_keycode(device, letter):
    """Get the keycode that is configured for the given letter."""
    # TODO I have no idea how to do this
    # in /usr/share/X11/xkb/keycodes the mapping is made
    return ''


def generate_setxkbmap_config(device, preset, mappings):
    """Generate a config file for setxkbmap.

    The file is created in ~/.config/key-mapper/<device>/<preset> and,
    in order to find all presets in the home dir to make backing them up
    more intuitive, a symlink is created in
    /usr/share/X11/xkb/symbols/key-mapper/<device>/<preset> to point to it.
    The file in home doesn't have underscore to be more beautiful on the
    frontend, while the symlink doesn't contain any whitespaces.
    """
    config_path = os.path.join(CONFIG_PATH, device, preset)
    # setxkbmap cannot handle spaces
    usr_path = os.path.join(SYMBOLS_PATH, device, preset).replace(' ', '_')

    if not os.path.exists(config_path):
        logger.info('Creating config file "%s"', config_path)
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        os.mknod(config_path)
    if not os.path.exists(usr_path):
        logger.info('Creating symlink in "%s"', usr_path)
        os.makedirs(os.path.dirname(usr_path), exist_ok=True)
        os.symlink(config_path, usr_path)

    with open(config_path, 'w') as f:
        f.write(generate_symbols_file_content(device, preset, mappings))


def generate_symbols_file_content(device, preset, mappings):
    """Create config contents to be placed in /usr/share/X11/xkb/symbols."""
    system_default = 'us'  # TODO get the system default
    # TODO I think I also have to create a file in /usr/share/X11/xkb/keycodes
    result = '\n'.join([
        'default xkb_symbols "basic" {',
        '    minimum = 8;',
        '    maximum = 255;',
        f'    include "{system_default}"',
        f'    name[Group1]="{device}/{preset}";',
        '    key <AE01> { [ 2, 2, 2, 2 ] };',
        '};',
    ]) + '\n'
    for mapping in mappings:
        key = mapping.key
        keycode = get_keycode(device, key)
        target = mapping.target
        # TODO support NUM block keys and modifiers somehow

    return result


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


def get_xinput_list():
    """Run xinput and get the resulting device names as list."""
    xinput = subprocess.check_output(['xinput', 'list', f'--name-only'])
    return [line for line in xinput.decode().split('\n') if line != '']


_devices = None


def find_devices():
    """Return a mapping of {name: [paths]} for each input device."""
    global _devices
    # this is expensive, do it only once
    if _devices is None:
        _devices = parse_libinput_list()
        logger.info('Found %s', ', '.join([f'"{name}"' for name in _devices]))
    return _devices
