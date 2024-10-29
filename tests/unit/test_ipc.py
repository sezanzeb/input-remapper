#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2024 sezanzeb <b8x45ygc9@mozmail.com>
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

import asyncio
import multiprocessing
import os
import select
import time
import unittest

from inputremapper.ipc.pipe import Pipe
from inputremapper.ipc.shared_dict import SharedDict
from inputremapper.ipc.socket import Server, Client, Base
from tests.lib.test_setup import test_setup
from tests.lib.tmp import tmp


@test_setup
class TestSharedDict(unittest.TestCase):
    def setUp(self):
        self.shared_dict = SharedDict()
        self.shared_dict.start()
        time.sleep(0.02)

    def test_returns_none(self):
        self.assertIsNone(self.shared_dict.get("a"))
        self.assertIsNone(self.shared_dict["a"])

    def test_set_get(self):
        self.shared_dict["a"] = 3
        self.assertEqual(self.shared_dict.get("a"), 3)
        self.assertEqual(self.shared_dict["a"], 3)


@test_setup
class TestSocket(unittest.TestCase):
    def test_socket(self):
        def test(s1, s2):
            self.assertEqual(s2.recv(), None)

            s1.send(1)
            self.assertTrue(s2.poll())
            self.assertEqual(s2.recv(), 1)
            self.assertFalse(s2.poll())
            self.assertEqual(s2.recv(), None)

            s1.send(2)
            self.assertTrue(s2.poll())
            s1.send(3)
            self.assertTrue(s2.poll())
            self.assertEqual(s2.recv(), 2)
            self.assertTrue(s2.poll())
            self.assertEqual(s2.recv(), 3)
            self.assertFalse(s2.poll())
            self.assertEqual(s2.recv(), None)

        server = Server(os.path.join(tmp, "socket1"))
        client = Client(os.path.join(tmp, "socket1"))
        test(server, client)

        client = Client(os.path.join(tmp, "socket2"))
        server = Server(os.path.join(tmp, "socket2"))
        test(client, server)

    def test_not_connected_1(self):
        # client discards old message, because it might have had a purpose
        # for a different client and not for the current one
        server = Server(os.path.join(tmp, "socket3"))
        server.send(1)

        client = Client(os.path.join(tmp, "socket3"))
        server.send(2)

        self.assertTrue(client.poll())
        self.assertEqual(client.recv(), 2)
        self.assertFalse(client.poll())
        self.assertEqual(client.recv(), None)

    def test_not_connected_2(self):
        client = Client(os.path.join(tmp, "socket4"))
        client.send(1)

        server = Server(os.path.join(tmp, "socket4"))
        client.send(2)

        self.assertTrue(server.poll())
        self.assertEqual(server.recv(), 2)
        self.assertFalse(server.poll())
        self.assertEqual(server.recv(), None)

    def test_select(self):
        """Is compatible to select.select."""
        server = Server(os.path.join(tmp, "socket6"))
        client = Client(os.path.join(tmp, "socket6"))

        server.send(1)
        ready = select.select([client], [], [], 0)[0][0]
        self.assertEqual(ready, client)

        client.send(2)
        ready = select.select([server], [], [], 0)[0][0]
        self.assertEqual(ready, server)

    def test_base_abstract(self):
        self.assertRaises(NotImplementedError, lambda: Base("foo"))
        self.assertRaises(NotImplementedError, lambda: Base.connect(None))
        self.assertRaises(NotImplementedError, lambda: Base.reconnect(None))
        self.assertRaises(NotImplementedError, lambda: Base.fileno(None))


@test_setup
class TestPipe(unittest.IsolatedAsyncioTestCase):
    def test_pipe_single(self):
        p1 = Pipe(os.path.join(tmp, "pipe"))
        self.assertEqual(p1.recv(), None)

        p1.send(1)
        self.assertTrue(p1.poll())
        self.assertEqual(p1.recv(), 1)
        self.assertFalse(p1.poll())
        self.assertEqual(p1.recv(), None)

        p1.send(2)
        self.assertTrue(p1.poll())
        p1.send(3)
        self.assertTrue(p1.poll())
        self.assertEqual(p1.recv(), 2)
        self.assertTrue(p1.poll())
        self.assertEqual(p1.recv(), 3)
        self.assertFalse(p1.poll())
        self.assertEqual(p1.recv(), None)

    def test_pipe_duo(self):
        p1 = Pipe(os.path.join(tmp, "pipe"))
        p2 = Pipe(os.path.join(tmp, "pipe"))
        self.assertEqual(p2.recv(), None)

        p1.send(1)
        self.assertEqual(p2.recv(), 1)
        self.assertEqual(p2.recv(), None)

        p1.send(2)
        p1.send(3)
        self.assertEqual(p2.recv(), 2)
        self.assertEqual(p2.recv(), 3)
        self.assertEqual(p2.recv(), None)

    async def test_async_for_loop(self):
        p1 = Pipe(os.path.join(tmp, "pipe"))
        iterator = p1.__aiter__()
        p1.send(1)

        self.assertEqual(await iterator.__anext__(), 1)

        read_task = asyncio.Task(iterator.__anext__())
        timeout_task = asyncio.Task(asyncio.sleep(1))

        done, pending = await asyncio.wait(
            (read_task, timeout_task), return_when=asyncio.FIRST_COMPLETED
        )
        self.assertIn(timeout_task, done)
        self.assertIn(read_task, pending)
        read_task.cancel()

    async def test_async_for_loop_duo(self):
        def writer():
            p = Pipe(os.path.join(tmp, "pipe"))
            for i in range(3):
                p.send(i)
            time.sleep(0.5)
            for i in range(3):
                p.send(i)
            time.sleep(0.1)
            p.send("stop now")

        p1 = Pipe(os.path.join(tmp, "pipe"))

        w_process = multiprocessing.Process(target=writer)
        w_process.start()

        messages = []
        async for msg in p1:
            messages.append(msg)
            if msg == "stop now":
                break

        self.assertEqual(messages, [0, 1, 2, 0, 1, 2, "stop now"])


if __name__ == "__main__":
    unittest.main()
