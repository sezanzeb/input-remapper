#!/usr/bin/python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2023 sezanzeb <proxima@sezanzeb.de>
#
# This file is part of input-remapper.
#
# input-remapper is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# input-remapper is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with input-remapper.  If not, see <https://www.gnu.org/licenses/>.


import time
import unittest
from unittest.async_case import TestCase, IsolatedAsyncioTestCase
import asyncio


class AsyncTestBase(IsolatedAsyncioTestCase):
    async def awaitEqual(self, func, value, *msg, timeout: float = 0.1):
        await self.awaitTrue(lambda: func() == value, *msg, timeout=timeout)

    async def awaitNotEqual(self, func, value, *msg, timeout: float = 0.1):
        await self.awaitTrue(lambda: func() != value, *msg, timeout=timeout)

    async def awaitIs(self, func, value, *msg, timeout: float = 0.1):
        await self.awaitTrue(lambda: func() is value, *msg, timeout=timeout)

    async def awaitIsNot(self, func, value, *msg, timeout: float = 0.1):
        await self.awaitTrue(lambda: func() is not value, *msg, timeout=timeout)

    async def awaitNone(self, func, *msg, timeout: float = 0.1):
        await self.awaitTrue(lambda: func() is None, *msg, timeout=timeout)

    async def awaitNotNone(self, func, *msg, timeout: float = 0.1):
        await self.awaitTrue(lambda: func() is not None, *msg, timeout=timeout)

    async def awaitFalse(self, func, *msg, timeout: float = 0.1):
        await self.awaitTrue(lambda: func() is False, *msg, timeout=timeout)

    async def awaitTrue(self, func, *msg, timeout: float = 0.1):
        delay = timeout / 100.0

        async def await_success(delay):
            while True:
                try:
                    if func() is True:
                        return
                except Exception as e:
                    ex = e

                delay *= 1.5  # use exponential delay
                await asyncio.sleep(delay)

        await asyncio.wait_for(await_success(delay), timeout)


class TestAsyncTestBase(AsyncTestBase):
    def setUp(self):
        self.text = 1

    async def modify(self, v, delay=0.01):
        await asyncio.sleep(delay)
        self.text = v

    async def test_await_delayed_value_change(self):
        self.assertEqual(self.text, 1)
        fut = asyncio.create_task(self.modify(2))
        await self.awaitEqual(lambda: self.text, 2)
        await fut
        self.assertEqual(self.text, 2)

    async def test_await_timeout(self):
        try:
            await self.awaitEqual(lambda: False, True)
        except asyncio.exceptions.TimeoutError:
            pass
        else:
            self.fail("awaitEqual must time out")


if __name__ == "__main__":
    asyncio.run(unittest.main())
