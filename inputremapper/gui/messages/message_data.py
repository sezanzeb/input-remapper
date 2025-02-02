# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2025 sezanzeb <b8x45ygc9@mozmail.com>
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

import re
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, Callable

from inputremapper.configs.input_config import InputCombination
from inputremapper.configs.mapping import MappingData
from inputremapper.gui.messages.message_types import (
    MessageType,
    Name,
    Capabilities,
    Key,
    DeviceTypes,
)


@dataclass(frozen=True)
class UInputsData:
    message_type = MessageType.uinputs
    uinputs: Dict[Name, Capabilities]

    def __str__(self):
        string = f"{self.__class__.__name__}(uinputs={self.uinputs})"

        # find all sequences of comma+space separated numbers, and shorten them
        # to the first and last number
        all_matches = list(re.finditer("(\d+, )+", string))
        all_matches.reverse()
        for match in all_matches:
            start = match.start()
            end = match.end()
            start += string[start:].find(",") + 2
            if start == end:
                continue
            string = f"{string[:start]}... {string[end:]}"

        return string


@dataclass(frozen=True)
class GroupsData:
    """Message containing all available groups and their device types."""

    message_type = MessageType.groups
    groups: Dict[Key, DeviceTypes]


@dataclass(frozen=True)
class GroupData:
    """Message with the active group and available presets for the group."""

    message_type = MessageType.group
    group_key: str
    presets: Tuple[str, ...]


@dataclass(frozen=True)
class PresetData:
    """Message with the active preset name and mapping names/combinations."""

    message_type = MessageType.preset
    name: Optional[Name]
    mappings: Optional[Tuple[MappingData, ...]]
    autoload: bool = False


@dataclass(frozen=True)
class StatusData:
    """Message with the strings and id for the status bar."""

    message_type = MessageType.status_msg
    ctx_id: int
    msg: Optional[str] = None
    tooltip: Optional[str] = None


@dataclass(frozen=True)
class CombinationRecorded:
    """Message with the latest recoded combination."""

    message_type = MessageType.combination_recorded
    combination: "InputCombination"


@dataclass(frozen=True)
class CombinationUpdate:
    """Message with the old and new combination (hash for a mapping) when it changed."""

    message_type = MessageType.combination_update
    old_combination: "InputCombination"
    new_combination: "InputCombination"


@dataclass(frozen=True)
class UserConfirmRequest:
    """Message for requesting a user response (confirm/cancel) from the gui."""

    message_type = MessageType.user_confirm_request
    msg: str
    respond: Callable[[bool], None] = lambda _: None


@dataclass(frozen=True)
class DoStackSwitch:
    """Command the stack to switch to a different page."""

    message_type = MessageType.do_stack_switch
    page_index: int
