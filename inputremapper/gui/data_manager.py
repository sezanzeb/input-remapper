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

import glob
import os
import re
import time
from typing import Optional, List, Tuple, Set

import gi
from gi.repository import GLib

from inputremapper.configs.global_config import GlobalConfig
from inputremapper.configs.mapping import UIMapping, MappingData
from inputremapper.configs.paths import get_preset_path, mkdir, split_all
from inputremapper.configs.preset import Preset
from inputremapper.configs.system_mapping import SystemMapping
from inputremapper.daemon import DaemonProxy
from inputremapper.configs.input_config import InputCombination, InputConfig
from inputremapper.exceptions import DataManagementError
from inputremapper.gui.gettext import _
from inputremapper.groups import _Group
from inputremapper.gui.messages.message_broker import (
    MessageBroker,
)
from inputremapper.gui.messages.message_data import (
    UInputsData,
    GroupData,
    PresetData,
    CombinationUpdate,
)
from inputremapper.gui.reader_client import ReaderClient
from inputremapper.injection.global_uinputs import GlobalUInputs
from inputremapper.injection.injector import (
    InjectorState,
    InjectorStateMessage,
)
from inputremapper.logger import logger

DEFAULT_PRESET_NAME = _("new preset")

# useful type aliases
Name = str
GroupKey = str


class DataManager:
    """DataManager provides an interface to create and modify configurations as well
    as modify the state of the Service.

    Any state changes will be announced via the MessageBroker.
    """

    def __init__(
        self,
        message_broker: MessageBroker,
        config: GlobalConfig,
        reader_client: ReaderClient,
        daemon: DaemonProxy,
        uinputs: GlobalUInputs,
        system_mapping: SystemMapping,
    ):
        self.message_broker = message_broker
        self._reader_client = reader_client
        self._daemon = daemon
        self._uinputs = uinputs
        self._system_mapping = system_mapping
        uinputs.prepare_all()

        self._config = config
        self._config.load_config()

        self._active_preset: Optional[Preset[UIMapping]] = None
        self._active_mapping: Optional[UIMapping] = None
        self._active_input_config: Optional[InputConfig] = None

    def publish_group(self):
        """Send active group to the MessageBroker.

        This is internally called whenever the group changes.
        It is usually not necessary to call this explicitly from
        outside DataManager.
        """
        self.message_broker.publish(
            GroupData(self.active_group.key, self.get_preset_names())
        )

    def publish_preset(self):
        """Send active preset to the MessageBroker.

        This is internally called whenever the preset changes.
        It is usually not necessary to call this explicitly from
        outside DataManager.
        """
        self.message_broker.publish(
            PresetData(
                self.active_preset.name, self.get_mappings(), self.get_autoload()
            )
        )

    def publish_mapping(self):
        """Send active mapping to the MessageBroker

        This is internally called whenever the mapping changes.
        It is usually not necessary to call this explicitly from
        outside DataManager.
        """
        if self.active_mapping:
            self.message_broker.publish(self.active_mapping.get_bus_message())

    def publish_event(self):
        """Send active event to the MessageBroker.

        This is internally called whenever the event changes.
        It is usually not necessary to call this explicitly from
        outside DataManager
        """
        if self.active_input_config:
            assert self.active_input_config in self.active_mapping.input_combination
            self.message_broker.publish(self.active_input_config)

    def publish_uinputs(self):
        """Send the "uinputs" message on the MessageBroker."""
        self.message_broker.publish(
            UInputsData(
                {
                    name: uinput.capabilities()
                    for name, uinput in self._uinputs.devices.items()
                }
            )
        )

    def publish_groups(self):
        """Publish the "groups" message on the MessageBroker."""
        self._reader_client.publish_groups()

    def publish_injector_state(self):
        """Publish the "injector_state" message for the active_group."""
        if not self.active_group:
            return

        self.message_broker.publish(InjectorStateMessage(self.get_state()))

    @property
    def active_group(self) -> Optional[_Group]:
        """The currently loaded group."""
        return self._reader_client.group

    @property
    def active_preset(self) -> Optional[Preset[UIMapping]]:
        """The currently loaded preset."""
        return self._active_preset

    @property
    def active_mapping(self) -> Optional[UIMapping]:
        """The currently loaded mapping."""
        return self._active_mapping

    @property
    def active_input_config(self) -> Optional[InputConfig]:
        """The currently loaded event."""
        return self._active_input_config

    def get_group_keys(self) -> Tuple[GroupKey, ...]:
        """Get all group keys (plugged devices)."""
        return tuple(group.key for group in self._reader_client.groups.filter())

    def get_preset_names(self) -> Tuple[Name, ...]:
        """Get all preset names for active_group and current user sorted by age."""
        if not self.active_group:
            raise DataManagementError("Cannot find presets: Group is not set")
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

    def get_mappings(self) -> Optional[List[MappingData]]:
        """All mappings from the active_preset."""
        if not self._active_preset:
            return None

        return [mapping.get_bus_message() for mapping in self._active_preset]

    def get_autoload(self) -> bool:
        """The autoload status of the active_preset."""
        if not self.active_preset or not self.active_group:
            return False
        return self._config.is_autoloaded(
            self.active_group.key, self.active_preset.name
        )

    def set_autoload(self, status: bool):
        """Set the autoload status of the active_preset.

        Will send "preset" message on the MessageBroker.
        """
        if not self.active_preset or not self.active_group:
            raise DataManagementError("Cannot set autoload status: Preset is not set")

        if status:
            self._config.set_autoload_preset(
                self.active_group.key, self.active_preset.name
            )
        elif self.get_autoload():
            self._config.set_autoload_preset(self.active_group.key, None)

        self.publish_preset()

    def get_newest_group_key(self) -> GroupKey:
        """group_key of the group with the most recently modified preset."""
        paths = []
        for path in glob.glob(os.path.join(get_preset_path(), "*/*.json")):
            if self._reader_client.groups.find(key=split_all(path)[-2]):
                paths.append((path, os.path.getmtime(path)))

        if not paths:
            raise FileNotFoundError()

        path, _ = max(paths, key=lambda x: x[1])
        return split_all(path)[-2]

    def get_newest_preset_name(self) -> Name:
        """Preset name of the most recently modified preset in the active group."""
        if not self.active_group:
            raise DataManagementError("Cannot find newest preset: Group is not set")

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
        """The first available preset in the active group."""
        if not self.active_group:
            raise DataManagementError("Unable find preset name. Group is not set")

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
        """Load a group. will publish "groups" and "injector_state" messages.

        This will render the active_mapping and active_preset invalid.
        """
        if group_key not in self.get_group_keys():
            raise DataManagementError("Unable to load non existing group")

        logger.info('Loading group "%s"', group_key)

        self._active_input_config = None
        self._active_mapping = None
        self._active_preset = None
        group = self._reader_client.groups.find(key=group_key)
        self._reader_client.set_group(group)
        self.publish_group()
        self.publish_injector_state()

    def load_preset(self, name: str):
        """Load a preset. Will send "preset" message on the MessageBroker.

        This will render the active_mapping invalid.
        """
        if not self.active_group:
            raise DataManagementError("Unable to load preset. Group is not set")

        logger.info('Loading preset "%s"', name)

        preset_path = get_preset_path(self.active_group.name, name)
        preset = Preset(preset_path, mapping_factory=UIMapping)
        preset.load()
        self._active_input_config = None
        self._active_mapping = None
        self._active_preset = preset
        self.publish_preset()

    def load_mapping(self, combination: InputCombination):
        """Load a mapping. Will send "mapping" message on the MessageBroker."""
        if not self._active_preset:
            raise DataManagementError("Unable to load mapping. Preset is not set")

        mapping = self._active_preset.get_mapping(combination)
        if not mapping:
            msg = (
                f"the mapping with {combination = } does not "
                f"exist in the {self._active_preset.path}"
            )
            logger.error(msg)
            raise KeyError(msg)

        self._active_input_config = None
        self._active_mapping = mapping
        self.publish_mapping()

    def load_input_config(self, input_config: InputConfig):
        """Load a InputConfig from the combination in the active mapping.

        Will send "event" message on the MessageBroker,
        """
        if not self.active_mapping:
            raise DataManagementError("Unable to load event. Mapping is not set")
        if input_config not in self.active_mapping.input_combination:
            raise ValueError(
                f"{input_config} is not member of active_mapping.input_combination: "
                f"{self.active_mapping.input_combination}"
            )
        self._active_input_config = input_config
        self.publish_event()

    def rename_preset(self, new_name: str):
        """Rename the current preset and move the correct file.

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
        self.publish_group()
        self.publish_preset()

    def copy_preset(self, name: str):
        """Copy the current preset to the given name.

        Will send "group" and "preset" message to the MessageBroker and load the copy
        """
        # todo: Do we want to load the copy here? or is this up to the controller?
        if not self.active_preset or not self.active_group:
            raise DataManagementError("Unable to copy preset: Preset is not set")

        if self.active_preset.path == get_preset_path(self.active_group.name, name):
            return

        if name in self.get_preset_names():
            raise ValueError(f"a preset with the name {name} already exits")

        new_path = get_preset_path(self.active_group.name, name)
        logger.info('Copy "%s" to "%s"', self.active_preset.path, new_path)
        self.active_preset.path = new_path
        self.save()
        self.publish_group()
        self.publish_preset()

    def create_preset(self, name: str):
        """Create empty preset in the active_group.

        Will send "group" message to the MessageBroker
        """
        if not self.active_group:
            raise DataManagementError("Unable to add preset. Group is not set")

        path = get_preset_path(self.active_group.name, name)
        if os.path.exists(path):
            raise DataManagementError("Unable to add preset. Preset exists")

        Preset(path).save()
        self.publish_group()

    def delete_preset(self):
        """Delete the active preset.

        Will send "group" message to the MessageBroker
        this will invalidate the active mapping,
        """
        preset_path = self._active_preset.path
        logger.info('Removing "%s"', preset_path)
        os.remove(preset_path)
        self._active_mapping = None
        self._active_preset = None
        self.publish_group()

    def update_mapping(self, **kwargs):
        """Update the active mapping with the given keywords and values.

        Will send "mapping" message to the MessageBroker. In case of a new
        input_combination. This will first send a "combination_update" message.
        """
        if not self._active_mapping:
            raise DataManagementError("Cannot modify Mapping: Mapping is not set")

        if symbol := kwargs.get("output_symbol"):
            kwargs["output_symbol"] = self._system_mapping.correct_case(symbol)

        combination = self.active_mapping.input_combination
        for key, value in kwargs.items():
            setattr(self._active_mapping, key, value)

        if (
            "input_combination" in kwargs
            and combination != self.active_mapping.input_combination
        ):
            self._active_input_config = None
            self.message_broker.publish(
                CombinationUpdate(combination, self._active_mapping.input_combination)
            )

        if "mapping_type" in kwargs:
            # mapping_type must be the last update because it is automatically updated
            # by a validation function
            self._active_mapping.mapping_type = kwargs["mapping_type"]

        self.publish_mapping()

    def update_input_config(self, new_input_config: InputConfig):
        """Update the active input configuration.

        Will send "combination_update", "mapping" and "event" messages to the
        MessageBroker (in that order)
        """
        if not self.active_mapping or not self.active_input_config:
            raise DataManagementError("Cannot modify event: Event is not set")

        combination = list(self.active_mapping.input_combination)
        combination[combination.index(self.active_input_config)] = new_input_config
        self.update_mapping(input_combination=InputCombination(combination))
        self._active_input_config = new_input_config
        self.publish_event()

    def create_mapping(self):
        """Create empty mapping in the active preset.

        Will send "preset" message to the MessageBroker
        """
        if not self._active_preset:
            raise DataManagementError("Cannot create mapping: Preset is not set")
        self._active_preset.add(UIMapping())
        self.publish_preset()

    def delete_mapping(self):
        """Delete the active mapping.

        Will send "preset" message to the MessageBroker
        """
        if not self._active_mapping:
            raise DataManagementError(
                "cannot delete active mapping: active mapping is not set"
            )

        self._active_preset.remove(self._active_mapping.input_combination)
        self._active_mapping = None
        self.publish_preset()

    def save(self):
        """Save the active preset."""
        if self._active_preset:
            self._active_preset.save()

    def refresh_groups(self):
        """Refresh the groups (plugged devices).

        Should send "groups" message to MessageBroker this will not happen immediately
        because the system might take a bit until the groups are available
        """
        self._reader_client.refresh_groups()

    def start_combination_recording(self):
        """Record user input.

        Will send "combination_recorded" messages as new input arrives.
        Will eventually send a "recording_finished" message.
        """
        self._reader_client.start_recorder()

    def stop_combination_recording(self):
        """Stop recording user input.

        Will send a recording_finished signal if a recording is running.
        """
        self._reader_client.stop_recorder()

    def stop_injecting(self) -> None:
        """Stop injecting for the active group.

        Will send "injector_state" message once the injector has stopped."""
        if not self.active_group:
            raise DataManagementError("Cannot stop injection: Group is not set")
        self._daemon.stop_injecting(self.active_group.key)
        self.do_when_injector_state(
            {InjectorState.STOPPED}, self.publish_injector_state
        )

    def start_injecting(self) -> bool:
        """Start injecting the active preset for the active group.

        returns if the startup was successfully initialized.
        Will send "injector_state" message once the startup is complete.
        """
        if not self.active_preset or not self.active_group:
            raise DataManagementError("Cannot start injection: Preset is not set")

        self._daemon.set_config_dir(self._config.get_dir())
        assert self.active_preset.name is not None
        if self._daemon.start_injecting(self.active_group.key, self.active_preset.name):
            self.do_when_injector_state(
                {
                    InjectorState.RUNNING,
                    InjectorState.FAILED,
                    InjectorState.NO_GRAB,
                    InjectorState.UPGRADE_EVDEV,
                },
                self.publish_injector_state,
            )
            return True
        return False

    def get_state(self) -> InjectorState:
        """The state of the injector."""
        if not self.active_group:
            raise DataManagementError("Cannot read state: Group is not set")
        return self._daemon.get_state(self.active_group.key)

    def refresh_service_config_path(self):
        """Tell the service to refresh its config path."""
        self._daemon.set_config_dir(self._config.get_dir())

    def do_when_injector_state(self, states: Set[InjectorState], callback):
        """Run callback once the injector state is one of states."""
        start = time.time()

        def do():
            if time.time() - start > 3:
                # something went wrong, there should have been a state long ago.
                # the timeout prevents tons of GLib.timeouts to run forever, especially
                # after spamming the "Stop" button.
                logger.error("Timed out while waiting for injector state %s", states)
                return False

            if self.get_state() in states:
                callback()
                return False
            return True

        GLib.timeout_add(100, do)
