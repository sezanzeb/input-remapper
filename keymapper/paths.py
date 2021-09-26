#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@sezanzeb.de>
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

from keymapper.logger import logger
from keymapper.user import USER, CONFIG_PATH


def chown(path):
    """Set the owner of a path to the user."""
    try:
        shutil.chown(path, user=USER, group=USER)
    except LookupError:
        # the users group was unknown in one case for whatever reason
        shutil.chown(path, user=USER)


def touch(path, log=True):
    """Create an empty file and all its parent dirs, give it to the user."""
    if path.endswith("/"):
        raise ValueError(f"Expected path to not end with a slash: {path}")

    if os.path.exists(path):
        return

    if log:
        logger.info('Creating file "%s"', path)

    mkdir(os.path.dirname(path), log=False)

    os.mknod(path)
    chown(path)


def mkdir(path, log=True):
    """Create a folder, give it to the user."""
    if path == "" or path is None:
        return

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


def remove(path):
    """Remove whatever is at the path"""
    if not os.path.exists(path):
        return

    if os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.remove(path)


def get_preset_path(group_name=None, preset=None):
    """Get a path to the stored preset, or to store a preset to."""
    presets_base = os.path.join(CONFIG_PATH, "presets")

    if group_name is None:
        return presets_base

    if preset is not None:
        # the extension of the preset should not be shown in the ui.
        # if a .json extension arrives this place, it has not been
        # stripped away properly prior to this.
        assert not preset.endswith(".json")
        preset = f"{preset}.json"

    if preset is None:
        return os.path.join(presets_base, group_name)

    return os.path.join(presets_base, group_name, preset)


def get_config_path(*paths):
    """Get a path in ~/.config/key-mapper/"""
    return os.path.join(CONFIG_PATH, *paths)
