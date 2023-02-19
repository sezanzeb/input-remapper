import time
import unittest
from unittest.async_case import TestCase, IsolatedAsyncioTestCase
import asyncio


class AsyncTestBase(IsolatedAsyncioTestCase):
    async def awaitEqual(self, func, value, *msg, timeout=100):
        timeout_seconds = float(timeout) / 1000.0
        delay = timeout_seconds / 100.0
        stop = time.time() + timeout_seconds
        result = None
        ex = None
        while True:
            try:
                result = func(self)
            except Exception as e:
                ex = e
            else:
                if result == value:
                    return

            # wait using exponential delay
            await asyncio.sleep(delay)
            delay = min(stop - time.time(), delay * 2.0)
            if delay < 0:
                break

        if ex:
            raise ex

        self.fail(f"awaitEqual({func.__name__}, {value}) timed out")


class TestAsyncTestCase(AsyncTestBase):
    def setUp(self):
        self.text = 1

    async def modify(self, v, delay=0.01):
        await asyncio.sleep(delay)
        self.text = v

    async def test_await_delayed_value_change(self):
        self.assertEqual(self.text, 1)
        fut = asyncio.create_task(self.modify(2))
        await self.awaitEqual(
            lambda t: self.text,
            2,
        )
        await fut
        self.assertEqual(self.text, 2)


if __name__ == "__main__":
    asyncio.run(unittest.main())
