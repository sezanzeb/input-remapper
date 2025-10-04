# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2025 sezanzeb <b8x45ygc9@mozmail.com>
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

from inputremapper.logging.logger import logger
from inputremapper.user import UserUtils


# TODO maybe this could become, idk, ConfigService and PresetService
class PathUtils:
    rel_path = ".config/input-remapper-2"

    @staticmethod
    def config_path() -> str:
        # TODO when proper DI is being done, construct PathUtils and configure it in
        #  the constructor. Then there is no need to recompute the config_path
        #  each time. Tests might have overwritten UserUtils.home.
        return os.path.join(UserUtils.home, PathUtils.rel_path)

    @staticmethod
    def chown(path: str) -> None:
        """Set the owner of a path to the user."""
        try:
            logger.debug('Chown "%s", "%s"', path, UserUtils.user)
            shutil.chown(path, user=UserUtils.user, group=UserUtils.user)
        except LookupError:
            # the users group was unknown in one case for whatever reason
            shutil.chown(path, user=UserUtils.user)

    @staticmethod
    def touch(path: Union[str, os.PathLike], log=True) -> None:
        """Create an empty file and all its parent dirs, give it to the user."""
        if str(path).endswith("/"):
            raise ValueError(f"Expected path to not end with a slash: {path}")

        if os.path.exists(path):
            return

        if log:
            logger.info('Creating file "%s"', path)

        PathUtils.mkdir(os.path.dirname(path), log=False)

        os.mknod(path)
        PathUtils.chown(path)

    @staticmethod
    def mkdir(path: Optional[str], log=True) -> None:
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
        PathUtils.mkdir(base, log=False)

        os.makedirs(path)
        PathUtils.chown(path)

    @staticmethod
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

    @staticmethod
    def remove(path: str) -> None:
        """Remove whatever is at the path."""
        if not os.path.exists(path):
            return

        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)

    @staticmethod
    def sanitize_path_component(group_name: str) -> str:
        """Replace characters listed in
        https://en.wikipedia.org/wiki/Filename#Reserved_characters_and_words
        with an underscore.
        """
        for character in '/\\?%*:|"<>':
            if character in group_name:
                group_name = group_name.replace(character, "_")
        return group_name

    @staticmethod
    def get_preset_path(
        folder_name: Optional[str] = None,
        preset: Optional[str] = None,
    ) -> str:
        """Get a path to the stored preset, or to store a preset to."""
        presets_base = os.path.join(PathUtils.config_path(), "presets")

        if folder_name is None:
            return presets_base

        folder_name = PathUtils.sanitize_path_component(folder_name)

        if preset is not None:
            # the extension of the preset should not be shown in the ui.
            # if a .json extension arrives this place, it has not been
            # stripped away properly prior to this.
            if not preset.endswith(".json"):
                preset = f"{preset}.json"

        if preset is None:
            return os.path.join(presets_base, folder_name)

        return os.path.join(presets_base, folder_name, preset)

    @staticmethod
    def get_config_path(*paths) -> str:
        """Get a path in ~/.config/input-remapper/."""
        return os.path.join(PathUtils.config_path(), *paths)
