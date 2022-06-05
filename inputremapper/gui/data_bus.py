import os.path
import re
import traceback
from collections import defaultdict, deque, namedtuple
from dataclasses import dataclass
from enum import Enum
from typing import (
    Callable,
    Dict,
    Set,
    Protocol,
    Tuple,
    Deque,
    Optional,
    List,
    NamedTuple,
)

from inputremapper.event_combination import EventCombination
from inputremapper.logger import logger


class MessageType(Enum):
    reset_gui = "reset_gui"
    init = "init"

    uinputs = "uinputs"
    groups = "groups"
    group = "group"
    preset = "preset"
    mapping = "mapping"
    combination_changed = "combination_changed"
    combination_recorded = "combination_recorded"
    recording_finished = "recording_finished"
    status = "status"

    # for unit tests:
    test1 = "test1"
    test2 = "test2"


class Message(Protocol):
    """the protocol any message must follow to be sent with the DataBus"""

    message_type: MessageType


# useful type aliases
MessageListener = Callable[[Message], None]
Capabilities = Dict[int, List]
Name = str
Key = str
DeviceTypes = List[str]


class DataBus:
    shorten_path = re.compile("inputremapper/")

    def __init__(self):
        self._listeners: Dict[MessageType, Set[MessageListener]] = defaultdict(set)
        self._messages: Deque[Tuple[Message, str, int]] = deque()
        self._sending = False

    def send(self, data: Message):
        """schedule a massage to be sent.
        The message will be sent after all currently pending messages are sent"""
        self._messages.append((data, *self.get_caller()))
        self._send_all()

    def signal(self, signal: MessageType):
        """send a signal without any data payload"""
        self.send(Signal(signal))

    def _send(self, data: Message, file: str, line: int):
        logger.debug(f"from {file}:{line}: Signal={data.message_type.name}:\t{data=}")
        for listener in self._listeners[data.message_type]:
            listener(data)

    def _send_all(self):
        """send all scheduled messages in order"""
        if self._sending:
            # don't run this twice, so we not mess up the order
            return

        self._sending = True
        try:
            while self._messages:
                self._send(*self._messages.popleft())
        finally:
            self._sending = False

    def subscribe(self, massage_type: MessageType, listener: MessageListener):
        """attach a listener to an event"""
        logger.debug("adding new EventListener: %s", listener)
        self._listeners[massage_type].add(listener)
        return self

    @staticmethod
    def get_caller(position: int = 3) -> Tuple[str, int]:
        """extract a file and line from current stack and format for logging"""
        tb = traceback.extract_stack(limit=position)[0]
        return os.path.basename(tb.filename), tb.lineno

    def unsubscribe(self, listener: MessageListener) -> None:
        for listeners in self._listeners.values():
            try:
                listeners.remove(listener)
            except KeyError:
                pass


@dataclass(frozen=True)
class UInputsData:
    message_type = MessageType.uinputs
    uinputs: Dict[Name, Capabilities]


@dataclass(frozen=True)
class GroupsData:
    message_type = MessageType.groups
    groups: Dict[Key, DeviceTypes]


@dataclass(frozen=True)
class GroupData:
    message_type = MessageType.group
    group_key: str
    presets: Tuple[str, ...]


@dataclass(frozen=True)
class PresetData:
    message_type = MessageType.preset
    name: Optional[Name]
    mappings: Optional[Tuple[Tuple[Name, EventCombination]]]
    autoload: bool = False


@dataclass(frozen=True)
class StatusData:
    message_type = MessageType.status
    ctx_id: Optional[int]
    msg: Optional[str]
    tooltip: Optional[str]


@dataclass(frozen=True)
class CombinationUpdate:
    message_type = MessageType.combination_changed
    old_combination: EventCombination
    new_combination: EventCombination


@dataclass(frozen=True)
class CombinationRecorded:
    message_type = MessageType.combination_recorded
    combination: EventCombination


class Signal(Message):
    """Send a Message without any associated data over the MassageBus"""

    def __init__(self, message_type: MessageType):
        self.message_type: MessageType = message_type

    def __str__(self):
        return f"Signal: {self.message_type}"

    def __eq__(self, other):
        return str(self) == str(other)
