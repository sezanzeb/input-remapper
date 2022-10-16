import re
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, Callable

from inputremapper.configs.mapping import MappingData
from inputremapper.event_combination import EventCombination
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
        all_matches = [m for m in re.finditer("(\d+, )+", string)]
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
    """Message containing all available groups and their device types"""

    message_type = MessageType.groups
    groups: Dict[Key, DeviceTypes]


@dataclass(frozen=True)
class GroupData:
    """Message with the active group and available presets for the group"""

    message_type = MessageType.group
    group_key: str
    presets: Tuple[str, ...]


@dataclass(frozen=True)
class PresetData:
    """Message with the active preset name and mapping names/combinations"""

    message_type = MessageType.preset
    name: Optional[Name]
    mappings: Optional[Tuple[MappingData, ...]]
    autoload: bool = False


@dataclass(frozen=True)
class StatusData:
    """Message with the strings and id for the status bar"""

    message_type = MessageType.status_msg
    ctx_id: int
    msg: Optional[str] = None
    tooltip: Optional[str] = None


@dataclass(frozen=True)
class CombinationRecorded:
    """Message with the latest recoded combination"""

    message_type = MessageType.combination_recorded
    combination: "EventCombination"


@dataclass(frozen=True)
class CombinationUpdate:
    """Message with the old and new combination (hash for a mapping) when it changed"""

    message_type = MessageType.combination_update
    old_combination: "EventCombination"
    new_combination: "EventCombination"


@dataclass(frozen=True)
class UserConfirmRequest:
    """Message for requesting a user response (confirm/cancel) from the gui"""

    message_type = MessageType.user_confirm_request
    msg: str
    respond: Callable[[bool], None] = lambda _: None


@dataclass(frozen=True)
class DoStackSwitch:
    """Command the stack to switch to a different page."""

    message_type = MessageType.do_stack_switch
    page_index: int
