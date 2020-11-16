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
  display server should be supported. Or does wayland use the same
  config files?

Resources:
[1] https://wiki.archlinux.org/index.php/Keyboard_input
[2] http://people.uleth.ca/~daniel.odonnell/Blog/custom-keyboard-in-linuxx11
[3] https://www.x.org/releases/X11R7.7/doc/xorg-docs/input/XKB-Enhancing.html
"""


import os
import re
import stat
import subprocess

from keymapper.paths import get_usr_path, KEYCODES_PATH, \
    USERS_SYMBOLS, DEFAULT_SYMBOLS, X11_SYMBOLS
from keymapper.logger import logger
from keymapper.data import get_data_path
from keymapper.linux import get_devices
from keymapper.mapping import custom_mapping, Mapping


def create_preset(device, name=None):
    """Create an empty preset and return the potentially incremented name.

    Automatically avoids file conflicts by adding a number to the name
    if needed.
    """
    if name is None:
        name = 'new preset'

    # find a name that is not already taken
    if os.path.exists(get_usr_path(device, name)):
        i = 2
        while os.path.exists(get_usr_path(device, f'{name} {i}')):
            i += 1
        name = f'{name} {i}'

    path = get_usr_path(device, name)
    if not os.path.exists(path):
        logger.info('Creating new file %s', path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        os.mknod(path)

    # add the same permissions as other symbol files, only root may write.
    os.chmod(path, stat.S_IREAD | stat.S_IWRITE | stat.S_IRGRP | stat.S_IROTH)

    """# give this file and the directories to the user
    # For now keep them with root to avoid doing too much unconventional
    # stuff.
    user = os.getlogin()
    for root, dirs, files in os.walk(USERS_SYMBOLS):
        shutil.chown(root, user, user)
        for file in files:
            shutil.chown(os.path.join(root, file), user, user)"""

    return name


def create_setxkbmap_config(device, preset):
    """Generate a config file for setxkbmap.

    The file is created in ~/.config/key-mapper/<device>/<preset> and,
    in order to find all presets in the home dir to make backing them up
    more intuitive, a symlink is created in
    /usr/share/X11/xkb/symbols/key-mapper/<device>/<preset> to point to it.
    The file in home doesn't have underscore to be more beautiful on the
    frontend, while the symlink doesn't contain any whitespaces.

    Parameters
    ----------
    device : string
    preset : string
    """
    if len(custom_mapping) == 0:
        logger.debug('Got empty mappings')
        return None

    create_identity_mapping()
    create_default_symbols()

    device_path = get_usr_path(device)
    if not os.path.exists(device_path):
        logger.info('Creating directory "%s"', device_path)
        os.makedirs(device_path, exist_ok=True)

    preset_path = get_usr_path(device, preset)
    if not os.path.exists(preset_path):
        logger.info('Creating config file "%s"', preset_path)
        os.mknod(preset_path)

    logger.info('Writing key mappings to %s', preset_path)
    with open(preset_path, 'w') as f:
        contents = generate_symbols(get_preset_name(device, preset))
        if contents is not None:
            f.write(contents)


def get_preset_name(device, preset=None):
    """Get the name for that preset that is used for the setxkbmap command."""
    # It's the relative path starting from X11/xkb/symbols and must not
    # contain spaces
    name = get_usr_path(device, preset)[len(X11_SYMBOLS) + 1:]
    assert ' ' not in name
    return name


DEFAULT_SYMBOLS_NAME = get_preset_name('default')


def apply_preset(device, preset):
    """Apply a preset to the device.

    Parameters
    ----------
    device : string
    preset : string
    """
    layout = get_preset_name(device, preset)
    setxkbmap(device, layout)


def get_system_layout():
    """Get the system wide configured default keyboard layout."""
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
        path = os.path.join(X11_SYMBOLS, layout)
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
        cmd = ['setxkbmap', '-layout', get_system_layout()]
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
        subprocess.run(device_cmd, capture_output=True)


def create_identity_mapping():
    """Because the concept of "reasonable symbolic names" [3] doesn't apply
    when mouse buttons are all over the place. Create an identity mapping
    to make generating "symbols" files easier. Keycode 10 -> "<10>"

    This has the added benefit that keycodes reported by xev can be
    identified in the symbols file.
    """
    if os.path.exists(KEYCODES_PATH):
        logger.debug('Found the keycodes file at %s', KEYCODES_PATH)
        return

    xkb_keycodes = []
    # the maximum specified in /usr/share/X11/xkb/keycodes is usually 255
    # and the minimum 8
    maximum = 255
    minimum = 8
    for keycode in range(minimum, maximum + 1):
        xkb_keycodes.append(f'<{keycode}> = {keycode};')

    template_path = get_data_path('xkb_keycodes_template')
    with open(template_path, 'r') as template_file:
        template = template_file.read()

    result = template.format(
        minimum=minimum,
        maximum=maximum,
        xkb_keycodes='\n    '.join(xkb_keycodes)
    )

    if not os.path.exists(KEYCODES_PATH):
        logger.debug('Creating "%s"', KEYCODES_PATH)
        os.makedirs(os.path.dirname(KEYCODES_PATH), exist_ok=True)
        os.mknod(KEYCODES_PATH)
    with open(KEYCODES_PATH, 'w') as keycodes:
        keycodes.write(result)


def generate_symbols(name, include=DEFAULT_SYMBOLS_NAME, mapping=custom_mapping):
    """Create config contents to be placed in /usr/share/X11/xkb/symbols.

    It's the mapping of the preset as expected by X. This function does not
    create the file.

    Parameters
    ----------
    name : string
        Usually what `get_preset_name` returns
    include : string or None
        If another preset should be included. Defaults to the default
        preset. Use None to avoid including.
    mapping : Mapping
        If you need to create a symbols file for some other mapping you can
        pass it to this parameter. By default the custom mapping will be
        used that is also displayed in the user interface.
    """
    if len(mapping) == 0:
        raise ValueError('Mapping is empty')

    # If the symbols file contains key codes that are not present in
    # the keycodes file, THE WHOLE X SESSION WILL CRASH!
    if not os.path.exists(KEYCODES_PATH):
        raise FileNotFoundError('Expected the keycodes file to exist')

    with open(KEYCODES_PATH, 'r') as f:
        keycodes = re.findall(r'<.+?>', f.read())

    xkb_symbols = []
    for keycode, character in mapping:
        if f'<{keycode}>' not in keycodes:
            logger.error(f'Unknown keycode <{keycode}> for "{character}"')
            # don't append that one, otherwise X would crash when loading
            continue
        xkb_symbols.append(f'key <{keycode}> {{ [ {character} ] }};')

    if len(xkb_symbols) == 0:
        logger.error('Failed to populate xkb_symbols')
        return None

    template_path = get_data_path('xkb_symbols_template')
    with open(template_path, 'r') as template_file:
        template = template_file.read()

    result = template.format(
        name=name,
        xkb_symbols='\n    '.join(xkb_symbols),
        include=f'include "{include}"' if include else ''
    )

    return result


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


def parse_symbols_file(device, preset):
    """Parse a symbols file populate the mapping.

    Existing mappings are overwritten if there are conflicts.
    """
    path = get_usr_path(device, preset)

    if not os.path.exists(path):
        logger.debug(
            'Tried to load non existing preset "%s" for %s',
            preset, device
        )
        custom_mapping.empty()
        custom_mapping.changed = False
        return

    with open(path, 'r') as f:
        # from "key <12> { [ 1 ] };" extract 12 and 1,
        # avoid lines that start with special characters
        # (might be comments)
        result = re.findall(r'\n\s+?key <(.+?)>.+?\[\s+(\w+)', f.read())
        logger.debug('Found %d mappings in this preset', len(result))
        for keycode, character in result:
            custom_mapping.change(None, int(keycode), character)
        custom_mapping.changed = False


def create_default_symbols():
    """Parse the output of xmodmap and create a default symbols file.

    Since xmodmap may print mappings that have already been modified by
    key-mapper, this should be done only once after the installation.

    This is needed because all our keycode aliases in the symbols files
    are "<int>", whereas the others are <AB01> and such, so they are not
    compatible.
    """
    if os.path.exists(DEFAULT_SYMBOLS):
        logger.debug('Found the default mapping at %s', DEFAULT_SYMBOLS)
        return

    xmodmap = subprocess.check_output(['xmodmap', '-pke']).decode() + '\n'
    mappings = re.findall(r'(\d+) = (.+)\n', xmodmap)
    defaults = Mapping()
    for keycode, characters in mappings:
        defaults.change(None, int(keycode), characters.split())

    contents = generate_symbols(DEFAULT_SYMBOLS_NAME, None, defaults)

    if not os.path.exists(DEFAULT_SYMBOLS):
        logger.info('Creating %s', DEFAULT_SYMBOLS)
        os.makedirs(os.path.dirname(DEFAULT_SYMBOLS), exist_ok=True)
        os.mknod(DEFAULT_SYMBOLS)

    with open(DEFAULT_SYMBOLS, 'w') as f:
        if contents is not None:
            logger.info('Updating default mappings')
            f.write(contents)
        else:
            logger.error('Failed to write default mappings')
