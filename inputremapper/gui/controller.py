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

from __future__ import annotations  # needed for the TYPE_CHECKING import

import re
from functools import partial
from typing import (
    TYPE_CHECKING,
    Optional,
    Union,
    Literal,
    Sequence,
    Dict,
    Callable,
    List,
    Any,
)

import gi
from evdev.ecodes import EV_KEY, EV_REL, EV_ABS

from gi.repository import Gtk

from inputremapper.configs.mapping import (
    MappingData,
    UIMapping,
    MacroButTypeOrCodeSetError,
    SymbolAndCodeMismatchError,
    MissingOutputAxisError,
    MissingMacroOrKeyError,
    OutputSymbolVariantError,
)
from inputremapper.configs.paths import sanitize_path_component
from inputremapper.configs.input_config import InputCombination, InputConfig
from inputremapper.configs.validation_errors import pydantify
from inputremapper.exceptions import DataManagementError
from inputremapper.gui.data_manager import DataManager, DEFAULT_PRESET_NAME
from inputremapper.gui.gettext import _
from inputremapper.gui.messages.message_broker import (
    MessageBroker,
    MessageType,
)
from inputremapper.gui.messages.message_data import (
    PresetData,
    StatusData,
    CombinationRecorded,
    UserConfirmRequest,
    DoStackSwitch,
)
from inputremapper.gui.utils import CTX_APPLY, CTX_ERROR, CTX_WARNING, CTX_MAPPING
from inputremapper.injection.injector import (
    InjectorState,
    InjectorStateMessage,
)
from inputremapper.logger import logger

if TYPE_CHECKING:
    # avoids gtk import error in tests
    from inputremapper.gui.user_interface import UserInterface


MAPPING_DEFAULTS = {"target_uinput": "keyboard"}


class Controller:
    """Implements the behaviour of the gui."""

    def __init__(self, message_broker: MessageBroker, data_manager: DataManager):
        self.message_broker = message_broker
        self.data_manager = data_manager
        self.gui: Optional[UserInterface] = None

        self.button_left_warn = False
        self._attach_to_events()

    def set_gui(self, gui: UserInterface):
        """Let the Controller know about the user interface singleton.."""
        self.gui = gui

    def _attach_to_events(self) -> None:
        self.message_broker.subscribe(MessageType.groups, self._on_groups_changed)
        self.message_broker.subscribe(MessageType.preset, self._on_preset_changed)
        self.message_broker.subscribe(MessageType.init, self._on_init)
        self.message_broker.subscribe(
            MessageType.preset, self._publish_mapping_errors_as_status_msg
        )
        self.message_broker.subscribe(
            MessageType.mapping, self._publish_mapping_errors_as_status_msg
        )

    def _on_init(self, __):
        """Initialize the gui and the data_manager."""
        # make sure we get a groups_changed event when everything is ready
        # this might not be necessary if the reader-service takes longer to provide the
        # initial groups
        self.data_manager.publish_groups()
        self.data_manager.publish_uinputs()

    def _on_groups_changed(self, _):
        """Load the newest group as soon as everyone got notified
        about the updated groups."""

        if self.data_manager.active_group is not None:
            # don't jump to a different group and preset suddenly, if the user
            # is already looking at one
            logger.debug("A group is already active")
            return

        group_key = self.get_a_group()
        if group_key is None:
            logger.debug("Could not find a group")
            return

        self.load_group(group_key)

    def _on_preset_changed(self, data: PresetData):
        """Load a mapping as soon as everyone got notified about the new preset."""
        if data.mappings:
            mappings = list(data.mappings)
            mappings.sort(
                key=lambda mapping: (
                    mapping.format_name() or mapping.input_combination.beautify()
                )
            )
            combination = mappings[0].input_combination
            self.load_mapping(combination)
            self.load_input_config(combination[0])
        else:
            # send an empty mapping to make sure the ui is reset to default values
            self.message_broker.publish(MappingData(**MAPPING_DEFAULTS))

    def _on_combination_recorded(self, data: CombinationRecorded):
        combination = self._auto_use_as_analog(data.combination)
        self.update_combination(combination)

    def _publish_mapping_errors_as_status_msg(self, *__):
        """Send mapping ValidationErrors to the MessageBroker."""
        if not self.data_manager.active_preset:
            return

        if self.data_manager.active_preset.is_valid():
            self.message_broker.publish(StatusData(CTX_MAPPING))
            return

        for mapping in self.data_manager.active_preset:
            if not mapping.get_error():
                continue

            position = mapping.format_name()
            error_strings = self._get_ui_error_strings(mapping)
            tooltip = ""
            if len(error_strings) == 0:
                # shouldn't be possible to get to this point
                logger.error("Expected an error")
                return
            elif len(error_strings) > 1:
                msg = _('%d Mapping errors at "%s", hover for info') % (
                    len(error_strings),
                    position,
                )
                tooltip = "– " + "\n– ".join(error_strings)
            else:
                msg = f'"{position}": {error_strings[0]}'
                tooltip = error_strings[0]

            self.show_status(
                CTX_MAPPING,
                msg.replace("\n", " "),
                tooltip,
            )

    @staticmethod
    def format_error_message(mapping, error_type, error_message: str) -> str:
        """Check all the different error messages which are not useful for the user."""
        # There is no more elegant way of comparing error_type with the base class.
        # https://github.com/pydantic/pydantic/discussions/5112
        if (
            pydantify(MacroButTypeOrCodeSetError) in error_type
            or pydantify(SymbolAndCodeMismatchError) in error_type
        ) and mapping.input_combination.defines_analog_input:
            return _(
                "Remove the macro or key from the macro input field "
                "when specifying an analog output"
            )

        if (
            pydantify(MacroButTypeOrCodeSetError) in error_type
            or pydantify(SymbolAndCodeMismatchError) in error_type
        ) and not mapping.input_combination.defines_analog_input:
            return _(
                "Remove the Analog Output Axis when specifying a macro or key output"
            )

        if pydantify(MissingOutputAxisError) in error_type:
            error_message = _(
                "The input specifies an analog axis, but no output axis is selected."
            )
            if mapping.output_symbol is not None:
                event = [
                    event
                    for event in mapping.input_combination
                    if event.defines_analog_input
                ][0]
                error_message += _(
                    "\nIf you mean to create a key or macro mapping "
                    "go to the advanced input configuration"
                    ' and set a "Trigger Threshold" for '
                    f'"{event.description()}"'
                )
            return error_message

        if (
            pydantify(MissingMacroOrKeyError) in error_type
            and mapping.output_symbol is None
        ):
            error_message = _(
                "The input specifies a key or macro input, but no macro or key is "
                "programmed."
            )
            if mapping.output_type in (EV_ABS, EV_REL):
                error_message += _(
                    "\nIf you mean to create an analog axis mapping go to the "
                    'advanced input configuration and set an input to "Use as Analog".'
                )
            return error_message

        return error_message

    @staticmethod
    def _get_ui_error_strings(mapping: UIMapping) -> List[str]:
        """Get a human readable error message from a mapping error."""
        validation_error = mapping.get_error()

        if validation_error is None:
            return []

        formatted_errors = []

        for error in validation_error.errors():
            if pydantify(OutputSymbolVariantError) in error["type"]:
                # this is rather internal, when this error appears in the gui, there is
                # also always another more readable error at the same time that explains
                # this problem.
                continue

            error_string = f'"{mapping.format_name()}": '
            error_message = error["msg"]
            error_location = error["loc"][0]
            if error_location != "__root__":
                error_string += f"{error_location}: "

            # check all the different error messages which are not useful for the user
            formatted_errors.append(
                Controller.format_error_message(
                    mapping,
                    error["type"],
                    error_message,
                )
            )

        return formatted_errors

    def get_a_preset(self) -> str:
        """Attempts to get the newest preset in the current group
        creates a new preset if that fails."""
        try:
            return self.data_manager.get_newest_preset_name()
        except FileNotFoundError:
            pass
        self.data_manager.create_preset(self.data_manager.get_available_preset_name())
        return self.data_manager.get_newest_preset_name()

    def get_a_group(self) -> Optional[str]:
        """Attempts to get the group with the newest preset
        returns any if that fails."""
        try:
            return self.data_manager.get_newest_group_key()
        except FileNotFoundError:
            pass

        keys = self.data_manager.get_group_keys()
        return keys[0] if keys else None

    def copy_preset(self):
        """Create a copy of the active preset and name it `preset_name copy`."""
        name = self.data_manager.active_preset.name
        match = re.search(" copy *\d*$", name)
        if match:
            name = name[: match.start()]

        self.data_manager.copy_preset(
            self.data_manager.get_available_preset_name(f"{name} copy")
        )
        self.message_broker.publish(DoStackSwitch(1))

    def _auto_use_as_analog(self, combination: InputCombination) -> InputCombination:
        """If output is analog, set the first fitting input to analog."""
        if self.data_manager.active_mapping is None:
            return combination

        if not self.data_manager.active_mapping.is_analog_output():
            return combination

        if combination.find_analog_input_config():
            # something is already set to do that
            return combination

        for i, input_config in enumerate(combination):
            # find the first analog input and set it to "use as analog"
            if input_config.type in (EV_ABS, EV_REL):
                logger.info("Using %s as analog input", input_config)

                # combinations and input_configs are immutable, a new combination
                # is created to fit the needs instead
                combination_list = list(combination)
                combination_list[i] = input_config.modify(analog_threshold=0)
                new_combination = InputCombination(combination_list)
                return new_combination

        return combination

    def update_combination(self, combination: InputCombination):
        """Update the input_combination of the active mapping."""
        combination = self._auto_use_as_analog(combination)

        try:
            self.data_manager.update_mapping(input_combination=combination)
            self.save()
        except KeyError:
            self.show_status(
                CTX_MAPPING,
                f'"{combination.beautify()}" already mapped to something else',
            )
            return

        if combination.is_problematic():
            self.show_status(
                CTX_WARNING,
                _("ctrl, alt and shift may not combine properly"),
                _(
                    "Your system might reinterpret combinations "
                    + "with those after they are injected, and by doing so "
                    + "break them."
                ),
            )

    def move_input_config_in_combination(
        self,
        input_config: InputConfig,
        direction: Union[Literal["up"], Literal["down"]],
    ):
        """Move the active_input_config up or down in the input_combination of the
        active_mapping."""
        if (
            not self.data_manager.active_mapping
            or len(self.data_manager.active_mapping.input_combination) == 1
        ):
            return
        combination: Sequence[
            InputConfig
        ] = self.data_manager.active_mapping.input_combination

        i = combination.index(input_config)
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
                + [input_config]
                + [combination[i - 1]]
                + list(combination[i + 1 :])
            )
        elif direction == "down":
            combination = (
                list(combination[:i])
                + [combination[i + 1]]
                + [input_config]
                + list(combination[i + 2 :])
            )
        else:
            raise ValueError(f"unknown direction: {direction}")
        self.update_combination(InputCombination(combination))
        self.load_input_config(input_config)

    def load_input_config(self, input_config: InputConfig):
        """Load an InputConfig form the active mapping input combination."""
        self.data_manager.load_input_config(input_config)

    def update_input_config(self, new_input_config: InputConfig):
        """Modify the active input configuration."""
        try:
            self.data_manager.update_input_config(new_input_config)
        except KeyError:
            # we need to synchronize the gui
            self.data_manager.publish_mapping()
            self.data_manager.publish_event()

    def remove_event(self):
        """Remove the active InputEvent from the active mapping event combination."""
        if (
            not self.data_manager.active_mapping
            or not self.data_manager.active_input_config
        ):
            return

        combination = list(self.data_manager.active_mapping.input_combination)
        combination.remove(self.data_manager.active_input_config)
        try:
            self.data_manager.update_mapping(
                input_combination=InputCombination(combination)
            )
            self.load_input_config(combination[0])
            self.save()
        except (KeyError, ValueError):
            # we need to synchronize the gui
            self.data_manager.publish_mapping()
            self.data_manager.publish_event()

    def set_event_as_analog(self, analog: bool):
        """Use the active event as an analog input."""
        assert self.data_manager.active_input_config is not None
        event = self.data_manager.active_input_config

        if event.type != EV_KEY:
            if analog:
                try:
                    self.data_manager.update_input_config(
                        event.modify(analog_threshold=0)
                    )
                    self.save()
                    return
                except KeyError:
                    pass
            else:
                try_values = {EV_REL: [1, -1], EV_ABS: [10, -10]}
                for value in try_values[event.type]:
                    try:
                        self.data_manager.update_input_config(
                            event.modify(analog_threshold=value)
                        )
                        self.save()
                        return
                    except KeyError:
                        pass

        # didn't update successfully
        # we need to synchronize the gui
        self.data_manager.publish_mapping()
        self.data_manager.publish_event()

    def load_groups(self):
        """Refresh the groups."""
        self.data_manager.refresh_groups()

    def load_group(self, group_key: str):
        """Load the group and then a preset of that group."""
        self.data_manager.load_group(group_key)
        self.load_preset(self.get_a_preset())

    def load_preset(self, name: str):
        """Load the preset."""
        self.data_manager.load_preset(name)
        # self.load_mapping(...) # not needed because we have on_preset_changed()

    def rename_preset(self, new_name: str):
        """Rename the active_preset."""
        if (
            not self.data_manager.active_preset
            or not new_name
            or new_name == self.data_manager.active_preset.name
        ):
            return

        new_name = sanitize_path_component(new_name)
        new_name = self.data_manager.get_available_preset_name(new_name)
        self.data_manager.rename_preset(new_name)

    def add_preset(self, name: str = DEFAULT_PRESET_NAME):
        """Create a new preset called `new preset n`, add it to the active_group."""
        name = self.data_manager.get_available_preset_name(name)
        try:
            self.data_manager.create_preset(name)
            self.data_manager.load_preset(name)
        except PermissionError as e:
            self.show_status(CTX_ERROR, _("Permission denied!"), str(e))

    def delete_preset(self):
        """Delete the active_preset from the disc."""

        def f(answer: bool):
            if answer:
                self.data_manager.delete_preset()
                self.data_manager.load_preset(self.get_a_preset())
                self.message_broker.publish(DoStackSwitch(1))

        if not self.data_manager.active_preset:
            return
        msg = (
            _('Are you sure you want to delete the preset "%s"?')
            % self.data_manager.active_preset.name
        )
        self.message_broker.publish(UserConfirmRequest(msg, f))

    def load_mapping(self, input_combination: InputCombination):
        """Load the mapping with the given input_combination form the active_preset."""
        self.data_manager.load_mapping(input_combination)
        self.load_input_config(input_combination[0])

    def update_mapping(self, **changes):
        """Update the active_mapping with the given keywords and values."""
        if "mapping_type" in changes.keys():
            if not (changes := self._change_mapping_type(changes)):
                # we need to synchronize the gui
                self.data_manager.publish_mapping()
                self.data_manager.publish_event()
                return

        self.data_manager.update_mapping(**changes)
        self.save()

    def create_mapping(self):
        """Create a new empty mapping in the active_preset."""
        try:
            self.data_manager.create_mapping()
        except KeyError:
            # there is already an empty mapping
            return

        self.data_manager.load_mapping(combination=InputCombination.empty_combination())
        self.data_manager.update_mapping(**MAPPING_DEFAULTS)

    def delete_mapping(self):
        """Remove the active_mapping form the active_preset."""

        def get_answer(answer: bool):
            if answer:
                self.data_manager.delete_mapping()
                self.save()

        if not self.data_manager.active_mapping:
            return
        self.message_broker.publish(
            UserConfirmRequest(
                _("Are you sure you want to delete this mapping?"),
                get_answer,
            )
        )

    def set_autoload(self, autoload: bool):
        """Set the autoload state for the active_preset and active_group."""
        self.data_manager.set_autoload(autoload)
        self.data_manager.refresh_service_config_path()

    def save(self):
        """Save all data to the disc."""
        try:
            self.data_manager.save()
        except PermissionError as e:
            self.show_status(CTX_ERROR, _("Permission denied!"), str(e))

    def start_key_recording(self):
        """Record the input of the active_group

        Updates the active_mapping.input_combination with the recorded events.
        """
        state = self.data_manager.get_state()
        if state == InjectorState.RUNNING or state == InjectorState.STARTING:
            self.data_manager.stop_combination_recording()
            self.message_broker.signal(MessageType.recording_finished)
            self.show_status(CTX_ERROR, _('Use "Stop" to stop before editing'))
            return

        logger.debug("Recording Keys")

        def on_recording_finished(_):
            self.message_broker.unsubscribe(on_recording_finished)
            self.message_broker.unsubscribe(self._on_combination_recorded)
            self.gui.connect_shortcuts()

        self.gui.disconnect_shortcuts()
        self.message_broker.subscribe(
            MessageType.combination_recorded,
            self._on_combination_recorded,
        )
        self.message_broker.subscribe(
            MessageType.recording_finished, on_recording_finished
        )
        self.data_manager.start_combination_recording()

    def stop_key_recording(self):
        """Stop recording the input."""
        logger.debug("Stopping Recording Keys")
        self.data_manager.stop_combination_recording()

    def start_injecting(self):
        """Inject the active_preset for the active_group."""
        if len(self.data_manager.active_preset) == 0:
            logger.error(_("Cannot apply empty preset file"))
            # also helpful for first time use
            self.show_status(CTX_ERROR, _("You need to add mappings first"))
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
            MessageType.injector_state,
            self.show_injector_result,
        )
        self.show_status(CTX_APPLY, _("Starting injection..."))
        if not self.data_manager.start_injecting():
            self.message_broker.unsubscribe(self.show_injector_result)
            self.show_status(
                CTX_APPLY,
                _("Failed to apply preset %s") % self.data_manager.active_preset.name,
            )

    def show_injector_result(self, msg: InjectorStateMessage):
        """Show if the injection was successfully started."""
        self.message_broker.unsubscribe(self.show_injector_result)
        state = msg.state

        def running():
            msg = _("Applied preset %s") % self.data_manager.active_preset.name
            if self.data_manager.active_preset.dangerously_mapped_btn_left():
                msg += _(", CTRL + DEL to stop")
            self.show_status(CTX_APPLY, msg)
            logger.info(
                'Group "%s" is currently mapped', self.data_manager.active_group.key
            )

        assert self.data_manager.active_preset  # make mypy happy
        state_calls: Dict[InjectorState, Callable] = {
            InjectorState.RUNNING: running,
            InjectorState.FAILED: partial(
                self.show_status,
                CTX_ERROR,
                _("Failed to apply preset %s") % self.data_manager.active_preset.name,
            ),
            InjectorState.NO_GRAB: partial(
                self.show_status,
                CTX_ERROR,
                "The device was not grabbed",
                "Either another application is already grabbing it, "
                "your preset doesn't contain anything that is sent by the "
                "device or your preset contains errors",
            ),
            InjectorState.UPGRADE_EVDEV: partial(
                self.show_status,
                CTX_ERROR,
                "Upgrade python-evdev",
                "Your python-evdev version is too old.",
            ),
        }

        if state in state_calls:
            state_calls[state]()

    def stop_injecting(self):
        """Stop injecting any preset for the active_group."""

        def show_result(msg: InjectorStateMessage):
            self.message_broker.unsubscribe(show_result)

            if not msg.inactive():
                # some speculation: there might be unexpected additional status messages
                # with a different state, or the status is wrong because something in
                # the long pipeline of status messages is broken.
                logger.error(
                    "Expected the injection to eventually stop, but got state %s",
                    msg.state,
                )
                return

            self.show_status(CTX_APPLY, _("Stopped the injection"))

        try:
            self.message_broker.subscribe(MessageType.injector_state, show_result)
            self.data_manager.stop_injecting()
        except DataManagementError:
            self.message_broker.unsubscribe(show_result)

    def show_status(
        self, ctx_id: int, msg: Optional[str] = None, tooltip: Optional[str] = None
    ):
        """Send a status message to the ui to show it in the status-bar."""
        self.message_broker.publish(StatusData(ctx_id, msg, tooltip))

    def is_empty_mapping(self) -> bool:
        """Check if the active_mapping is empty."""
        return (
            self.data_manager.active_mapping == UIMapping(**MAPPING_DEFAULTS)
            or self.data_manager.active_mapping is None
        )

    def refresh_groups(self):
        """Reload the connected devices and send them as a groups message.

        Runs asynchronously.
        """
        self.data_manager.refresh_groups()

    def close(self):
        """Safely close the application."""
        logger.debug("Closing Application")
        self.save()
        self.message_broker.signal(MessageType.terminate)
        logger.debug("Quitting")
        Gtk.main_quit()

    def set_focus(self, component):
        """Focus the given component."""
        self.gui.window.set_focus(component)

    def _change_mapping_type(self, changes: Dict[str, Any]):
        """Query the user to update the mapping in order to change the mapping type."""
        mapping = self.data_manager.active_mapping

        if mapping is None:
            return changes

        if changes["mapping_type"] == mapping.mapping_type:
            return changes

        if changes["mapping_type"] == "analog":
            msg = _("You are about to change the mapping to analog.")
            if mapping.output_symbol:
                msg += _('\nThis will remove "{}" ' "from the text input!").format(
                    mapping.output_symbol
                )

            if not [
                input_config
                for input_config in mapping.input_combination
                if input_config.defines_analog_input
            ]:
                # there is no analog input configured, let's try to autoconfigure it
                inputs: List[InputConfig] = list(mapping.input_combination)
                for i, input_config in enumerate(inputs):
                    if input_config.type in [EV_ABS, EV_REL]:
                        inputs[i] = input_config.modify(analog_threshold=0)
                        changes["input_combination"] = InputCombination(inputs)
                        msg += _(
                            '\nThe input "{}" will be used as analog input.'
                        ).format(input_config.description())
                        break
                else:
                    # not possible to autoconfigure inform the user
                    msg += _("\nYou need to record an analog input.")

            elif not mapping.output_symbol:
                return changes

            answer = None

            def get_answer(answer_: bool):
                nonlocal answer
                answer = answer_

            self.message_broker.publish(UserConfirmRequest(msg, get_answer))
            if answer:
                changes["output_symbol"] = None
                return changes
            else:
                return None

        if changes["mapping_type"] == "key_macro":
            try:
                analog_input = tuple(
                    filter(lambda i: i.defines_analog_input, mapping.input_combination)
                )[0]
            except IndexError:
                changes["output_type"] = None
                changes["output_code"] = None
                return changes

            answer = None

            def get_answer(answer_: bool):
                nonlocal answer
                answer = answer_

            self.message_broker.publish(
                UserConfirmRequest(
                    f"You are about to change the mapping to a Key or Macro mapping!\n"
                    f"Go to the advanced input configuration and set a "
                    f'"Trigger Threshold" for "{analog_input.description()}".',
                    get_answer,
                )
            )
            if answer:
                changes["output_type"] = None
                changes["output_code"] = None
                return changes
            else:
                return None

        return changes
