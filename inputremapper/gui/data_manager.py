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
import glob
import os
import time
from typing import Optional, List

from inputremapper.configs.global_config import global_config
from inputremapper.configs.mapping import UIMapping
from inputremapper.configs.preset import Preset
from inputremapper.configs.paths import get_preset_path, mkdir
from inputremapper.event_combination import EventCombination
from inputremapper.exceptions import DataManagementError
from inputremapper.gui.event_handler import EventHandler, EventEnum
from inputremapper.logger import logger


class DataManager:
    def __init__(self, event_handler: EventHandler):
        self.event_handler = event_handler
        self._active_group_key: Optional[str] = None
        self._active_preset: Optional[Preset] = None
        self._active_mapping: Optional[UIMapping] = None
        self._new_mapping: Optional[UIMapping] = None
        self._config = global_config
        self._config.load_config()
        self.attach_to_event_handler()

    def attach_to_event_handler(self):
        """registers all necessary functions at the event handler"""
        (
            self.event_handler.subscribe(EventEnum.load_group, self.on_load_group)
            .subscribe(EventEnum.load_preset, self.on_load_preset)
            .subscribe(EventEnum.rename_preset, self.on_rename_preset)
            .subscribe(EventEnum.add_preset, self.on_add_preset)
            .subscribe(EventEnum.delete_preset, self.on_delete_preset)
            .subscribe(EventEnum.load_mapping, self.on_load_mapping)
            .subscribe(EventEnum.create_mapping, self.on_create_mapping)
            .subscribe(EventEnum.delete_mapping, self.on_delete_mapping)
            .subscribe(EventEnum.update_mapping, self.on_update_mapping)
            .subscribe(EventEnum.get_autoload, self.on_get_autoload)
            .subscribe(EventEnum.set_autoload, self.on_set_autoload)
            .subscribe(EventEnum.save, self.on_save)
        )

    def on_load_group(self, group_key: str):
        """gather all presets in the group and provide them"""
        self._active_group_key = group_key
        self._active_preset = None
        self._active_mapping = None
        self.event_handler.emit(EventEnum.group_loaded, presets=self.get_presets())

    def on_load_preset(self, name: str):
        """load the preset in the active group and provide all mappings"""
        if not self._active_group_key:
            raise DataManagementError("Unable to load preset. Group is not set")

        preset_path = get_preset_path(self._active_group_key, name)
        preset = Preset(preset_path, mapping_factory=UIMapping)
        preset.load()
        self._active_preset = preset
        self._active_mapping = None

        response = [(mapping.name, mapping.event_combination) for mapping in preset]
        self.event_handler.emit(EventEnum.preset_loaded, name=name, mappings=response)

    def on_rename_preset(self, new_name: str):
        """rename the current preset and move the correct file"""
        if not self._active_preset:
            raise DataManagementError("Unable rename preset: Preset is not set")

        if self._active_preset.path == get_preset_path(
            self._active_group_key, new_name
        ):
            return

        old_path = self._active_preset.path
        old_name = os.path.basename(old_path)
        new_path = get_preset_path(self._active_group_key, new_name)
        if os.path.exists(new_path):
            raise DataManagementError(
                f"cannot rename {old_name} to " f"{new_name}, preset already exists"
            )

        logger.info('Moving "%s" to "%s"', old_path, new_path)
        os.rename(old_path, new_path)
        now = time.time()
        os.utime(new_path, (now, now))
        self._active_preset.path = get_preset_path(self._active_group_key, new_name)

    def on_add_preset(self, name: str):
        if not self._active_group_key:
            raise DataManagementError("Unable to add preset. Group is not set")

        path = get_preset_path(self._active_group_key, name)
        if os.path.exists(path):
            raise DataManagementError("Unable to add preset. Preset exists")

        mkdir(path)

    def on_delete_preset(self):
        preset_path = self._active_preset.path
        logger.info('Removing "%s"', preset_path)
        self._active_preset = None
        self._active_mapping = None
        os.remove(preset_path)

    def on_load_mapping(
        self, combination: EventCombination = EventCombination.empty_combination()
    ):
        """load the mapping and provide its values as a dict"""
        if not self._active_preset:
            raise DataManagementError("Unable to load mapping. Preset is not set")

        mapping = self._active_preset.get_mapping(combination)
        if not mapping:
            raise KeyError(
                f"the mapping with {combination = } does not "
                f"exist in the {self._active_preset.path}"
            )

        self._active_mapping = mapping
        self.event_handler.emit(
            EventEnum.mapping_loaded, mapping=self._active_mapping.dict()
        )

    def on_update_mapping(self, **kwargs):
        if not self._active_mapping:
            raise DataManagementError("Cannot modify Mapping: mapping is not set")

        for key, value in kwargs.items():
            setattr(self._active_mapping, key, value)

    def on_create_mapping(self):
        if not self._active_preset:
            raise DataManagementError("cannot create mapping: preset is not set")
        self._active_preset.add(UIMapping())
        logger.debug(self._active_preset)

    def on_delete_mapping(self):
        """delete teh active mapping"""
        if not self._active_mapping:
            raise DataManagementError(
                "cannot delete active mapping: active mapping is not set"
            )

        self._active_preset.remove(self._active_mapping.event_combination)
        self._active_mapping = None

    def on_get_autoload(self):
        if not self._active_preset:
            raise DataManagementError("cannot get autoload status: Preset is not set")
        name = os.path.basename(self._active_preset.path).split(".")[0]
        autoload = self._config.is_autoloaded(self._active_group_key, name)
        self.event_handler.emit(EventEnum.autoload_status, autoload=autoload)

    def on_set_autoload(self, autoload: bool):
        if not self._active_preset:
            raise DataManagementError("cannot set autoload status: Preset is not set")

        name = os.path.basename(self._active_preset.path).split(".")[0]
        self._config.set_autoload_preset(
            self._active_group_key, name if autoload else None
        )

    def on_save(self):
        if self._active_preset:
            self._active_preset.save()

    def get_presets(self) -> List[str]:
        """Get all preset filenames for self._active_group_key and user,
        starting with the newest."""
        if not self._active_group_key:
            raise DataManagementError("Unable to load presets. group is not set")
        device_folder = get_preset_path(self._active_group_key)
        mkdir(device_folder)

        paths = glob.glob(os.path.join(device_folder, "*.json"))
        presets = [
            os.path.splitext(os.path.basename(path))[0]
            for path in sorted(paths, key=os.path.getmtime)
        ]
        # the highest timestamp to the front
        presets.reverse()
        return presets
