import enum
from typing import Callable, Awaitable


class GuiEvents(str, enum.Enum):

    # two events for unit tests
    test_ev1 = "test_event1"
    test_ev2 = "test_event2"


GuiEventListener = Callable[[...], Awaitable]


class GuiEventHandler:

    def emit(self, event: GuiEvents, **kwargs) -> None:
        pass

    def emit_blocking(self, event: GuiEvents, **kwargs) -> None:
        pass

    def subscribe(self, event: GuiEvents, listener: GuiEventListener) -> None:
        pass

    def unsubscribe(self, listener: GuiEventListener) -> None:
        pass
