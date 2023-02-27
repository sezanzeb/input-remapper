# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2023 sezanzeb <proxima@sezanzeb.de>
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

# TODO: convert everything to use pathlib.Path

"""Path constants to be used."""


import os
import shutil
from typing import List, Union, Optional

from inputremapper.logger import logger, VERSION
from inputremapper.user import USER, HOME

rel_path = ".config/input-remapper-2"

CONFIG_PATH = os.path.join(HOME, rel_path)


def chown(path):
    """Set the owner of a path to the user."""
    try:
        shutil.chown(path, user=USER, group=USER)
    except LookupError:
        # the users group was unknown in one case for whatever reason
        shutil.chown(path, user=USER)


def touch(path: os.PathLike, log=True):
    """Create an empty file and all its parent dirs, give it to the user."""
    if str(path).endswith("/"):
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
    # e.g. if .config/input-remapper/mouse/ is created the latter two
    base = os.path.split(path)[0]
    mkdir(base, log=False)

    os.makedirs(path)
    chown(path)


def split_all(path: Union[os.PathLike, str]) -> List[str]:
    """Split the path into its segments."""
    parts = []
    while True:
        path, tail = os.path.split(path)
        parts.append(tail)
        if path == os.path.sep:
            # we arrived at the root '/'
            parts.append(path)
            break
        if not path:
            # arrived at start of relative path
            break

    parts.reverse()
    return parts


def remove(path):
    """Remove whatever is at the path."""
    if not os.path.exists(path):
        return

    if os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.remove(path)


def sanitize_path_component(group_name: str) -> str:
    """Replace characters listed in
    https://en.wikipedia.org/wiki/Filename#Reserved_characters_and_words
    with an underscore.
    """
    for character in '/\\?%*:|"<>':
        if character in group_name:
            group_name = group_name.replace(character, "_")
    return group_name


def get_preset_path(group_name: Optional[str] = None, preset: Optional[str] = None):
    """Get a path to the stored preset, or to store a preset to."""
    presets_base = os.path.join(CONFIG_PATH, "presets")

    if group_name is None:
        return presets_base

    group_name = sanitize_path_component(group_name)

    if preset is not None:
        # the extension of the preset should not be shown in the ui.
        # if a .json extension arrives this place, it has not been
        # stripped away properly prior to this.
        if not preset.endswith(".json"):
            preset = f"{preset}.json"

    if preset is None:
        return os.path.join(presets_base, group_name)

    return os.path.join(presets_base, group_name, preset)


def get_config_path(*paths):
    """Get a path in ~/.config/input-remapper/."""
    return os.path.join(CONFIG_PATH, *paths)
