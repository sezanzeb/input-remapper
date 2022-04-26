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
from typing import Optional, List, Tuple

from inputremapper.configs.global_config import GlobalConfig, global_config
from inputremapper.configs.mapping import UIMapping
from inputremapper.configs.preset import Preset
from inputremapper.configs.paths import get_preset_path, mkdir, split_all
from inputremapper.event_combination import EventCombination
from inputremapper.exceptions import DataManagementError
from inputremapper.groups import groups, _Group, _Groups
from inputremapper.gui.event_handler import EventHandler, EventEnum
from inputremapper.injection.global_uinputs import global_uinputs
from inputremapper.logger import logger


class DataManager:
    def __init__(self, event_handler: EventHandler):
        self.event_handler = event_handler
        self._active_group_key: Optional[str] = None
        self._active_preset: Optional[Preset] = None
        self._active_mapping: Optional[UIMapping] = None
        self._config = global_config
        self._config.load_config()
        self.attach_to_event_handler()
        global_uinputs.prepare_all()

    @property
    def _autoload(self) -> bool:
        if not self._active_preset:
            return False
        return self._config.is_autoloaded(
            self._active_group_key, self.get_preset_name()
        )

    @_autoload.setter
    def _autoload(self, status: bool):
        if self._active_preset:
            if status:
                self._config.set_autoload_preset(
                    self._active_group_key, self.get_preset_name()
                )
            elif self._autoload:
                self._config.set_autoload_preset(self._active_group_key, None)

    @property
    def active_group(self) -> _Group:
        return groups.find(key=self._active_group_key)

    @property
    def groups(self) -> _Groups:
        return groups

    def newest_group(self) -> str:
        """group_key of the group with the most recently modified preset"""
        paths = []
        for path in glob.glob(os.path.join(get_preset_path(), "*/*.json")):
            if self.groups.find(key=split_all(path)[-2]):
                paths.append((path, os.path.getmtime(path)))

        path, _ = max(paths, key=lambda x: x[1])
        return split_all(path)[-2]

    def newest_preset(self) -> str:
        """preset name of the most recently modified preset in the active group"""
        if not self._active_group_key:
            raise DataManagementError("cannot find newest preset: Group is not set")

        paths = [
            (path, os.path.getmtime(path))
            for path in glob.glob(
                os.path.join(get_preset_path(self._active_group_key), "*.json")
            )
        ]
        path, _ = max(paths, key=lambda x: x[1])
        return os.path.split(path)[-1].split(".")[0]

    def emit_group_changed(self):
        self.event_handler.emit(
            EventEnum.group_changed,
            group_key=self._active_group_key,
            presets=self.get_presets(),
        )

    def emit_preset_changed(self):
        self.event_handler.emit(
            EventEnum.preset_changed,
            name=self.get_preset_name(),
            mappings=self.get_mappings(),
        )

    def emit_autoload_changed(self):
        if self._active_preset:
            self.event_handler.emit(EventEnum.autoload_changed, autoload=self._autoload)

    def emit_mapping_changed(self):
        mapping = self._active_mapping
        if mapping:
            self.event_handler.emit(EventEnum.mapping_changed, mapping=mapping.dict())
        else:
            self.event_handler.emit(EventEnum.mapping_changed, mapping=None)

    def get_presets(self) -> List[str]:
        """Get all preset filenames for self._active_group_key and user,
        starting with the newest."""
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

    def get_preset_name(self) -> Optional[str]:
        """get the current active preset name"""
        if not self._active_preset:
            return None
        return os.path.basename(self._active_preset.path).split(".")[0]

    def get_mappings(self) -> Optional[List[Tuple[str, EventCombination]]]:
        if not self._active_preset:
            return None
        return [
            (mapping.name, mapping.event_combination) for mapping in self._active_preset
        ]

    def attach_to_event_handler(self):
        """registers all necessary functions at the event handler"""
        pass

    def load_group(self, group_key: str):
        """gather all presets in the group and provide them"""
        self._active_mapping = None
        self._active_preset = None
        self._active_group_key = group_key
        self.emit_mapping_changed()
        self.emit_preset_changed()
        self.emit_group_changed()

    def load_preset(self, name: str):
        """load the preset in the active group and provide all mappings"""
        if not self._active_group_key:
            raise DataManagementError("Unable to load preset. Group is not set")

        preset_path = get_preset_path(self._active_group_key, name)
        preset = Preset(preset_path, mapping_factory=UIMapping)
        preset.load()
        self._active_mapping = None
        self._active_preset = preset
        self.emit_mapping_changed()
        self.emit_preset_changed()
        self.emit_autoload_changed()

    def rename_preset(self, new_name: str):
        """rename the current preset and move the correct file"""
        if not self._active_preset:
            raise DataManagementError("Unable rename preset: Preset is not set")

        if self._active_preset.path == get_preset_path(
            self._active_group_key, new_name
        ):
            return

        old_path = self._active_preset.path
        old_name = os.path.basename(old_path).split(".")[0]
        new_path = get_preset_path(self._active_group_key, new_name)
        if os.path.exists(new_path):
            raise DataManagementError(
                f"cannot rename {old_name} to " f"{new_name}, preset already exists"
            )

        logger.info('Moving "%s" to "%s"', old_path, new_path)
        os.rename(old_path, new_path)
        now = time.time()
        os.utime(new_path, (now, now))

        if self._config.is_autoloaded(self._active_group_key, old_name):
            self._config.set_autoload_preset(self._active_group_key, new_name)

        self._active_preset.path = get_preset_path(self._active_group_key, new_name)
        self.emit_group_changed()
        self.emit_preset_changed()

    def add_preset(self, name: str):
        if not self._active_group_key:
            raise DataManagementError("Unable to add preset. Group is not set")

        path = get_preset_path(self._active_group_key, name)
        if os.path.exists(path):
            raise DataManagementError("Unable to add preset. Preset exists")

        mkdir(path)
        self.emit_group_changed()

    def delete_preset(self):
        preset_path = self._active_preset.path
        logger.info('Removing "%s"', preset_path)
        os.remove(preset_path)
        self._active_mapping = None
        self._active_preset = None
        self.emit_mapping_changed()
        self.emit_preset_changed()
        self.emit_group_changed()

    def load_mapping(self, combination: EventCombination):
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
        self.emit_mapping_changed()

    def update_mapping(self, **kwargs):
        if not self._active_mapping:
            raise DataManagementError("Cannot modify Mapping: mapping is not set")

        for key, value in kwargs.items():
            setattr(self._active_mapping, key, value)
        self.emit_mapping_changed()

    def create_mapping(self):
        if not self._active_preset:
            raise DataManagementError("cannot create mapping: preset is not set")
        self._active_preset.add(UIMapping())
        self.emit_preset_changed()

    def delete_mapping(self):
        """delete teh active mapping"""
        if not self._active_mapping:
            raise DataManagementError(
                "cannot delete active mapping: active mapping is not set"
            )

        self._active_preset.remove(self._active_mapping.event_combination)
        self._active_mapping = None
        self.emit_mapping_changed()
        self.emit_preset_changed()

    def set_autoload(self, autoload: bool):
        if not self._active_preset:
            raise DataManagementError("cannot set autoload status: Preset is not set")

        self._autoload = autoload
        self.emit_autoload_changed()

    def get_uinputs(self):
        self.event_handler.emit(
            EventEnum.uinputs_changed, uinputs=global_uinputs.devices.copy()
        )

    def save(self):
        if self._active_preset:
            self._active_preset.save()
