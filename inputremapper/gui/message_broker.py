import os.path
import re
import traceback
from collections import defaultdict, deque
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
    Any,
    TYPE_CHECKING,
)

from inputremapper.logger import logger

if TYPE_CHECKING:
    from inputremapper.event_combination import EventCombination


class MessageType(Enum):
    reset_gui = "reset_gui"
    terminate = "terminate"
    init = "init"

    uinputs = "uinputs"
    groups = "groups"
    group = "group"
    preset = "preset"
    mapping = "mapping"
    selected_event = "selected_event"
    combination_recorded = "combination_recorded"
    recording_finished = "recording_finished"
    combination_update = "combination_update"
    status_msg = "status_msg"
    injector_state = "injector_state"

    gui_focus_request = "gui_focus_request"
    user_confirm_request = "user_confirm_request"

    # for unit tests:
    test1 = "test1"
    test2 = "test2"


class Message(Protocol):
    """the protocol any message must follow to be sent with the MessageBroker"""

    message_type: MessageType


# useful type aliases
MessageListener = Callable[[Any], None]
Capabilities = Dict[int, List]
Name = str
Key = str
DeviceTypes = List[str]


class MessageBroker:
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
        logger.debug(f"from {file}:{line}: Signal={data.message_type.name}: {data}")
        for listener in self._listeners[data.message_type].copy():
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
        logger.debug("adding new Listener: %s", listener)
        self._listeners[massage_type].add(listener)
        return self

    @staticmethod
    def get_caller(position: int = 3) -> Tuple[str, int]:
        """extract a file and line from current stack and format for logging"""
        tb = traceback.extract_stack(limit=position)[0]
        return os.path.basename(tb.filename), tb.lineno or 0

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
    mappings: Optional[Tuple[Tuple[Name, "EventCombination"], ...]]
    autoload: bool = False


@dataclass(frozen=True)
class StatusData:
    message_type = MessageType.status_msg
    ctx_id: int
    msg: Optional[str] = None
    tooltip: Optional[str] = None


@dataclass(frozen=True)
class CombinationRecorded:
    message_type = MessageType.combination_recorded
    combination: "EventCombination"


@dataclass(frozen=True)
class CombinationUpdate:
    message_type = MessageType.combination_update
    old_combination: "EventCombination"
    new_combination: "EventCombination"


@dataclass(frozen=True)
class UserConfirmRequest:
    message_type = MessageType.user_confirm_request
    msg: str
    response: Callable[[bool], None] = lambda _: None


class Signal(Message):
    """Send a Message without any associated data over the MassageBus"""

    def __init__(self, message_type: MessageType):
        self.message_type: MessageType = message_type

    def __str__(self):
        return f"Signal: {self.message_type}"

    def __eq__(self, other):
        return str(self) == str(other)
