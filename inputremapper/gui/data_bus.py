import os.path
import re
import traceback
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, Set, Protocol, Tuple, Deque, Optional, List

from inputremapper.event_combination import EventCombination
from inputremapper.logger import logger


class MassageType(Enum):
    reset_gui = "reset_gui"

    groups = "groups"
    group = "group"
    preset = "preset"
    mapping = "mapping"
    combination_changed = "combination_changed"

    # for unit tests:
    test1 = "test1"
    test2 = "test2"


class MassageData(Protocol):
    massage_type: MassageType


# useful type aliases
MassageListener = Callable[[MassageData], None]
Name = str


class DataBus:
    shorten_path = re.compile("inputremapper/")

    def __init__(self):
        self._listeners: Dict[MassageType, Set[MassageListener]] = defaultdict(set)
        self._massages: Deque[Tuple[MassageData, str, int]] = deque()
        self._sending = False

    def send(self, data: MassageData):
        """schedule a massage to be sent.
        The massage will be sent after all currently pending massages are sent"""
        self._massages.append((data, *self.get_caller()))
        self._send_all()

    def _send(self, data: MassageData, file: str, line: int):
        logger.debug(f"from {file}:{line}: sending {data}")
        for listener in self._listeners[data.massage_type]:
            listener(data)

    def _send_all(self):
        """send all scheduled messages in order"""
        if self._sending:
            # don't run this twice, so we not mess up te order
            return

        self._sending = True
        try:
            while self._massages:
                self._send(*self._massages.popleft())
        finally:
            self._sending = False

    def subscribe(
        self, massage_type: MassageType, listener: Callable[[MassageData], None]
    ):
        """attach a listener to an event.
        The listener can optionally return a callable which
        will be called after all other listeners have been called"""
        logger.debug("adding new EventListener: %s", listener)
        self._listeners[massage_type].add(listener)
        return self

    @staticmethod
    def get_caller(position: int = 3) -> Tuple[str, int]:
        """extract a file and line from current stack and format for logging"""
        tb = traceback.extract_stack(limit=position)[0]
        return os.path.basename(tb.filename), tb.lineno

    def unsubscribe(self, listener: MassageListener) -> None:
        for listeners in self._listeners.values():
            try:
                listeners.remove(listener)
            except KeyError:
                pass


@dataclass(frozen=True)
class GroupData:
    massage_type = MassageType.group
    group_key: str
    presets: Tuple[str, ...]


@dataclass(frozen=True)
class PresetData:
    massage_type = MassageType.preset
    name: Optional[Name]
    mappings: Optional[Tuple[Tuple[Name, EventCombination]]]
    autoload: bool = False


@dataclass(frozen=True)
class CombinationUpdate:
    massage_type = MassageType.combination_changed
    old_combination: EventCombination
    new_combination: EventCombination
