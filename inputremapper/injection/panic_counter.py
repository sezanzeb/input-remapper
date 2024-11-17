import asyncio
import multiprocessing
import os
from typing import List

from evdev.ecodes import EV_KEY

from inputremapper.configs.keyboard_layout import keyboard_layout
from inputremapper.input_event import InputEvent
from inputremapper.logging.logger import logger


class PanicCounter:
    """Stop the input-remapper-service if the user types the codeword.

    This is useful if a macro, for whatever reason, did something like
    key_down(Shift_L) and you need to stop input-remapper to regain control of
    your system."""

    panic_counter = 0
    panic_codes: List[int]

    def __init__(self) -> None:
        self.panic_codes = self._get_panic_word_codes()

    async def track(self, event: InputEvent) -> None:
        if event.type != EV_KEY or event.value != 1:
            return

        if self.panic_codes[self.panic_counter] == event.code:
            self.panic_counter += 1
        else:
            self.panic_counter = 0

        if self.panic_counter == len(self.panic_codes):
            try:
                logger.info("Panic word detected, stopping process")

                # The event-reader is running in the injector, which is a separate process,
                # so just doing sys.exit won't suffice. We need to tell the daemon
                # parent-process to stop.
                os.system("input-remapper-control --command quit &")

                # Give the daemon some time to exit gracefully.
                await asyncio.sleep(1)

                # If we are still alive, then try to stop using SIGTERM via pythons
                # built-in methods.
                parent_process = multiprocessing.parent_process()
                if parent_process is not None:
                    logger.error("Process is still running, trying to terminate")
                    parent_process.terminate()
                    await asyncio.sleep(1)
            finally:
                # Last resort
                logger.error("Process is still running, sending SIGKILL")
                os.system("pkill -f -9 input-remapper-service")

    def _get_panic_word_codes(self) -> List[int]:
        # Optimization to avoid having to map codes to letters during runtime.
        result = []
        for letter in "inputremapperpanicquit":
            code = keyboard_layout.get(letter)
            if code is None:
                code = keyboard_layout.get(f"KEY_{letter}")
            result.append(code)
        return result
