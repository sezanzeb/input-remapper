#!/usr/bin/python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2022 sezanzeb <proxima@sezanzeb.de>
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
from __future__ import annotations

"""Contains and manages mappings."""


import os
import re
import json
import glob
import time

from typing import Tuple, Dict, List
from evdev.ecodes import EV_KEY, BTN_LEFT

from inputremapper.logger import logger
from inputremapper.paths import touch, get_preset_path, mkdir
from inputremapper.configs.global_config import ConfigBase, global_config
from inputremapper.key import Key
from inputremapper.injection.macros.parse import clean
from inputremapper.groups import groups


def split_key(key):
    """Take a key like "1,2,3" and return a 3-tuple of ints."""
    key = key.strip()

    if key.count(",") != 2:
        logger.error('Found invalid key: "%s"', key)
        return None

    ev_type, code, value = key.split(",")
    try:
        key = (int(ev_type), int(code), int(value))
    except ValueError:
        logger.error('Found non-int in: "%s"', key)
        return None

    return key


class Preset(ConfigBase):
    """Contains and manages mappings of a single preset."""

    _mapping: Dict[Key, Tuple[str, str]]

    def __init__(self):
        self._mapping = {}  # a mapping of Key objects to strings
        self._changed = False

        # are there actually any keys set in the preset file?
        self.num_saved_keys = 0

        super().__init__(fallback=global_config)

    def __iter__(self) -> Preset._mapping.items:
        """Iterate over Key objects and their mappings."""
        return iter(self._mapping.items())

    def __len__(self):
        return len(self._mapping)

    def set(self, *args):
        """Set a config value. See `ConfigBase.set`."""
        self._changed = True
        return super().set(*args)

    def remove(self, *args):
        """Remove a config value. See `ConfigBase.remove`."""
        self._changed = True
        return super().remove(*args)

    def change(self, new_key, target, symbol, previous_key=None):
        """Replace the mapping of a keycode with a different one.

        Parameters
        ----------
        new_key : Key
        target : string
            name of target uinput
        symbol : string
            A single symbol known to xkb or linux.
            Examples: KEY_KP1, Shift_L, a, B, BTN_LEFT.
        previous_key : Key or None
            the previous key

            If not set, will not remove any previous mapping. If you recently
            used (1, 10, 1) for new_key and want to overwrite that with
            (1, 11, 1), provide (1, 10, 1) here.
        """
        if not isinstance(new_key, Key):
            raise TypeError(f"Expected {new_key} to be a Key object")

        if symbol is None or symbol.strip() == "":
            raise ValueError("Expected `symbol` not to be empty")

        if target is None or target.strip() == "":
            raise ValueError("Expected `target` not to be None")

        target = target.strip()
        symbol = symbol.strip()
        output = (symbol, target)

        if previous_key is None and self._mapping.get(new_key):
            # the key didn't change
            previous_key = new_key

        key_changed = new_key != previous_key
        if not key_changed and (symbol, target) == self._mapping.get(new_key):
            # nothing was changed, no need to act
            return

        self.clear(new_key)  # this also clears all equivalent keys

        logger.debug('changing %s to "%s"', new_key, clean(symbol))

        self._mapping[new_key] = output

        if key_changed and previous_key is not None:
            # clear previous mapping of that code, because the line
            # representing that one will now represent a different one
            self.clear(previous_key)

        self._changed = True

    def has_unsaved_changes(self):
        """Check if there are unsaved changed."""
        return self._changed

    def set_has_unsaved_changes(self, changed):
        """Write down if there are unsaved changes, or if they have been saved."""
        self._changed = changed

    def clear(self, key):
        """Remove a keycode from the preset.

        Parameters
        ----------
        key : Key
        """
        if not isinstance(key, Key):
            raise TypeError(f"Expected key to be a Key object but got {key}")

        for permutation in key.get_permutations():
            if permutation in self._mapping:
                logger.debug("%s cleared", permutation)
                del self._mapping[permutation]
                self._changed = True
                # there should be only one variation of the permutations
                # in the preset actually

    def empty(self):
        """Remove all mappings and custom configs without saving."""
        self._mapping = {}
        self._changed = True
        self.clear_config()

    def load(self, path):
        """Load a dumped JSON from home to overwrite the mappings.

        Parameters
        path : string
            Path of the preset file
        """
        logger.info('Loading preset from "%s"', path)

        if not os.path.exists(path):
            raise FileNotFoundError(f'Tried to load non-existing preset "{path}"')

        self.empty()
        self._changed = False

        with open(path, "r") as file:
            preset_dict = json.load(file)

            if not isinstance(preset_dict.get("mapping"), dict):
                logger.error(
                    "Expected mapping to be a dict, but was %s. "
                    'Invalid preset config at "%s"',
                    preset_dict.get("mapping"),
                    path,
                )
                return

            for key, symbol in preset_dict["mapping"].items():
                try:
                    key = Key(
                        *[
                            split_key(chunk)
                            for chunk in key.split("+")
                            if chunk.strip() != ""
                        ]
                    )
                except ValueError as error:
                    logger.error(str(error))
                    continue

                if None in key:
                    continue

                if isinstance(symbol, list):
                    symbol = tuple(symbol)  # use a immutable type

                logger.debug("%s maps to %s", key, symbol)
                self._mapping[key] = symbol

            # add any metadata of the preset
            for key in preset_dict:
                if key == "mapping":
                    continue
                self._config[key] = preset_dict[key]

        self._changed = False
        self.num_saved_keys = len(self)

    def save(self, path):
        """Dump as JSON into home."""
        logger.info("Saving preset to %s", path)

        touch(path)

        with open(path, "w") as file:
            if self._config.get("mapping") is not None:
                logger.error(
                    '"mapping" is reserved and cannot be used as config ' "key: %s",
                    self._config.get("mapping"),
                )

            preset_dict = self._config.copy()  # shallow copy

            # make sure to keep the option to add metadata if ever needed,
            # so put the mapping into a special key
            json_ready_mapping = {}
            # tuple keys are not possible in json, encode them as string
            for key, value in self._mapping.items():
                new_key = "+".join(
                    [",".join([str(value) for value in sub_key]) for sub_key in key]
                )
                json_ready_mapping[new_key] = value

            preset_dict["mapping"] = json_ready_mapping
            json.dump(preset_dict, file, indent=4)
            file.write("\n")

        self._changed = False
        self.num_saved_keys = len(self)

    def get_mapping(self, key):
        """Read the (symbol, target)-tuple that is mapped to this keycode.

        Parameters
        ----------
        key : Key
        """
        if not isinstance(key, Key):
            raise TypeError(f"Expected key to be a Key object but got {key}")

        for permutation in key.get_permutations():
            existing = self._mapping.get(permutation)
            if existing is not None:
                return existing

        return None

    def dangerously_mapped_btn_left(self):
        """Return True if this mapping disables BTN_Left."""
        if self.get_mapping(Key(EV_KEY, BTN_LEFT, 1)) is not None:
            values = [value[0].lower() for value in self._mapping.values()]
            return "btn_left" not in values

        return False


###########################################################################
# Method from previously presets.py
# TODO: See what can be implemented as classmethod or
#  member function of Preset
###########################################################################

def get_available_preset_name(group_name, preset="new preset", copy=False):
    """Increment the preset name until it is available."""
    if group_name is None:
        # endless loop otherwise
        raise ValueError("group_name may not be None")

    preset = preset.strip()

    if copy and not re.match(r"^.+\scopy( \d+)?$", preset):
        preset = f"{preset} copy"

    # find a name that is not already taken
    if os.path.exists(get_preset_path(group_name, preset)):
        # if there already is a trailing number, increment it instead of
        # adding another one
        match = re.match(r"^(.+) (\d+)$", preset)
        if match:
            preset = match[1]
            i = int(match[2]) + 1
        else:
            i = 2

        while os.path.exists(get_preset_path(group_name, f"{preset} {i}")):
            i += 1

        return f"{preset} {i}"

    return preset


def get_presets(group_name: str) -> List[str]:
    """Get all preset filenames for the device and user, starting with the newest.

    Parameters
    ----------
    group_name : string
    """
    device_folder = get_preset_path(group_name)
    mkdir(device_folder)

    paths = glob.glob(os.path.join(device_folder, "*.json"))
    presets = [
        os.path.splitext(os.path.basename(path))[0]
        for path in sorted(paths, key=os.path.getmtime)
    ]
    # the highest timestamp to the front
    presets.reverse()
    return presets


def get_any_preset() -> Tuple[str | None, str | None]:
    """Return the first found tuple of (device, preset)."""
    group_names = groups.list_group_names()
    if len(group_names) == 0:
        return None, None
    any_device = list(group_names)[0]
    any_preset = (get_presets(any_device) or [None])[0]
    return any_device, any_preset


def find_newest_preset(group_name=None):
    """Get a tuple of (device, preset) that was most recently modified
    in the users home directory.

    If no device has been configured yet, return an arbitrary device.

    Parameters
    ----------
    group_name : string
        If set, will return the newest preset for the device or None
    """
    # sort the oldest files to the front in order to use pop to get the newest
    if group_name is None:
        paths = sorted(
            glob.glob(os.path.join(get_preset_path(), "*/*.json")), key=os.path.getmtime
        )
    else:
        paths = sorted(
            glob.glob(os.path.join(get_preset_path(group_name), "*.json")),
            key=os.path.getmtime,
        )

    if len(paths) == 0:
        logger.debug("No presets found")
        return get_any_preset()

    group_names = groups.list_group_names()

    newest_path = None
    while len(paths) > 0:
        # take the newest path
        path = paths.pop()
        preset = os.path.split(path)[1]
        group_name = os.path.split(os.path.split(path)[0])[1]
        if group_name in group_names:
            newest_path = path
            break

    if newest_path is None:
        return get_any_preset()

    preset = os.path.splitext(preset)[0]
    logger.debug('The newest preset is "%s", "%s"', group_name, preset)

    return group_name, preset


def delete_preset(group_name, preset):
    """Delete one of the users presets."""
    preset_path = get_preset_path(group_name, preset)
    if not os.path.exists(preset_path):
        logger.debug('Cannot remove non existing path "%s"', preset_path)
        return

    logger.info('Removing "%s"', preset_path)
    os.remove(preset_path)

    device_path = get_preset_path(group_name)
    if os.path.exists(device_path) and len(os.listdir(device_path)) == 0:
        logger.debug('Removing empty dir "%s"', device_path)
        os.rmdir(device_path)


def rename_preset(group_name, old_preset_name, new_preset_name):
    """Rename one of the users presets while avoiding name conflicts."""
    if new_preset_name == old_preset_name:
        return None

    new_preset_name = get_available_preset_name(group_name, new_preset_name)
    logger.info('Moving "%s" to "%s"', old_preset_name, new_preset_name)
    os.rename(
        get_preset_path(group_name, old_preset_name),
        get_preset_path(group_name, new_preset_name),
    )
    # set the modification date to now
    now = time.time()
    os.utime(get_preset_path(group_name, new_preset_name), (now, now))
    return new_preset_name
