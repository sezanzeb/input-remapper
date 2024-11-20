import asyncio
import time
import unittest
from unittest.mock import patch

import evdev
from evdev.ecodes import KEY_A, EV_KEY, KEY_B, KEY_LEFTSHIFT, KEY_C

from inputremapper.configs.input_config import InputConfig
from inputremapper.configs.mapping import Mapping
from inputremapper.configs.preset import Preset
from inputremapper.injection.context import Context
from inputremapper.injection.event_reader import EventReader
from inputremapper.injection.global_uinputs import GlobalUInputs, UInput
from inputremapper.injection.macros.parse import Parser
from inputremapper.injection.mapping_handlers.mapping_parser import MappingParser
from inputremapper.input_event import InputEvent
from tests.lib.fixtures import fixtures
from tests.lib.patches import InputDevice
from tests.lib.pipes import uinput_write_history
from tests.lib.test_setup import test_setup
from tests.unit.test_macros import MacroTestBase, DummyMapping


@test_setup
class TestModTapIntegration(unittest.IsolatedAsyncioTestCase):
    # Testcases are from https://github.com/qmk/qmk_firmware/blob/78a0adfbb4d2c4e12f93f2a62ded0020d406243e/docs/tap_hold.md#nested-tap-abba-nested-tap
    # This test-setup is a bit more involved, because I want to also properly test the forwarding based on the
    # return-value of the listener.

    def setUp(self):
        self.origin_hash = fixtures.bar_device.get_device_hash()
        self.forward_uinput = evdev.UInput(name="test-forward-uinput")
        self.source_device = InputDevice(fixtures.bar_device.path)
        self.stop_event = asyncio.Event()
        self.global_uinputs = GlobalUInputs(UInput)
        self.global_uinputs.prepare_all()
        self.target_uinput = self.global_uinputs.get_uinput("keyboard")
        self.mapping_parser = MappingParser(self.global_uinputs)

        self.mapping = Mapping.from_combination(
            input_combination=[
                InputConfig(
                    type=EV_KEY,
                    code=KEY_A,
                    origin_hash=self.origin_hash,
                )
            ],
            output_symbol="mod_tap(a, Shift_L)",
        )

        self.preset = Preset()
        self.preset.add(self.mapping)

        self.bootstrap_event_reader()

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def bootstrap_event_reader(self):
        self.context = Context(
            self.preset,
            source_devices={self.origin_hash: self.source_device},
            forward_devices={self.origin_hash: self.forward_uinput},
            mapping_parser=self.mapping_parser,
        )

        self.event_reader = EventReader(
            self.context,
            self.source_device,
            self.stop_event,
        )

    def write(self, type_, code, value):
        self.target_uinput.write_event(InputEvent.from_tuple((type_, code, value)))

    async def input(self, type_, code, value):
        asyncio.ensure_future(
            self.event_reader.handle(
                InputEvent.from_tuple(
                    (
                        type_,
                        code,
                        value,
                    ),
                    origin_hash=self.origin_hash,
                )
            )
        )
        # Make the main_loop iterate a bit for the event_reader to do its thing.
        await asyncio.sleep(0)

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
        await asyncio.sleep(0.220)  # exceeds tapping_term here
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
        await asyncio.sleep(0.100)
        self.assertEqual(uinput_write_history, [])

        await self.input(EV_KEY, KEY_B, 1)
        await asyncio.sleep(0.020)
        self.assertEqual(uinput_write_history, [])

        await self.input(EV_KEY, KEY_B, 0)
        await asyncio.sleep(0.050)
        self.assertEqual(uinput_write_history, [])

        await self.input(EV_KEY, KEY_A, 0)

        # everything happened within the tapping_term, so the modifier is not activated.
        # "ab" should be written, in the exact order of the input.
        await asyncio.sleep(0.040)
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
        await asyncio.sleep(0.100)
        await self.input(EV_KEY, KEY_B, 1)
        await asyncio.sleep(0.020)
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
        await asyncio.sleep(0.220)  # exceeds tapping_term here
        await self.input(EV_KEY, KEY_B, 1)
        await asyncio.sleep(0.020)
        await self.input(EV_KEY, KEY_B, 0)
        await asyncio.sleep(0.020)
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
        await asyncio.sleep(0.100)
        await self.input(EV_KEY, KEY_B, 1)
        await asyncio.sleep(0.020)
        await self.input(EV_KEY, KEY_A, 0)
        await asyncio.sleep(0.020)
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
        await asyncio.sleep(0.100)
        await self.input(EV_KEY, KEY_B, 1)
        await asyncio.sleep(0.100)  # exceeds tapping_term here
        await self.input(EV_KEY, KEY_A, 0)
        await asyncio.sleep(0.020)
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

    async def test_many_keys_correct_order(self):
        await self.many_keys_correct_order()

    async def test_many_keys_correct_order_with_sleep(self):
        self.mapping.macro_key_sleep_ms = 20
        await self.many_keys_correct_order()

    async def many_keys_correct_order(self):
        await self.input(EV_KEY, KEY_A, 1)

        # Send many events to the listener. It has to make all of them wait.
        for i in range(30):
            await self.input(EV_KEY, i, 1)

        # exceed tapping_term. mod_tap will inject the modifier and replay all the
        # previous events.
        await asyncio.sleep(0.201)

        # mod_tap is busy replaying events. While it does that, inject this
        await self.input(EV_KEY, 100, 1)

        start = time.time()
        timeout = 2
        while len(uinput_write_history) < 32 and (time.time() - start) < timeout:
            # Wait for it to complete
            await asyncio.sleep(0.1)

        self.assertEqual(len(uinput_write_history), 32)

        # Expect it to cleanly handle all events before injecting 100. Expect
        # everything to be in the correct order.
        self.assertEqual(
            uinput_write_history,
            [
                InputEvent.from_tuple((EV_KEY, KEY_LEFTSHIFT, 1)),
                *[InputEvent.from_tuple((EV_KEY, i, 1)) for i in range(30)],
                InputEvent.from_tuple((EV_KEY, 100, 1)),
            ],
        )

    async def test_mapped_second_key(self):
        # Map b to c.
        # While mod_tap is waiting for the timeout to happen, press b.
        # We expect c to be written, because b goes through the handlers and
        # gets mapped.
        # The event_reader has to wait for listeners to complete for mod_tap to work, so
        # that it hands them over to the other handlers when the time comes.
        # That means however, that the event_readers loop blocks. Therefore, it was turned
        # into a fire-and-forget kind of thing. When an event arrives, it just schedules
        # asyncio to do that stuff later, and continues reading.

        self.preset.add(
            Mapping.from_combination(
                input_combination=[
                    InputConfig(
                        type=EV_KEY,
                        code=KEY_B,
                        origin_hash=self.origin_hash,
                    )
                ],
                output_symbol="c",
            ),
        )

        self.bootstrap_event_reader()

        async def async_generator():
            events = [
                InputEvent(0, 0, EV_KEY, KEY_A, 1),
                InputEvent(0, 0, EV_KEY, KEY_B, 1),
                InputEvent(0, 0, EV_KEY, KEY_A, 0),
                InputEvent(0, 0, EV_KEY, KEY_B, 0),
            ]
            for event in events:
                yield event
                # Wait a bit. During runtime, events don't come in that quickly
                # and the mod_tap macro needs some loop iterations until it adds
                # the listener to the context.
                await asyncio.sleep(0.010)

        with patch.object(self.event_reader, "read_loop", async_generator):
            await self.event_reader.run()

        await asyncio.sleep(0.020)
        self.assertIn(InputEvent(0, 0, EV_KEY, KEY_C, 1), uinput_write_history)
        self.assertIn(InputEvent(0, 0, EV_KEY, KEY_C, 0), uinput_write_history)
        self.assertIn(InputEvent(0, 0, EV_KEY, KEY_A, 1), uinput_write_history)
        self.assertIn(InputEvent(0, 0, EV_KEY, KEY_A, 0), uinput_write_history)
        self.assertNotIn(InputEvent(0, 0, EV_KEY, KEY_B, 1), uinput_write_history)
        self.assertNotIn(InputEvent(0, 0, EV_KEY, KEY_B, 0), uinput_write_history)


@test_setup
class TestModTapUnit(MacroTestBase):
    async def wait_for_timeout(self, macro):
        macro = Parser.parse(macro, self.context, DummyMapping, True)

        start = time.time()
        # Awaiting the macro run will cause it to wait for the tapping_term
        macro.press_trigger()
        await macro.run(lambda *_, **__: macro.release_trigger())
        return time.time() - start

    async def test_tapping_term_configuration_default(self):
        time_ = await self.wait_for_timeout("mod_tap(a, b)")
        # + 3 times 10ms of keycode_pause
        self.assertAlmostEqual(time_, 0.23, delta=0.01)

    async def test_tapping_term_configuration_100(self):
        time_ = await self.wait_for_timeout("mod_tap(a, b, 100)")
        self.assertAlmostEqual(time_, 0.13, delta=0.01)

    async def test_tapping_term_configuration_100_kwarg(self):
        time_ = await self.wait_for_timeout("mod_tap(a, b, tapping_term=100)")
        self.assertAlmostEqual(time_, 0.13, delta=0.01)
