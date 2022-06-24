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


"""Migration functions"""

import os
import re
import json
import copy
import shutil
import pkg_resources

from typing import List
from pathlib import Path
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

from inputremapper.configs.preset import Preset
from inputremapper.configs.mapping import Mapping, UIMapping
from inputremapper.event_combination import EventCombination
from inputremapper.logger import logger, VERSION, IS_BETA
from inputremapper.user import HOME
from inputremapper.configs.paths import get_preset_path, mkdir, CONFIG_PATH, remove
from inputremapper.configs.system_mapping import system_mapping
from inputremapper.injection.global_uinputs import global_uinputs
from inputremapper.injection.macros.parse import is_this_a_macro


def all_presets() -> List[os.PathLike]:
    """Get all presets for all groups as list."""
    if not os.path.exists(get_preset_path()):
        return []

    preset_path = Path(get_preset_path())
    presets = []
    for folder in preset_path.iterdir():
        if not folder.is_dir():
            continue

        for preset in folder.iterdir():
            if preset.suffix != ".json":
                continue

            try:
                with open(preset, "r") as f:
                    preset_dict = json.load(f)
                    yield preset, preset_dict
            except json.decoder.JSONDecodeError:
                logger.warning('Invalid json format in preset "%s"', preset)
                continue

    return presets


def config_version():
    """Get the version string in config.json as packaging.Version object."""
    config_path = os.path.join(CONFIG_PATH, "config.json")

    if not os.path.exists(config_path):
        return pkg_resources.parse_version("0.0.0")

    with open(config_path, "r") as file:
        config = json.load(file)

    if "version" in config.keys():
        return pkg_resources.parse_version(config["version"])

    return pkg_resources.parse_version("0.0.0")


def _config_suffix():
    """Append the .json suffix to the config file."""
    deprecated_path = os.path.join(CONFIG_PATH, "config")
    config_path = os.path.join(CONFIG_PATH, "config.json")
    if os.path.exists(deprecated_path) and not os.path.exists(config_path):
        logger.info('Moving "%s" to "%s"', deprecated_path, config_path)
        os.rename(deprecated_path, config_path)


def _preset_path():
    """Migrate the folder structure from < 0.4.0.

    Move existing presets into the new subfolder "presets"
    """
    new_preset_folder = os.path.join(CONFIG_PATH, "presets")
    if os.path.exists(get_preset_path()) or not os.path.exists(CONFIG_PATH):
        return

    logger.info("Migrating presets from < 0.4.0...")
    groups = os.listdir(CONFIG_PATH)
    mkdir(get_preset_path())
    for group in groups:
        path = os.path.join(CONFIG_PATH, group)
        if os.path.isdir(path):
            target = path.replace(CONFIG_PATH, new_preset_folder)
            logger.info('Moving "%s" to "%s"', path, target)
            os.rename(path, target)

    logger.info("done")


def _mapping_keys():
    """Update all preset mappings.

    Update all keys in preset to include value e.g.: "1,5"->"1,5,1"
    """
    for preset, preset_dict in all_presets():
        if "mapping" in preset_dict.keys():
            mapping = copy.deepcopy(preset_dict["mapping"])
            for key in mapping.keys():
                if key.count(",") == 1:
                    preset_dict["mapping"][f"{key},1"] = preset_dict["mapping"].pop(key)

        with open(preset, "w") as file:
            json.dump(preset_dict, file, indent=4)
            file.write("\n")


def _update_version():
    """Write the current version to the config file."""
    config_file = os.path.join(CONFIG_PATH, "config.json")
    if not os.path.exists(config_file):
        return

    logger.info("Updating version in config to %s", VERSION)
    with open(config_file, "r") as file:
        config = json.load(file)

    config["version"] = VERSION
    with open(config_file, "w") as file:
        json.dump(config, file, indent=4)


def _rename_config(new_path=CONFIG_PATH):
    """Rename .config/key-mapper to .config/input-remapper."""
    old_config_path = os.path.join(HOME, ".config/key-mapper")
    if not os.path.exists(new_path) and os.path.exists(old_config_path):
        logger.info("Moving %s to %s", old_config_path, new_path)
        shutil.move(old_config_path, new_path)


def _find_target(symbol):
    """try to find a uinput with the required capabilities for the symbol."""
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

    logger.info("could not find a suitable target UInput for '%s'", symbol)
    return None


def _add_target():
    """add the target field to each preset mapping"""
    for preset, preset_dict in all_presets():
        if "mapping" not in preset_dict.keys():
            continue

        changed = False
        for key, symbol in preset_dict["mapping"].copy().items():
            if isinstance(symbol, list):
                continue

            target = _find_target(symbol)
            if target is None:
                target = "keyboard"
                symbol = f"{symbol}\n# Broken mapping:\n# No target can handle all specified keycodes"

            logger.info(
                'Changing target of mapping for "%s" in preset "%s" to "%s"',
                key,
                preset,
                target,
            )
            symbol = [symbol, target]
            preset_dict["mapping"][key] = symbol
            changed = True

        if not changed:
            continue

        with open(preset, "w") as file:
            json.dump(preset_dict, file, indent=4)
            file.write("\n")


def _otherwise_to_else():
    """Conditional macros should use an "else" parameter instead of "otherwise"."""
    for preset, preset_dict in all_presets():
        if "mapping" not in preset_dict.keys():
            continue

        changed = False
        for key, symbol in preset_dict["mapping"].copy().items():
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

            preset_dict["mapping"][key] = symbol

        if not changed:
            continue

        with open(preset, "w") as file:
            json.dump(preset_dict, file, indent=4)
            file.write("\n")


def _convert_to_individual_mappings():
    """Convert preset.json
    from {key: [symbol, target]}
    to {key: {target: target, symbol: symbol, ...}}
    """

    for preset_path, old_preset in all_presets():
        preset = Preset(preset_path, UIMapping)
        if "mapping" in old_preset.keys():
            for combination, symbol_target in old_preset["mapping"].items():
                logger.info(
                    f"migrating from '{combination}: {symbol_target}' to mapping dict"
                )
                try:
                    combination = EventCombination.from_string(combination)
                except ValueError:
                    logger.error(
                        f"unable to migrate mapping with invalid {combination = }"
                    )
                    continue

                mapping = UIMapping(
                    event_combination=combination,
                    target_uinput=symbol_target[1],
                    output_symbol=symbol_target[0],
                )
                preset.add(mapping)

        if (
            "gamepad" in old_preset.keys()
            and "joystick" in old_preset["gamepad"].keys()
        ):
            joystick_dict = old_preset["gamepad"]["joystick"]
            left_purpose = joystick_dict.get("left_purpose")
            right_purpose = joystick_dict.get("right_purpose")
            pointer_speed = joystick_dict.get("pointer_speed")
            if pointer_speed:
                pointer_speed /= 100
            non_linearity = joystick_dict.get("non_linearity")  # Todo
            x_scroll_speed = joystick_dict.get("x_scroll_speed")
            y_scroll_speed = joystick_dict.get("y_scroll_speed")

            cfg = {
                "event_combination": None,
                "target_uinput": "mouse",
                "output_type": EV_REL,
                "output_code": None,
            }

            if left_purpose == "mouse":
                x_config = cfg.copy()
                y_config = cfg.copy()
                x_config["event_combination"] = ",".join((str(EV_ABS), str(ABS_X), "0"))
                y_config["event_combination"] = ",".join((str(EV_ABS), str(ABS_Y), "0"))
                x_config["output_code"] = REL_X
                y_config["output_code"] = REL_Y
                mapping_x = Mapping(**x_config)
                mapping_y = Mapping(**y_config)
                if pointer_speed:
                    mapping_x.gain = pointer_speed
                    mapping_y.gain = pointer_speed
                preset.add(mapping_x)
                preset.add(mapping_y)

            if right_purpose == "mouse":
                x_config = cfg.copy()
                y_config = cfg.copy()
                x_config["event_combination"] = ",".join(
                    (str(EV_ABS), str(ABS_RX), "0")
                )
                y_config["event_combination"] = ",".join(
                    (str(EV_ABS), str(ABS_RY), "0")
                )
                x_config["output_code"] = REL_X
                y_config["output_code"] = REL_Y
                mapping_x = Mapping(**x_config)
                mapping_y = Mapping(**y_config)
                if pointer_speed:
                    mapping_x.gain = pointer_speed
                    mapping_y.gain = pointer_speed
                preset.add(mapping_x)
                preset.add(mapping_y)

            if left_purpose == "wheel":
                x_config = cfg.copy()
                y_config = cfg.copy()
                x_config["event_combination"] = ",".join((str(EV_ABS), str(ABS_X), "0"))
                y_config["event_combination"] = ",".join((str(EV_ABS), str(ABS_Y), "0"))
                x_config["output_code"] = REL_HWHEEL_HI_RES
                y_config["output_code"] = REL_WHEEL_HI_RES
                mapping_x = Mapping(**x_config)
                mapping_y = Mapping(**y_config)
                if x_scroll_speed:
                    mapping_x.gain = x_scroll_speed
                if y_scroll_speed:
                    mapping_y.gain = y_scroll_speed
                preset.add(mapping_x)
                preset.add(mapping_y)

            if right_purpose == "wheel":
                x_config = cfg.copy()
                y_config = cfg.copy()
                x_config["event_combination"] = ",".join(
                    (str(EV_ABS), str(ABS_RX), "0")
                )
                y_config["event_combination"] = ",".join(
                    (str(EV_ABS), str(ABS_RY), "0")
                )
                x_config["output_code"] = REL_HWHEEL_HI_RES
                y_config["output_code"] = REL_WHEEL_HI_RES
                mapping_x = Mapping(**x_config)
                mapping_y = Mapping(**y_config)
                if x_scroll_speed:
                    mapping_x.gain = x_scroll_speed
                if y_scroll_speed:
                    mapping_y.gain = y_scroll_speed
                preset.add(mapping_x)
                preset.add(mapping_y)

        preset.save()


def _copy_to_beta():
    if os.path.exists(CONFIG_PATH) or not IS_BETA:
        # don't copy to already existing folder
        # users should delete the beta folder if they need to
        return

    regular_path = os.path.join(*os.path.split(CONFIG_PATH)[:-1])
    # workaround to maker sure the rename from key-mapper to input-remapper
    # does not move everythig to the beta folder
    _rename_config(regular_path)
    if os.path.exists(regular_path):
        logger.debug(f"copying all from {regular_path} to {CONFIG_PATH}")
        shutil.copytree(regular_path, CONFIG_PATH)


def _remove_logs():
    """We will try to rely on journalctl for this in the future."""
    try:
        remove(f"{HOME}/.log/input-remapper")
        remove("/var/log/input-remapper")
        remove("/var/log/input-remapper-control")
    except Exception as error:
        logger.debug("Failed to remove deprecated logfiles: %s", str(error))
        # this migration is not important. Continue
        pass


def migrate():
    """Migrate config files to the current release."""

    _copy_to_beta()
    v = config_version()
    if v < pkg_resources.parse_version("0.4.0"):
        _config_suffix()
        _preset_path()

    if v < pkg_resources.parse_version("1.2.2"):
        _mapping_keys()

    if v < pkg_resources.parse_version("1.3.0"):
        _rename_config()

    if v < pkg_resources.parse_version("1.4.0"):
        global_uinputs.prepare_all()
        _add_target()

    if v < pkg_resources.parse_version("1.4.1"):
        _otherwise_to_else()

    if v < pkg_resources.parse_version("1.5.0"):
        _remove_logs()

    if v < pkg_resources.parse_version("1.6.0-beta"):
        _convert_to_individual_mappings()

    # add new migrations here

    if v < pkg_resources.parse_version(VERSION):
        _update_version()
