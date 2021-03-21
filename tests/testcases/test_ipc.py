#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@sezanzeb.de>
#
# This file is part of key-mapper.
#
# key-mapper is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# key-mapper is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with key-mapper.  If not, see <https://www.gnu.org/licenses/>.


import unittest
import select

from keymapper.ipc.pipe import Pipe
from keymapper.ipc.socket import Server, Client, Base


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

        server = Server('/tmp/key-mapper-test/socket1')
        client = Client('/tmp/key-mapper-test/socket1')
        test(server, client)

        client = Client('/tmp/key-mapper-test/socket2')
        server = Server('/tmp/key-mapper-test/socket2')
        test(client, server)

    def test_not_connected_1(self):
        # client discards old message, because it might have had a purpose
        # for a different client and not for the current one
        server = Server('/tmp/key-mapper-test/socket3')
        server.send(1)

        client = Client('/tmp/key-mapper-test/socket3')
        server.send(2)

        self.assertTrue(client.poll())
        self.assertEqual(client.recv(), 2)
        self.assertFalse(client.poll())
        self.assertEqual(client.recv(), None)

    def test_not_connected_2(self):
        client = Client('/tmp/key-mapper-test/socket4')
        client.send(1)

        server = Server('/tmp/key-mapper-test/socket4')
        client.send(2)

        self.assertTrue(server.poll())
        self.assertEqual(server.recv(), 2)
        self.assertFalse(server.poll())
        self.assertEqual(server.recv(), None)

    def test_select(self):
        """is compatible to select.select"""
        server = Server('/tmp/key-mapper-test/socket6')
        client = Client('/tmp/key-mapper-test/socket6')

        server.send(1)
        ready = select.select([client], [], [], 0)[0][0]
        self.assertEqual(ready, client)

        client.send(2)
        ready = select.select([server], [], [], 0)[0][0]
        self.assertEqual(ready, server)

    def test_base_abstract(self):
        self.assertRaises(NotImplementedError, lambda: Base('foo'))
        self.assertRaises(NotImplementedError, lambda: Base.connect(None))
        self.assertRaises(NotImplementedError, lambda: Base.reconnect(None))
        self.assertRaises(NotImplementedError, lambda: Base.fileno(None))


class TestPipe(unittest.TestCase):
    def test_pipe_single(self):
        p1 = Pipe('/tmp/key-mapper-test/pipe')
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
        p1 = Pipe('/tmp/key-mapper-test/pipe')
        p2 = Pipe('/tmp/key-mapper-test/pipe')
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
