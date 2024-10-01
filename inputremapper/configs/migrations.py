# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2024 sezanzeb <b8x45ygc9@mozmail.com>
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

"""Migration functions.

Only write changes to disk, if there actually are changes. Otherwise, file-modification
dates are destroyed.
"""
from __future__ import annotations

import copy
import json
import os
import re
import shutil
from pathlib import Path
from typing import Iterator, Tuple, Dict, List, Optional, TypedDict

import pkg_resources
from evdev.ecodes import (
    EV_KEY,
    EV_ABS,
    EV_REL,
    ABS_X,
    ABS_Y,
    ABS_RX,
    ABS_RY,
    REL_X,
    REL_Y,
    REL_WHEEL_HI_RES,
    REL_HWHEEL_HI_RES,
)

from inputremapper.configs.input_config import InputCombination, InputConfig
from inputremapper.configs.mapping import Mapping, UIMapping
from inputremapper.configs.paths import PathUtils
from inputremapper.configs.preset import Preset
from inputremapper.configs.system_mapping import system_mapping, SystemMapping
from inputremapper.injection.global_uinputs import global_uinputs, GlobalUInputs
from inputremapper.injection.macros.parse import is_this_a_macro
from inputremapper.logger.logger import logger, VERSION
from inputremapper.user import UserUtils


class Config(TypedDict):
    input_combination: Optional[InputCombination]
    target_uinput: str
    output_type: int
    output_code: Optional[int]


class Migrations:
    @staticmethod
    def migrate():
        """Migrate config files to the current release."""

        Migrations._rename_to_input_remapper()

        Migrations._copy_to_v2()

        v = Migrations.config_version()

        if v < pkg_resources.parse_version("0.4.0"):
            Migrations._config_suffix()
            Migrations._preset_path()

        if v < pkg_resources.parse_version("1.2.2"):
            Migrations._mapping_keys()

        if v < pkg_resources.parse_version("1.4.0"):
            global_uinputs.prepare_all()
            Migrations._add_target()

        if v < pkg_resources.parse_version("1.4.1"):
            Migrations._otherwise_to_else()

        if v < pkg_resources.parse_version("1.5.0"):
            Migrations._remove_logs()

        if v < pkg_resources.parse_version("1.6.0-beta"):
            Migrations._convert_to_individual_mappings()

        # add new migrations here

        if v < pkg_resources.parse_version(VERSION):
            Migrations._update_version()

    @staticmethod
    def all_presets() -> Iterator[Tuple[os.PathLike, Dict | List]]:
        """Get all presets for all groups as list."""
        if not os.path.exists(PathUtils.get_preset_path()):
            return

        preset_path = Path(PathUtils.get_preset_path())
        for folder in preset_path.iterdir():
            if not folder.is_dir():
                continue

            for preset in folder.iterdir():
                if preset.suffix != ".json":
                    continue

                try:
                    with open(preset, "r") as f:
                        preset_structure = json.load(f)
                        yield preset, preset_structure
                except json.decoder.JSONDecodeError:
                    logger.warning('Invalid json format in preset "%s"', preset)
                    continue

    @staticmethod
    def config_version():
        """Get the version string in config.json as packaging.Version object."""
        config_path = os.path.join(PathUtils.config_path(), "config.json")

        if not os.path.exists(config_path):
            return pkg_resources.parse_version("0.0.0")

        with open(config_path, "r") as file:
            config = json.load(file)

        if "version" in config.keys():
            return pkg_resources.parse_version(config["version"])

        return pkg_resources.parse_version("0.0.0")

    @staticmethod
    def _config_suffix():
        """Append the .json suffix to the config file."""
        deprecated_path = os.path.join(PathUtils.config_path(), "config")
        config_path = os.path.join(PathUtils.config_path(), "config.json")
        if os.path.exists(deprecated_path) and not os.path.exists(config_path):
            logger.info('Moving "%s" to "%s"', deprecated_path, config_path)
            os.rename(deprecated_path, config_path)

    @staticmethod
    def _preset_path():
        """Migrate the folder structure from < 0.4.0.

        Move existing presets into the new subfolder 'presets'
        """
        new_preset_folder = os.path.join(PathUtils.config_path(), "presets")
        if os.path.exists(PathUtils.get_preset_path()) or not os.path.exists(
            PathUtils.config_path()
        ):
            return

        logger.info("Migrating presets from < 0.4.0...")
        groups = os.listdir(PathUtils.config_path())
        PathUtils.mkdir(PathUtils.get_preset_path())
        for group in groups:
            path = os.path.join(PathUtils.config_path(), group)
            if os.path.isdir(path):
                target = path.replace(PathUtils.config_path(), new_preset_folder)
                logger.info('Moving "%s" to "%s"', path, target)
                os.rename(path, target)

        logger.info("done")

    @staticmethod
    def _mapping_keys():
        """Update all preset mappings.

        Update all keys in preset to include value e.g.: '1,5'->'1,5,1'
        """
        for preset, preset_structure in Migrations.all_presets():
            if isinstance(preset_structure, list):
                continue  # the preset must be at least 1.6-beta version

            changes = 0
            if "mapping" in preset_structure.keys():
                mapping = copy.deepcopy(preset_structure["mapping"])
                for key in mapping.keys():
                    if key.count(",") == 1:
                        preset_structure["mapping"][f"{key},1"] = preset_structure[
                            "mapping"
                        ].pop(key)
                        changes += 1

            if changes:
                with open(preset, "w") as file:
                    logger.info('Updating mapping keys of "%s"', preset)
                    json.dump(preset_structure, file, indent=4)
                    file.write("\n")

    @staticmethod
    def _update_version():
        """Write the current version to the config file."""
        config_file = os.path.join(PathUtils.config_path(), "config.json")
        if not os.path.exists(config_file):
            return

        with open(config_file, "r") as file:
            config = json.load(file)

        config["version"] = VERSION
        with open(config_file, "w") as file:
            logger.info('Updating version in config to "%s"', VERSION)
            json.dump(config, file, indent=4)

    @staticmethod
    def _rename_to_input_remapper():
        """Rename .config/key-mapper to .config/input-remapper."""
        old_config_path = os.path.join(UserUtils.home, ".config/key-mapper")
        if not os.path.exists(PathUtils.config_path()) and os.path.exists(
            old_config_path
        ):
            logger.info("Moving %s to %s", old_config_path, PathUtils.config_path())
            shutil.move(old_config_path, PathUtils.config_path())

    @staticmethod
    def _find_target(symbol):
        """Try to find a uinput with the required capabilities for the symbol."""
        capabilities = {EV_KEY: set(), EV_REL: set()}

        if is_this_a_macro(symbol):
            # deprecated mechanic, cannot figure this out anymore
            # capabilities = parse(symbol).get_capabilities()
            return None

        capabilities[EV_KEY] = {system_mapping.get(symbol)}

        if len(capabilities[EV_REL]) > 0:
            return "mouse"

        for name, uinput in global_uinputs.devices.items():
            if capabilities[EV_KEY].issubset(uinput.capabilities()[EV_KEY]):
                return name

        logger.info('could not find a suitable target UInput for "%s"', symbol)
        return None

    @staticmethod
    def _add_target():
        """Add the target field to each preset mapping."""
        for preset, preset_structure in Migrations.all_presets():
            if isinstance(preset_structure, list):
                continue

            if "mapping" not in preset_structure.keys():
                continue

            changed = False
            for key, symbol in preset_structure["mapping"].copy().items():
                if isinstance(symbol, list):
                    continue

                target = Migrations._find_target(symbol)
                if target is None:
                    target = "keyboard"
                    symbol = (
                        f"{symbol}\n"
                        "# Broken mapping:\n"
                        "# No target can handle all specified keycodes"
                    )

                logger.info(
                    'Changing target of mapping for "%s" in preset "%s" to "%s"',
                    key,
                    preset,
                    target,
                )
                symbol = [symbol, target]
                preset_structure["mapping"][key] = symbol
                changed = True

            if not changed:
                continue

            with open(preset, "w") as file:
                logger.info('Adding targets for "%s"', preset)
                json.dump(preset_structure, file, indent=4)
                file.write("\n")

    @staticmethod
    def _otherwise_to_else():
        """Conditional macros should use an "else" parameter instead of "otherwise"."""
        for preset, preset_structure in Migrations.all_presets():
            if isinstance(preset_structure, list):
                continue

            if "mapping" not in preset_structure.keys():
                continue

            changed = False
            for key, symbol in preset_structure["mapping"].copy().items():
                if not is_this_a_macro(symbol[0]):
                    continue

                symbol_before = symbol[0]
                symbol[0] = re.sub(r"otherwise\s*=\s*", "else=", symbol[0])

                if symbol_before == symbol[0]:
                    continue

                changed = changed or symbol_before != symbol[0]

                logger.info(
                    'Changing mapping for "%s" in preset "%s" to "%s"',
                    key,
                    preset,
                    symbol[0],
                )

                preset_structure["mapping"][key] = symbol

            if not changed:
                continue

            with open(preset, "w") as file:
                logger.info('Changing otherwise to else for "%s"', preset)
                json.dump(preset_structure, file, indent=4)
                file.write("\n")

    @staticmethod
    def _input_combination_from_string(combination_string: str) -> InputCombination:
        configs = []
        for event_str in combination_string.split("+"):
            type_, code, analog_threshold = event_str.split(",")
            configs.append(
                {
                    "type": int(type_),
                    "code": int(code),
                    "analog_threshold": int(analog_threshold),
                }
            )

        return InputCombination(configs)

    @staticmethod
    def _convert_to_individual_mappings() -> None:
        """Convert preset.json
        from {key: [symbol, target]}
        to [{input_combination: ..., output_symbol: symbol, ...}]
        """

        for old_preset_path, old_preset in Migrations.all_presets():
            if isinstance(old_preset, list):
                continue

            migrated_preset = Preset(old_preset_path, UIMapping)
            if "mapping" in old_preset.keys():
                for combination, symbol_target in old_preset["mapping"].items():
                    logger.info(
                        'migrating from "%s: %s" to mapping dict',
                        combination,
                        symbol_target,
                    )
                    try:
                        combination = Migrations._input_combination_from_string(
                            combination
                        )
                    except ValueError:
                        logger.error(
                            "unable to migrate mapping with invalid combination %s",
                            combination,
                        )
                        continue

                    mapping = UIMapping(
                        input_combination=combination,
                        target_uinput=symbol_target[1],
                        output_symbol=symbol_target[0],
                    )
                    migrated_preset.add(mapping)

            if (
                "gamepad" in old_preset.keys()
                and "joystick" in old_preset["gamepad"].keys()
            ):
                joystick_dict = old_preset["gamepad"]["joystick"]
                left_purpose = joystick_dict.get("left_purpose")
                right_purpose = joystick_dict.get("right_purpose")
                # TODO if pointer_speed is migrated, why is it in my config?
                pointer_speed = joystick_dict.get("pointer_speed")
                if pointer_speed:
                    pointer_speed /= 100
                non_linearity = joystick_dict.get("non_linearity")  # Todo
                x_scroll_speed = joystick_dict.get("x_scroll_speed")
                y_scroll_speed = joystick_dict.get("y_scroll_speed")

                cfg: Config = {
                    "input_combination": None,
                    "target_uinput": "mouse",
                    "output_type": EV_REL,
                    "output_code": None,
                }

                if left_purpose == "mouse":
                    x_config = cfg.copy()
                    y_config = cfg.copy()
                    x_config["input_combination"] = InputCombination(
                        [InputConfig(type=EV_ABS, code=ABS_X)]
                    )
                    y_config["input_combination"] = InputCombination(
                        [InputConfig(type=EV_ABS, code=ABS_Y)]
                    )
                    x_config["output_code"] = REL_X
                    y_config["output_code"] = REL_Y
                    mapping_x = Mapping(**x_config)
                    mapping_y = Mapping(**y_config)
                    if pointer_speed:
                        mapping_x.gain = pointer_speed
                        mapping_y.gain = pointer_speed
                    migrated_preset.add(mapping_x)
                    migrated_preset.add(mapping_y)

                if right_purpose == "mouse":
                    x_config = cfg.copy()
                    y_config = cfg.copy()
                    x_config["input_combination"] = InputCombination(
                        [InputConfig(type=EV_ABS, code=ABS_RX)]
                    )
                    y_config["input_combination"] = InputCombination(
                        [InputConfig(type=EV_ABS, code=ABS_RY)]
                    )
                    x_config["output_code"] = REL_X
                    y_config["output_code"] = REL_Y
                    mapping_x = Mapping(**x_config)
                    mapping_y = Mapping(**y_config)
                    if pointer_speed:
                        mapping_x.gain = pointer_speed
                        mapping_y.gain = pointer_speed
                    migrated_preset.add(mapping_x)
                    migrated_preset.add(mapping_y)

                if left_purpose == "wheel":
                    x_config = cfg.copy()
                    y_config = cfg.copy()
                    x_config["input_combination"] = InputCombination(
                        [InputConfig(type=EV_ABS, code=ABS_X)]
                    )
                    y_config["input_combination"] = InputCombination(
                        [InputConfig(type=EV_ABS, code=ABS_Y)]
                    )
                    x_config["output_code"] = REL_HWHEEL_HI_RES
                    y_config["output_code"] = REL_WHEEL_HI_RES
                    mapping_x = Mapping(**x_config)
                    mapping_y = Mapping(**y_config)
                    if x_scroll_speed:
                        mapping_x.gain = x_scroll_speed
                    if y_scroll_speed:
                        mapping_y.gain = y_scroll_speed
                    migrated_preset.add(mapping_x)
                    migrated_preset.add(mapping_y)

                if right_purpose == "wheel":
                    x_config = cfg.copy()
                    y_config = cfg.copy()
                    x_config["input_combination"] = InputCombination(
                        [InputConfig(type=EV_ABS, code=ABS_RX)]
                    )
                    y_config["input_combination"] = InputCombination(
                        [InputConfig(type=EV_ABS, code=ABS_RY)]
                    )
                    x_config["output_code"] = REL_HWHEEL_HI_RES
                    y_config["output_code"] = REL_WHEEL_HI_RES
                    mapping_x = Mapping(**x_config)
                    mapping_y = Mapping(**y_config)
                    if x_scroll_speed:
                        mapping_x.gain = x_scroll_speed
                    if y_scroll_speed:
                        mapping_y.gain = y_scroll_speed
                    migrated_preset.add(mapping_x)
                    migrated_preset.add(mapping_y)

            migrated_preset.save()

    @staticmethod
    def _copy_to_v2():
        """Move the beta config to the v2 path, or copy the v1 config to the v2 path."""
        # TODO test
        if os.path.exists(PathUtils.config_path()):
            # don't copy to already existing folder
            # users should delete the input-remapper-2 folder if they need to
            return

        # prioritize the v1 configs over beta configs
        old_path = os.path.join(UserUtils.home, ".config/input-remapper")
        if os.path.exists(os.path.join(old_path, "config.json")):
            # no beta path, only old presets exist. COPY to v2 path, which will then be
            # migrated by the various migrations.
            logger.debug("copying all from %s to %s", old_path, PathUtils.config_path())
            shutil.copytree(old_path, PathUtils.config_path())
            return

        # if v1 configs don't exist, try to find beta configs.
        beta_path = os.path.join(
            UserUtils.home, ".config/input-remapper/beta_1.6.0-beta"
        )
        if os.path.exists(beta_path):
            # There has never been a different version than "1.6.0-beta" in beta, so we
            # only need to check for that exact directory
            # already migrated, possibly new presets in them, move to v2 path
            logger.debug("moving %s to %s", beta_path, PathUtils.config_path())
            shutil.move(beta_path, PathUtils.config_path())

    @staticmethod
    def _remove_logs():
        """We will try to rely on journalctl for this in the future."""
        try:
            PathUtils.remove(f"{UserUtils.home}/.log/input-remapper")
            PathUtils.remove("/var/log/input-remapper")
            PathUtils.remove("/var/log/input-remapper-control")
        except Exception as error:
            logger.debug("Failed to remove deprecated logfiles: %s", str(error))
            # this migration is not important. Continue
            pass
