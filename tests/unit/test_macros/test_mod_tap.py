import asyncio
import unittest

import evdev
from evdev.ecodes import KEY_A, EV_KEY, KEY_B, KEY_LEFTSHIFT

from inputremapper.configs.input_config import InputCombination, InputConfig
from inputremapper.configs.mapping import Mapping
from inputremapper.configs.preset import Preset
from inputremapper.injection.context import Context
from inputremapper.injection.event_reader import EventReader
from inputremapper.injection.global_uinputs import GlobalUInputs, UInput
from inputremapper.injection.mapping_handlers.mapping_parser import MappingParser
from inputremapper.input_event import InputEvent
from tests.lib.fixtures import fixtures
from tests.lib.patches import InputDevice
from tests.lib.pipes import uinput_write_history
from tests.lib.test_setup import test_setup


@test_setup
class TestModMap(unittest.IsolatedAsyncioTestCase):
    # Testcases are from https://github.com/qmk/qmk_firmware/blob/78a0adfbb4d2c4e12f93f2a62ded0020d406243e/docs/tap_hold.md#nested-tap-abba-nested-tap
    # This test-setup is a bit more involved, because I want to also properly test the forwarding based on the
    # return-valueof the listener.

    def setUp(self):
        bar_device = fixtures.bar_device
        self.forward_uinput = evdev.UInput(name="test-forward-uinput")
        self.source_device = InputDevice(bar_device.path)
        self.stop_event = asyncio.Event()
        self.global_uinputs = GlobalUInputs(UInput)
        self.global_uinputs.prepare_all()
        self.target_uinput = self.global_uinputs.get_uinput("keyboard")
        self.mapping_parser = MappingParser(self.global_uinputs)

        preset = Preset()
        input_cfg = InputCombination(
            [
                InputConfig(
                    type=EV_KEY,
                    code=KEY_A,
                    origin_hash=bar_device.get_device_hash(),
                )
            ]
        ).to_config()
        preset.add(
            Mapping.from_combination(
                input_combination=input_cfg,
                output_symbol="mod_tap(a, Shift_L)",
            ),
        )

        self.context = Context(
            preset,
            source_devices={bar_device.get_device_hash(): self.source_device},
            forward_devices={bar_device.get_device_hash(): self.forward_uinput},
            mapping_parser=self.mapping_parser,
        )

        self.event_reader = EventReader(
            self.context,
            self.source_device,
            self.stop_event,
        )

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def write(self, type_, code, value):
        self.target_uinput.write_event(InputEvent.from_tuple((type_, code, value)))

    async def input(self, type_, code, value):
        await self.event_reader.handle(
            InputEvent.from_tuple(
                (
                    type_,
                    code,
                    value,
                ),
                origin_hash=fixtures.bar_device.get_device_hash(),
            )
        )

    async def test_distinct_taps_1(self):
        await self.input(EV_KEY, KEY_A, 1)
        await asyncio.sleep(0.190)
        await self.input(EV_KEY, KEY_A, 0)
        await asyncio.sleep(0.020)  # exceeds tapping_term here
        await self.input(EV_KEY, KEY_B, 1)
        await asyncio.sleep(0.020)
        await self.input(EV_KEY, KEY_B, 0)

        self.assertEqual(
            uinput_write_history,
            [
                InputEvent.from_tuple((EV_KEY, KEY_A, 1)),
                InputEvent.from_tuple((EV_KEY, KEY_A, 0)),
                InputEvent.from_tuple((EV_KEY, KEY_B, 1)),
                InputEvent.from_tuple((EV_KEY, KEY_B, 0)),
            ],
        )
        self.assertEqual(
            self.target_uinput.write_history,
            [
                InputEvent.from_tuple((EV_KEY, KEY_A, 1)),
                InputEvent.from_tuple((EV_KEY, KEY_A, 0)),
            ],
        )
        self.assertEqual(
            self.forward_uinput.write_history,
            [
                InputEvent.from_tuple((EV_KEY, KEY_B, 1)),
                InputEvent.from_tuple((EV_KEY, KEY_B, 0)),
            ],
        )

    async def test_distinct_taps_2(self):
        await self.input(EV_KEY, KEY_A, 1)
        await asyncio.sleep(0.210)  # exceeds tapping_term here
        await self.input(EV_KEY, KEY_A, 0)
        await asyncio.sleep(0.020)
        await self.input(EV_KEY, KEY_B, 1)
        await asyncio.sleep(0.020)
        await self.input(EV_KEY, KEY_B, 0)

        self.assertEqual(
            uinput_write_history,
            [
                InputEvent.from_tuple((EV_KEY, KEY_LEFTSHIFT, 1)),
                InputEvent.from_tuple((EV_KEY, KEY_LEFTSHIFT, 0)),
                InputEvent.from_tuple((EV_KEY, KEY_B, 1)),
                InputEvent.from_tuple((EV_KEY, KEY_B, 0)),
            ],
        )
        self.assertEqual(
            self.target_uinput.write_history,
            [
                InputEvent.from_tuple((EV_KEY, KEY_LEFTSHIFT, 1)),
                InputEvent.from_tuple((EV_KEY, KEY_LEFTSHIFT, 0)),
            ],
        )
        self.assertEqual(
            self.forward_uinput.write_history,
            [
                InputEvent.from_tuple((EV_KEY, KEY_B, 1)),
                InputEvent.from_tuple((EV_KEY, KEY_B, 0)),
            ],
        )

    async def test_nested_tap_1(self):
        await self.input(EV_KEY, KEY_A, 1)
        await asyncio.sleep(0.110)
        self.assertEqual(uinput_write_history, [])

        await self.input(EV_KEY, KEY_B, 1)
        await asyncio.sleep(0.010)
        self.assertEqual(uinput_write_history, [])

        await self.input(EV_KEY, KEY_B, 0)
        await asyncio.sleep(0.070)
        self.assertEqual(uinput_write_history, [])

        await self.input(EV_KEY, KEY_A, 0)

        # everything happened within the tapping_term, so the modifier is not activated.
        # "ab" should be written, in the exact order of the input.
        await asyncio.sleep(0.020)
        self.assertEqual(
            uinput_write_history,
            [
                InputEvent.from_tuple((EV_KEY, KEY_A, 1)),
                InputEvent.from_tuple((EV_KEY, KEY_B, 1)),
                InputEvent.from_tuple((EV_KEY, KEY_B, 0)),
                InputEvent.from_tuple((EV_KEY, KEY_A, 0)),
            ],
        )

    async def test_nested_tap_2(self):
        await self.input(EV_KEY, KEY_A, 1)
        await asyncio.sleep(0.110)
        await self.input(EV_KEY, KEY_B, 1)
        await asyncio.sleep(0.010)
        await self.input(EV_KEY, KEY_B, 0)
        await asyncio.sleep(0.100)  # exceeds tapping_term here
        await self.input(EV_KEY, KEY_A, 0)

        await asyncio.sleep(0.020)
        self.assertEqual(
            uinput_write_history,
            [
                InputEvent.from_tuple((EV_KEY, KEY_LEFTSHIFT, 1)),
                InputEvent.from_tuple((EV_KEY, KEY_B, 1)),
                InputEvent.from_tuple((EV_KEY, KEY_B, 0)),
                InputEvent.from_tuple((EV_KEY, KEY_LEFTSHIFT, 0)),
            ],
        )

    async def test_nested_tap_3(self):
        await self.input(EV_KEY, KEY_A, 1)
        await asyncio.sleep(0.210)  # exceeds tapping_term here
        await self.input(EV_KEY, KEY_B, 1)
        await asyncio.sleep(0.010)
        await self.input(EV_KEY, KEY_B, 0)
        await asyncio.sleep(0.010)
        await self.input(EV_KEY, KEY_A, 0)

        await asyncio.sleep(0.020)
        self.assertEqual(
            uinput_write_history,
            [
                InputEvent.from_tuple((EV_KEY, KEY_LEFTSHIFT, 1)),
                InputEvent.from_tuple((EV_KEY, KEY_B, 1)),
                InputEvent.from_tuple((EV_KEY, KEY_B, 0)),
                InputEvent.from_tuple((EV_KEY, KEY_LEFTSHIFT, 0)),
            ],
        )

    async def test_rolling_keys_1(self):
        await self.input(EV_KEY, KEY_A, 1)
        await asyncio.sleep(0.110)
        await self.input(EV_KEY, KEY_B, 1)
        await asyncio.sleep(0.010)
        await self.input(EV_KEY, KEY_A, 0)
        await asyncio.sleep(0.010)
        await self.input(EV_KEY, KEY_B, 0)

        # everything happened within the tapping_term, so the modifier is not activated.
        # "ab" should be written, in the exact order of the input.
        await asyncio.sleep(0.100)
        self.assertEqual(
            uinput_write_history,
            [
                InputEvent.from_tuple((EV_KEY, KEY_A, 1)),
                InputEvent.from_tuple((EV_KEY, KEY_B, 1)),
                InputEvent.from_tuple((EV_KEY, KEY_A, 0)),
                InputEvent.from_tuple((EV_KEY, KEY_B, 0)),
            ],
        )

    async def test_rolling_keys_2(self):
        await self.input(EV_KEY, KEY_A, 1)
        await asyncio.sleep(0.110)
        await self.input(EV_KEY, KEY_B, 1)
        await asyncio.sleep(0.100)  # exceeds tapping_term here
        await self.input(EV_KEY, KEY_A, 0)
        await asyncio.sleep(0.010)
        await self.input(EV_KEY, KEY_B, 0)

        await asyncio.sleep(0.020)
        self.assertEqual(
            uinput_write_history,
            [
                InputEvent.from_tuple((EV_KEY, KEY_LEFTSHIFT, 1)),
                InputEvent.from_tuple((EV_KEY, KEY_B, 1)),
                InputEvent.from_tuple((EV_KEY, KEY_LEFTSHIFT, 0)),
                InputEvent.from_tuple((EV_KEY, KEY_B, 0)),
            ],
        )
