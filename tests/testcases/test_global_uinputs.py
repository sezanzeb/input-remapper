import sys
import unittest
import evdev

from unittest.mock import patch
from evdev.ecodes import (
    EV_KEY,
    EV_ABS,
    KEY_A,
    ABS_X,
)
from tests.test import cleanup

from inputremapper.injection.global_uinputs import global_uinputs, FrontendUInput, UInput, GlobalUInputs
from inputremapper.exceptions import EventNotHandled, UinputNotAvailable


class TestFrontendUinput(unittest.TestCase):
    def setUp(self) -> None:
        cleanup()

    def test_init(self):
        name = "foo"
        capabilities = {
            1: [1, 2, 3],
            2: [4, 5, 6]
        }
        uinput_defaults = FrontendUInput()
        uinput_custom = FrontendUInput(name=name, events=capabilities)

        self.assertEqual(uinput_defaults.name, 'py-evdev-uinput')
        self.assertIsNone(uinput_defaults.capabilities())

        self.assertEqual(uinput_custom.name, name)
        self.assertEqual(uinput_custom.capabilities(), capabilities)


class TestGlobalUinputs(unittest.TestCase):
    def setUp(self) -> None:
        cleanup()

    def test_iter(self):
        for uinput in global_uinputs:
            self.assertIsInstance(uinput, evdev.UInput)

    def test_write(self):
        """test write and write failure

        implicitly tests get_uinput and UInput.can_emit
        """
        ev_1 = (EV_KEY, KEY_A, 1)
        ev_2 = (EV_ABS, ABS_X, 10)

        keyboard = global_uinputs.get_uinput("keyboard")

        global_uinputs.write(ev_1, "keyboard")
        self.assertEqual(keyboard.write_count, 1)

        with self.assertRaises(EventNotHandled):
            global_uinputs.write(ev_2, "keyboard")

        with self.assertRaises(UinputNotAvailable):
            global_uinputs.write(ev_1, "foo")

    def test_creates_frontend_uinputs(self):
        frontend_uinputs = GlobalUInputs()
        with patch.object(sys, "argv", ["foo"]):
            frontend_uinputs.prepare()

        uinput = frontend_uinputs.get_uinput("keyboard")
        self.assertIsInstance(uinput, FrontendUInput)
