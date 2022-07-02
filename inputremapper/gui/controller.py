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
from __future__ import annotations  # needed for the TYPE_CHECKING import

import re
from functools import partial
from typing import TYPE_CHECKING, Optional, Union, Literal, Sequence, Dict, Callable

from evdev.ecodes import EV_KEY, EV_REL, EV_ABS
from gi.repository import Gtk

from inputremapper.configs.mapping import MappingData, UIMapping
from inputremapper.event_combination import EventCombination
from inputremapper.exceptions import DataManagementError
from inputremapper.gui.data_manager import DataManager, DEFAULT_PRESET_NAME
from inputremapper.gui.gettext import _
from inputremapper.gui.helper import is_helper_running
from inputremapper.gui.utils import CTX_APPLY, CTX_ERROR, CTX_WARNING
from inputremapper.injection.injector import (
    RUNNING,
    FAILED,
    NO_GRAB,
    UPGRADE_EVDEV,
    STARTING,
    STOPPED,
    InjectorState,
)
from inputremapper.input_event import InputEvent
from inputremapper.logger import logger
from inputremapper.gui.message_broker import (
    MessageBroker,
    MessageType,
    PresetData,
    StatusData,
    CombinationRecorded,
    UserConfirmRequest,
)

if TYPE_CHECKING:
    # avoids gtk import error in tests
    from .user_interface import UserInterface


MAPPING_DEFAULTS = {"target_uinput": "keyboard"}


class Controller:
    """implements the behaviour of the gui"""

    def __init__(self, message_broker: MessageBroker, data_manager: DataManager):
        self.message_broker = message_broker
        self.data_manager = data_manager
        self.gui: Optional[UserInterface] = None

        self.button_left_warn = False
        self.attach_to_events()

    def set_gui(self, gui: UserInterface):
        self.gui = gui

    def attach_to_events(self) -> None:
        self.message_broker.subscribe(MessageType.groups, self.on_groups_changed)
        self.message_broker.subscribe(MessageType.preset, self.on_preset_changed)
        self.message_broker.subscribe(MessageType.init, self.on_init)

    def get_a_preset(self) -> str:
        """attempts to get the newest preset in the current group
        creates a new preset if that fails"""
        try:
            return self.data_manager.get_newest_preset_name()
        except FileNotFoundError:
            pass
        self.data_manager.create_preset(self.data_manager.get_available_preset_name())
        return self.data_manager.get_newest_preset_name()

    def get_a_group(self) -> Optional[str]:
        """attempts to get the group with the newest preset
        returns any if that fails"""
        try:
            return self.data_manager.get_newest_group_key()
        except FileNotFoundError:
            pass

        keys = self.data_manager.get_group_keys()
        return keys[0] if keys else None

    def on_init(self, __):
        # make sure we get a groups_changed event when everything is ready
        # this might not be necessary if the helper takes longer to provide the
        # initial groups
        self.data_manager.send_groups()
        self.data_manager.send_uinputs()
        if not is_helper_running():
            self.show_status(CTX_ERROR, _("The helper did not start"))

    def on_groups_changed(self, _):
        """load the newest group as soon as everyone got notified
        about the updated groups"""
        group_key = self.get_a_group()
        if group_key:
            self.load_group(self.get_a_group())

    def on_preset_changed(self, data: PresetData):
        """load a mapping as soon as everyone got notified about the new preset"""
        if data.mappings:
            mappings = list(data.mappings)
            mappings.sort(key=lambda t: t[0] or t[1].beautify())
            combination = mappings[0][1]
            self.load_mapping(combination)
            self.load_event(combination[0])
        else:
            # send an empty mapping to make sure the ui is reset to default values
            self.message_broker.send(MappingData(**MAPPING_DEFAULTS))

    def on_combination_recorded(self, data: CombinationRecorded):
        self.update_combination(data.combination)

    def copy_preset(self):
        name = self.data_manager.active_preset.name
        match = re.search(" copy *\d*$", name)
        if match:
            name = name[: match.start()]

        self.data_manager.copy_preset(
            self.data_manager.get_available_preset_name(f"{name} copy")
        )

    def update_combination(self, combination: EventCombination):
        try:
            self.data_manager.update_mapping(event_combination=combination)
            self.save()
        except KeyError:
            # the combination was a duplicate
            return

        if combination.is_problematic():
            self.show_status(
                CTX_WARNING,
                _("ctrl, alt and shift may not combine properly"),
                _("Your system might reinterpret combinations ")
                + _("with those after they are injected, and by doing so ")
                + _("break them."),
            )

    def move_event_in_combination(
        self, event: InputEvent, direction: Union[Literal["up"], Literal["down"]]
    ):
        """move self.event up or down in the mapping_combination"""
        if (
            not self.data_manager.active_mapping
            or len(self.data_manager.active_mapping.event_combination) == 1
        ):
            return
        combination: Sequence[
            InputEvent
        ] = self.data_manager.active_mapping.event_combination

        i = combination.index(event)
        if (
            i + 1 == len(combination)
            and direction == "down"
            or i == 0
            and direction == "up"
        ):
            return

        if direction == "up":
            combination = (
                list(combination[: i - 1])
                + [event]
                + [combination[i - 1]]
                + list(combination[i + 1 :])
            )
        elif direction == "down":
            combination = (
                list(combination[:i])
                + [combination[i + 1]]
                + [event]
                + list(combination[i + 2 :])
            )
        else:
            raise ValueError(f"unknown direction: {direction}")
        self.update_combination(EventCombination(combination))
        self.load_event(event)

    def load_event(self, event: InputEvent):
        """load an InputEvent form the active mapping event combination"""
        self.data_manager.load_event(event)

    def update_event(self, new_event: InputEvent):
        """modify the active event"""
        try:
            self.data_manager.update_event(new_event)
        except KeyError:
            # we need to synchronize the gui
            self.data_manager.send_mapping()
            self.data_manager.send_event()

    def set_event_as_analog(self, analog: bool):
        """use the active event as an analog input"""
        assert self.data_manager.active_event is not None
        event = self.data_manager.active_event
        if event.type == EV_KEY:
            pass

        elif analog:
            try:
                self.data_manager.update_event(event.modify(value=0))
                return
            except KeyError:
                pass
        else:
            try_values = {EV_REL: [1, -1], EV_ABS: [10, -10]}
            for value in try_values[event.type]:
                try:
                    self.data_manager.update_event(event.modify(value=value))
                    return
                except KeyError:
                    pass

        # didn't update successfully
        # we need to synchronize the gui
        self.data_manager.send_mapping()
        self.data_manager.send_event()

    def load_groups(self):
        """refresh the groups"""
        self.data_manager.refresh_groups()

    def load_group(self, group_key: str):
        """load the group and then a preset of that group"""
        self.data_manager.load_group(group_key)
        self.load_preset(self.get_a_preset())

    def load_preset(self, name: str):
        """load the preset"""
        self.data_manager.load_preset(name)
        # self.load_mapping(...) # not needed because we have on_preset_changed()

    def rename_preset(self, new_name: str):
        if (
            not self.data_manager.active_preset
            or not new_name
            or new_name == self.data_manager.active_preset.name
        ):
            return
        name = self.data_manager.get_available_preset_name(new_name)
        self.data_manager.rename_preset(name)

    def add_preset(self, name: str = DEFAULT_PRESET_NAME):
        name = self.data_manager.get_available_preset_name(name)
        try:
            self.data_manager.create_preset(name)
            self.data_manager.load_preset(name)
        except PermissionError as e:
            self.show_status(CTX_ERROR, _("Permission denied!"), str(e))

    def delete_preset(self):
        def f(answer: bool):
            if answer:
                self.data_manager.delete_preset()
                self.data_manager.load_preset(self.get_a_preset())

        if not self.data_manager.active_preset:
            return
        msg = (
            _("Are you sure you want to delete the \npreset: '%s' ?")
            % self.data_manager.active_preset.name
        )
        self.message_broker.send(UserConfirmRequest(msg, f))

    def load_mapping(self, event_combination: EventCombination):
        self.data_manager.load_mapping(event_combination)
        self.load_event(event_combination[0])

    def update_mapping(self, **kwargs):
        self.data_manager.update_mapping(**kwargs)
        self.save()

    def create_mapping(self):
        try:
            self.data_manager.create_mapping()
        except KeyError:
            # there is already an empty mapping
            return
        self.data_manager.load_mapping(combination=EventCombination.empty_combination())
        self.data_manager.update_mapping(**MAPPING_DEFAULTS)

    def delete_mapping(self):
        def f(answer: bool):
            if answer:
                self.data_manager.delete_mapping()
                self.save()

        if not self.data_manager.active_mapping:
            return
        self.message_broker.send(
            UserConfirmRequest(_("Are you sure you want to delete \nthis mapping?"), f)
        )

    def set_autoload(self, autoload: bool):
        self.data_manager.set_autoload(autoload)
        self.data_manager.refresh_service_config_path()

    def save(self):
        try:
            self.data_manager.save()
        except PermissionError as e:
            self.show_status(CTX_ERROR, _("Permission denied!"), str(e))

    def start_key_recording(self):
        state = self.data_manager.get_state()
        if state == RUNNING or state == STARTING:
            self.message_broker.signal(MessageType.recording_finished)
            self.show_status(
                CTX_ERROR, _('Use "Stop Injection" to stop before editing')
            )
            return

        logger.debug("Recording Keys")

        def f(_):
            self.message_broker.unsubscribe(f)
            self.message_broker.unsubscribe(self.on_combination_recorded)
            self.gui.connect_shortcuts()

        self.gui.disconnect_shortcuts()
        self.message_broker.subscribe(
            MessageType.combination_recorded, self.on_combination_recorded
        )
        self.message_broker.subscribe(MessageType.recording_finished, f)
        self.data_manager.start_combination_recording()

    def stop_key_recording(self):
        logger.debug("Stopping Key recording")
        self.data_manager.stop_combination_recording()

    def start_injecting(self):
        if len(self.data_manager.active_preset) == 0:
            logger.error(_("Cannot apply empty preset file"))
            # also helpful for first time use
            self.show_status(CTX_ERROR, _("You need to add keys and save first"))
            return

        if not self.button_left_warn:
            if self.data_manager.active_preset.dangerously_mapped_btn_left():
                self.show_status(
                    CTX_ERROR,
                    "This would disable your click button",
                    "Map a button to BTN_LEFT to avoid this.\n"
                    "To overwrite this warning, press apply again.",
                )
                self.button_left_warn = True
                return

        # todo: warn about unreleased keys
        self.button_left_warn = False
        self.message_broker.subscribe(
            MessageType.injector_state, self.show_injector_result
        )
        self.show_status(CTX_APPLY, _("Starting injection..."))
        if not self.data_manager.start_injecting():
            self.message_broker.unsubscribe(self.show_injector_result)
            self.show_status(
                CTX_APPLY,
                _("Failed to apply preset %s") % self.data_manager.active_preset.name,
            )

    def show_injector_result(self, msg: InjectorState):
        """Show if the injection was successfully started."""
        self.message_broker.unsubscribe(self.show_injector_result)
        state = msg.state

        def running():
            msg = _("Applied preset %s") % self.data_manager.active_preset.name
            if self.data_manager.active_preset.get_mapping(
                EventCombination(InputEvent.btn_left())
            ):
                msg += _(", CTRL + DEL to stop")
            self.show_status(CTX_APPLY, msg)
            logger.info(
                'Group "%s" is currently mapped', self.data_manager.active_group.key
            )

        assert self.data_manager.active_preset  # make mypy happy
        state_calls: Dict[int, Callable] = {
            RUNNING: running,
            FAILED: partial(
                self.show_status,
                CTX_ERROR,
                _("Failed to apply preset %s") % self.data_manager.active_preset.name,
            ),
            NO_GRAB: partial(
                self.show_status,
                CTX_ERROR,
                "The device was not grabbed",
                "Either another application is already grabbing it or "
                "your preset doesn't contain anything that is sent by the "
                "device.",
            ),
            UPGRADE_EVDEV: partial(
                self.show_status,
                CTX_ERROR,
                "Upgrade python-evdev",
                "Your python-evdev version is too old.",
            ),
        }
        state_calls[state]()

    def stop_injecting(self):
        def show_result(msg: InjectorState):
            self.message_broker.unsubscribe(show_result)
            assert msg.state == STOPPED
            self.show_status(CTX_APPLY, _("Applied the system default"))

        try:
            self.message_broker.subscribe(MessageType.injector_state, show_result)
            self.data_manager.stop_injecting()
        except DataManagementError:
            self.message_broker.unsubscribe(show_result)

    def show_status(
        self, ctx_id: int, msg: Optional[str] = None, tooltip: Optional[str] = None
    ):
        self.message_broker.send(StatusData(ctx_id, msg, tooltip))

    def is_empty_mapping(self) -> bool:
        """check if the active_mapping is empty"""
        return (
            self.data_manager.active_mapping == UIMapping(**MAPPING_DEFAULTS)
            or self.data_manager.active_mapping is None
        )

    def refresh_groups(self):
        self.data_manager.refresh_groups()

    def close(self):
        """safely close the application"""
        logger.debug("Closing Application")
        self.save()
        self.message_broker.signal(MessageType.terminate)
        logger.debug("Quitting")
        Gtk.main_quit()

    def set_focus(self, component):
        """focus the given component"""
        self.gui.window.set_focus(component)
