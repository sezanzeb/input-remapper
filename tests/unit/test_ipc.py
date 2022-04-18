#!/usr/bin/python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2022 sezanzeb <proxima@sezanzeb.de>
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


from tests.test import quick_cleanup, tmp

import unittest
import select
import time
import os

from inputremapper.ipc.pipe import Pipe
from inputremapper.ipc.shared_dict import SharedDict
from inputremapper.ipc.socket import Server, Client, Base


class TestSharedDict(unittest.TestCase):
    def setUp(self):
        self.shared_dict = SharedDict()
        self.shared_dict.start()
        time.sleep(0.02)

    def tearDown(self):
        quick_cleanup()

    def test_returns_none(self):
        self.assertIsNone(self.shared_dict.get("a"))
        self.assertIsNone(self.shared_dict["a"])

    def test_set_get(self):
        self.shared_dict["a"] = 3
        self.assertEqual(self.shared_dict.get("a"), 3)
        self.assertEqual(self.shared_dict["a"], 3)


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


class TestPipe(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
