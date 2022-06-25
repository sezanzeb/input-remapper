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
import re
import time
from typing import Optional, List, Tuple

from inputremapper.configs.global_config import GlobalConfig
from inputremapper.configs.mapping import UIMapping, MappingData
from inputremapper.configs.preset import Preset
from inputremapper.configs.paths import get_preset_path, mkdir, split_all
from inputremapper.daemon import DaemonProxy
from inputremapper.event_combination import EventCombination
from inputremapper.exceptions import DataManagementError
from inputremapper.groups import _Group
from inputremapper.gui.message_broker import (
    MessageBroker,
    GroupData,
    PresetData,
    StatusData,
    CombinationUpdate,
    UInputsData,
)
from inputremapper.gui.reader import Reader
from inputremapper.gui.utils import CTX_MAPPING, CTX_APPLY
from inputremapper.gui.gettext import _
from inputremapper.injection.global_uinputs import GlobalUInputs
from inputremapper.logger import logger

DEFAULT_PRESET_NAME = "new preset"

# useful type aliases
Name = str
GroupKey = str


class DataManager:
    """provides an interface to create configurations
    and send commands to the service"""

    def __init__(
        self,
        message_broker: MessageBroker,
        config: GlobalConfig,
        reader: Reader,
        daemon: DaemonProxy,
        uinputs: GlobalUInputs,
    ):
        self.message_broker = message_broker
        self._reader = reader
        self._daemon = daemon
        self._uinputs = uinputs
        uinputs.prepare_all()

        self._config = config
        self._config.load_config()

        self._active_preset: Optional[Preset] = None
        self._active_mapping: Optional[UIMapping] = None

    def _send_group(self):
        """send active group to the message_broker"""
        self.message_broker.send(GroupData(self.active_group.key, self.get_presets()))

    def _send_preset(self):
        """send active preset to the message_broker"""
        self.message_broker.send(
            PresetData(
                self.active_preset.name, self.get_mappings(), self.get_autoload()
            )
        )
        self._send_mapping_errors()

    def _send_mapping(self):
        """send active mapping to the message_broker"""
        mapping = self._active_mapping
        if mapping:
            self.message_broker.send(mapping.get_bus_message())
            self._send_mapping_errors()
        else:
            self.message_broker.send(MappingData())

    def _send_mapping_errors(self):
        if not self._active_preset:
            return

        if self._active_preset.is_valid():
            self.message_broker.send(StatusData(CTX_MAPPING))

        for mapping in self._active_preset:
            error = mapping.get_error()
            if not error:
                continue

            position = mapping.name or mapping.event_combination.beautify()
            msg = _("Mapping error at %s, hover for info") % position
            self.message_broker.send(StatusData(CTX_MAPPING, msg, str(error)))

    @property
    def active_group(self) -> Optional[_Group]:
        return self._reader.group

    @property
    def active_preset(self) -> Optional[Preset]:
        return self._active_preset

    @property
    def active_mapping(self) -> Optional[UIMapping]:
        return self._active_mapping

    def get_group_keys(self) -> Tuple[GroupKey, ...]:
        """Get all group keys (plugged devices)"""
        return tuple(group.key for group in self._reader.groups.filter())

    def get_presets(self) -> Tuple[Name, ...]:
        """Get all preset names for active_group and current user,
        starting with the newest."""
        if not self.active_group:
            raise DataManagementError("cannot find presets: Group is not set")
        device_folder = get_preset_path(self.active_group.name)
        mkdir(device_folder)

        paths = glob.glob(os.path.join(device_folder, "*.json"))
        presets = [
            os.path.splitext(os.path.basename(path))[0]
            for path in sorted(paths, key=os.path.getmtime)
        ]
        # the highest timestamp to the front
        presets.reverse()
        return tuple(presets)

    def get_mappings(self) -> Optional[List[Tuple[Optional[Name], EventCombination]]]:
        """all mapping names and their combination from the active_preset"""
        if not self._active_preset:
            return None
        return [
            (mapping.name, mapping.event_combination) for mapping in self._active_preset
        ]

    def get_autoload(self) -> bool:
        """the autoload status of the active_preset"""
        if not self.active_preset or not self.active_group:
            return False
        return self._config.is_autoloaded(
            self.active_group.key, self.active_preset.name
        )

    def set_autoload(self, status: bool):
        """set the autoload status of the active_preset.
        Will send "preset" message on the MessageBroker
        """
        if not self.active_preset or not self.active_group:
            raise DataManagementError("cannot set autoload status: Preset is not set")

        if status:
            self._config.set_autoload_preset(
                self.active_group.key, self.active_preset.name
            )
        elif self.get_autoload:
            self._config.set_autoload_preset(self.active_group.key, None)

        self._send_preset()

    def get_newest_group_key(self) -> GroupKey:
        """group_key of the group with the most recently modified preset"""
        paths = []
        for path in glob.glob(os.path.join(get_preset_path(), "*/*.json")):
            if self._reader.groups.find(key=split_all(path)[-2]):
                paths.append((path, os.path.getmtime(path)))

        if not paths:
            raise FileNotFoundError()

        path, _ = max(paths, key=lambda x: x[1])
        return split_all(path)[-2]

    def get_newest_preset_name(self) -> Name:
        """preset name of the most recently modified preset in the active group"""
        if not self.active_group:
            raise DataManagementError("cannot find newest preset: Group is not set")

        paths = [
            (path, os.path.getmtime(path))
            for path in glob.glob(
                os.path.join(get_preset_path(self.active_group.name), "*.json")
            )
        ]
        if not paths:
            raise FileNotFoundError()

        path, _ = max(paths, key=lambda x: x[1])
        return os.path.split(path)[-1].split(".")[0]

    def get_available_preset_name(self, name=DEFAULT_PRESET_NAME) -> Name:
        """the first available preset in the active group"""
        if not self.active_group:
            raise DataManagementError("unable find preset name. Group is not set")

        name = name.strip()

        # find a name that is not already taken
        if os.path.exists(get_preset_path(self.active_group.name, name)):
            # if there already is a trailing number, increment it instead of
            # adding another one
            match = re.match(r"^(.+) (\d+)$", name)
            if match:
                name = match[1]
                i = int(match[2]) + 1
            else:
                i = 2

            while os.path.exists(
                get_preset_path(self.active_group.name, f"{name} {i}")
            ):
                i += 1

            return f"{name} {i}"

        return name

    def load_group(self, group_key: str):
        """Load a group. will send "groups" message on the MessageBroker

        this will render the active_mapping and active_preset invalid
        """
        if group_key not in self.get_group_keys():
            raise DataManagementError("Unable to load non existing group")

        self._active_mapping = None
        self._active_preset = None
        group = self._reader.groups.find(key=group_key)
        self._reader.set_group(group)
        self._send_group()

    def load_preset(self, name: str):
        """Load a preset. Will send "preset" message on the MessageBroker

        this will render the active_mapping invalid
        """
        if not self.active_group:
            raise DataManagementError("Unable to load preset. Group is not set")

        preset_path = get_preset_path(self.active_group.name, name)
        preset = Preset(preset_path, mapping_factory=UIMapping)
        preset.load()
        self._active_mapping = None
        self._active_preset = preset
        self._send_preset()

    def load_mapping(self, combination: EventCombination):
        """Load a mapping. Will send "mapping" message on the MessageBroker"""
        if not self._active_preset:
            raise DataManagementError("Unable to load mapping. Preset is not set")

        mapping = self._active_preset.get_mapping(combination)
        if not mapping:
            raise KeyError(
                f"the mapping with {combination = } does not "
                f"exist in the {self._active_preset.path}"
            )
        self._active_mapping = mapping
        self._send_mapping()

    def rename_preset(self, new_name: str):
        """rename the current preset and move the correct file
        Will send "group" and then "preset" message on the MessageBroker
        """
        if not self.active_preset or not self.active_group:
            raise DataManagementError("Unable rename preset: Preset is not set")

        if self.active_preset.path == get_preset_path(self.active_group.name, new_name):
            return

        old_path = self.active_preset.path
        assert old_path is not None
        old_name = os.path.basename(old_path).split(".")[0]
        new_path = get_preset_path(self.active_group.name, new_name)
        if os.path.exists(new_path):
            raise ValueError(
                f"cannot rename {old_name} to " f"{new_name}, preset already exists"
            )

        logger.info('Moving "%s" to "%s"', old_path, new_path)
        os.rename(old_path, new_path)
        now = time.time()
        os.utime(new_path, (now, now))

        if self._config.is_autoloaded(self.active_group.key, old_name):
            self._config.set_autoload_preset(self.active_group.key, new_name)

        self.active_preset.path = get_preset_path(self.active_group.name, new_name)
        self._send_group()
        self._send_preset()

    def copy_preset(self, name: str):
        """copy the current preset to the given name.
        Will send "group" and "preset" message to the MessageBroker and load the copy
        """
        # todo: Do we want to load the copy here? or is this up to the controller?
        if not self.active_preset or not self.active_group:
            raise DataManagementError("Unable to copy preset: Preset is not set")

        if self.active_preset.path == get_preset_path(self.active_group.name, name):
            return

        if name in self.get_presets():
            raise ValueError(f"a preset with the name {name} already exits")

        new_path = get_preset_path(self.active_group.name, name)
        logger.info('Copy "%s" to "%s"', self.active_preset.path, new_path)
        self.active_preset.path = new_path
        self.save()
        self._send_group()
        self._send_preset()

    def create_preset(self, name: str):
        """create empty preset in the active_group.
        Will send "group" message to the MessageBroker
        """
        if not self.active_group:
            raise DataManagementError("Unable to add preset. Group is not set")

        path = get_preset_path(self.active_group.name, name)
        if os.path.exists(path):
            raise DataManagementError("Unable to add preset. Preset exists")

        Preset(path).save()
        self._send_group()

    def delete_preset(self):
        """delete the active preset
        Will send "group" message to the MessageBroker
        this will invalidate the active mapping,
        """
        preset_path = self._active_preset.path
        logger.info('Removing "%s"', preset_path)
        os.remove(preset_path)
        self._active_mapping = None
        self._active_preset = None
        self._send_group()

    def update_mapping(self, **kwargs):
        """update the active mapping with the given keywords and values.

        Will send "mapping" message to the MessageBroker. In case of a new event_combination
        this will first send a "combination_update" message
        """
        if not self._active_mapping:
            raise DataManagementError("Cannot modify Mapping: mapping is not set")

        combination = self.active_mapping.event_combination
        for key, value in kwargs.items():
            setattr(self._active_mapping, key, value)

        if (
            "event_combination" in kwargs
            and combination != self.active_mapping.event_combination
        ):
            self.message_broker.send(
                CombinationUpdate(combination, self._active_mapping.event_combination)
            )
        self._send_mapping()

    def create_mapping(self):
        """create empty mapping in the active preset.
        Will send "preset" message to the MessageBroker
        """
        if not self._active_preset:
            raise DataManagementError("cannot create mapping: preset is not set")
        self._active_preset.add(UIMapping())
        self._send_preset()

    def delete_mapping(self):
        """delete the active mapping
        Will send "preset" message to the MessageBroker
        """
        if not self._active_mapping:
            raise DataManagementError(
                "cannot delete active mapping: active mapping is not set"
            )

        self._active_preset.remove(self._active_mapping.event_combination)
        self._active_mapping = None
        self._send_preset()

    def send_uinputs(self):
        """send the "uinputs" message on the MessageBroker"""
        self.message_broker.send(
            UInputsData(
                {
                    name: uinput.capabilities()
                    for name, uinput in self._uinputs.devices.items()
                }
            )
        )

    def send_groups(self):
        """send the "groups" message on the MessageBroker"""
        self._reader.send_groups()

    def save(self):
        """save the active preset"""
        if self._active_preset:
            self._active_preset.save()

    def refresh_groups(self):
        """refresh the groups (plugged devices)
        Should send "groups" message to MessageBroker this will not happen immediately
        because the system might take a bit until the groups are available
        """
        self._reader.refresh_groups()

    def start_combination_recording(self):
        """Record user input.

        Will send "combination_recorded" messages as new input arrives.
        Will eventually send a "recording_finished" message.
        """
        self._reader.start_recorder()

    def stop_combination_recording(self):
        """Stop recording user input.

        Will send RecordingFinished message if a recording is running.
        """
        self._reader.stop_recorder()

    def stop_injecting(self) -> None:
        """stop injecting for the active group"""
        if not self.active_group:
            raise DataManagementError("cannot stop injection: group is not set")
        self._daemon.stop_injecting(self.active_group.key)

    def start_injecting(self) -> bool:
        """start injecting the active preset for the active group"""
        if not self.active_preset or not self.active_group:
            raise DataManagementError("cannot start injection: preset is not set")

        self._daemon.set_config_dir(self._config.get_dir())
        assert self.active_preset.name is not None
        return self._daemon.start_injecting(
            self.active_group.key, self.active_preset.name
        )

    def get_state(self) -> int:
        """the state of the injector"""
        if not self.active_group:
            raise DataManagementError("cannot read state: group is not set")
        return self._daemon.get_state(self.active_group.key)

    def refresh_service_config_path(self):
        """tell the service to refresh its config path"""
        self._daemon.set_config_dir(self._config.get_dir())
