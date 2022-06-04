import unittest
from dataclasses import dataclass

from inputremapper.gui.data_bus import DataBus, MassageType


class Listener:
    def __init__(self):
        self.calls = []

    def __call__(self, data):
        self.calls.append(data)


@dataclass
class Massage:
    massage_type: MassageType
    msg: str


class TestDataBus(unittest.TestCase):
    def test_calls_listeners(self):
        """The correct Listeners get called"""
        data_bus = DataBus()
        listener = Listener()
        data_bus.subscribe(MassageType.test1, listener)
        data_bus.send(Massage(MassageType.test1, "foo"))
        data_bus.send(Massage(MassageType.test2, "bar"))
        self.assertEqual(listener.calls[0], Massage(MassageType.test1, "foo"))

    def test_unsubscribe(self):
        data_bus = DataBus()
        listener = Listener()
        data_bus.subscribe(MassageType.test1, listener)
        data_bus.send(Massage(MassageType.test1, "a"))
        data_bus.unsubscribe(listener)
        data_bus.send(Massage(MassageType.test1, "b"))
        self.assertEqual(len(listener.calls), 1)
        self.assertEqual(listener.calls[0], Massage(MassageType.test1, "a"))

    def test_unsubscribe_unknown_listener(self):
        """nothing happens if we unsubscribe an unknown listener"""
        data_bus = DataBus()
        listener1 = Listener()
        listener2 = Listener()
        data_bus.subscribe(MassageType.test1, listener1)
        data_bus.unsubscribe(listener2)
        data_bus.send(Massage(MassageType.test1, "a"))
        self.assertEqual(listener1.calls[0], Massage(MassageType.test1, "a"))

    def test_preserves_order(self):
        data_bus = DataBus()
        calls = []

        def listener1(_):
            data_bus.send(Massage(MassageType.test2, "f"))
            calls.append(1)

        def listener2(_):
            data_bus.send(Massage(MassageType.test2, "f"))
            calls.append(2)

        def listener3(_):
            data_bus.send(Massage(MassageType.test2, "f"))
            calls.append(3)

        def listener4(_):
            calls.append(4)

        data_bus.subscribe(MassageType.test1, listener1)
        data_bus.subscribe(MassageType.test1, listener2)
        data_bus.subscribe(MassageType.test1, listener3)
        data_bus.subscribe(MassageType.test2, listener4)
        data_bus.send(Massage(MassageType.test1, ""))

        first = calls[:3]
        first.sort()
        self.assertEqual([1, 2, 3], first)
        self.assertEqual([4, 4, 4], calls[3:])
