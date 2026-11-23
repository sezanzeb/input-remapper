# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2026 sezanzeb <4t1pzast9@mozmail.com>
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


"""Reading and writing profiles: one JSON file per profile."""

from __future__ import annotations

import json
import os
from pathlib import Path

from inputremapper.configs.paths import PathUtils
from inputremapper.gui_v3.document import Profile, Workspace
from inputremapper.logging.logger import logger


def default_profiles_dir() -> Path:
    return Path(PathUtils.config_path()) / "v3" / "profiles"


def _file_for(directory: Path, name: str) -> Path:
    return directory / f"{PathUtils.sanitize_path_component(name)}.json"


def load_workspace(directory: Path | None = None) -> Workspace:
    directory = directory or default_profiles_dir()
    profiles: list[Profile] = []
    if directory.is_dir():
        for path in sorted(directory.glob("*.json")):
            try:
                data = json.loads(path.read_text())
                profiles.append(Profile.from_json(path.stem, data))
            except (ValueError, KeyError, TypeError) as error:
                # Skip rather than fail: one broken file shouldn't hide the rest.
                logger.error('Could not load profile "%s": %s', path, error)
    return Workspace(tuple(profiles))


def save_workspace(
    workspace: Workspace,
    directory: Path | None = None,
    previous: Workspace | None = None,
) -> None:
    """Write the profiles that changed, and remove the ones that are gone.

    Without `previous` every profile is written, and files of unknown profiles are
    left alone.
    """
    directory = directory or default_profiles_dir()
    directory.mkdir(parents=True, exist_ok=True)

    for profile in workspace.profiles:
        if previous is not None and previous.get(profile.name) == profile:
            continue
        _write_atomic(_file_for(directory, profile.name), profile)

    if previous is not None:
        for old in previous.profiles:
            if workspace.get(old.name) is None:
                _file_for(directory, old.name).unlink(missing_ok=True)


def _write_atomic(path: Path, profile: Profile) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(profile.to_json(), indent=2) + "\n")
    os.replace(temporary, path)
