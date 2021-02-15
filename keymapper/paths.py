#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@hip70890b.de>
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


"""Path constants to be used."""


import os
import shutil
import getpass
import pwd

from keymapper.logger import logger


def get_user():
    """Try to find the user who called sudo/pkexec."""
    try:
        return os.getlogin()
    except OSError:
        # failed in some ubuntu installations and in systemd services
        pass

    try:
        user = os.environ['USER']
    except KeyError:
        # possibly the systemd service. no sudo was used
        return getpass.getuser()

    if user == 'root':
        try:
            return os.environ['SUDO_USER']
        except KeyError:
            # no sudo was used
            pass

        try:
            pkexec_uid = int(os.environ['PKEXEC_UID'])
            return pwd.getpwuid(pkexec_uid).pw_name
        except KeyError:
            # no pkexec was used or the uid is unknown
            pass

    return user


USER = get_user()

CONFIG_PATH = os.path.join('/home', USER, '.config/key-mapper')


def chown(path):
    """Set the owner of a path to the user."""
    try:
        shutil.chown(path, user=USER, group=USER)
    except LookupError:
        # the users group was unknown in one case for whatever reason
        shutil.chown(path, user=USER)


def touch(path, log=True):
    """Create an empty file and all its parent dirs, give it to the user."""
    if path.endswith('/'):
        raise ValueError(f'Expected path to not end with a slash: {path}')

    if os.path.exists(path):
        return

    if log:
        logger.info('Creating file "%s"', path)

    mkdir(os.path.dirname(path), log=False)

    os.mknod(path)
    chown(path)


def mkdir(path, log=True):
    """Create a folder, give it to the user."""
    if os.path.exists(path):
        return

    if log:
        logger.info('Creating dir "%s"', path)

    # give all newly created folders to the user.
    # e.g. if .config/key-mapper/mouse/ is created the latter two
    base = os.path.split(path)[0]
    mkdir(base, log=False)

    os.makedirs(path)
    chown(path)


def get_preset_path(device=None, preset=None):
    """Get a path to the stored preset, or to store a preset to."""
    presets_base = os.path.join(CONFIG_PATH, 'presets')

    if device is None:
        return presets_base

    if preset is not None:
        # the extension of the preset should not be shown in the ui.
        # if a .json extension arrives this place, it has not been
        # stripped away properly prior to this.
        assert not preset.endswith('.json')
        preset = f'{preset}.json'

    if preset is None:
        return os.path.join(presets_base, device)

    return os.path.join(presets_base, device, preset)


def get_config_path(*paths):
    """Get a path in ~/.config/key-mapper/"""
    return os.path.join(CONFIG_PATH, *paths)
