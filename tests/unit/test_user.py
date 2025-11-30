#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2025 sezanzeb <b8x45ygc9@mozmail.com>
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


import os
import unittest
from unittest import mock

from inputremapper.user import UserUtils
from tests.lib.test_setup import test_setup


def _raise(error):
    raise error


@test_setup
class TestUser(unittest.TestCase):
    def test_get_user(self):
        with mock.patch("os.getlogin", lambda: "foo"):
            self.assertEqual(UserUtils.get_user(), "foo")

        with mock.patch("os.getlogin", lambda: "root"):
            self.assertEqual(UserUtils.get_user(), "root")

        property_mock = mock.Mock()
        property_mock.configure_mock(pw_name="quix")
        with (
            mock.patch("os.getlogin", lambda: _raise(OSError())),
            mock.patch("pwd.getpwuid", return_value=property_mock),
        ):
            os.environ["USER"] = "root"
            os.environ["SUDO_USER"] = "qux"
            self.assertEqual(UserUtils.get_user(), "qux")

            os.environ["USER"] = "root"
            del os.environ["SUDO_USER"]
            os.environ["PKEXEC_UID"] = "1000"
            self.assertNotEqual(UserUtils.get_user(), "root")

    def test_get_home(self):
        property_mock = mock.Mock()
        property_mock.configure_mock(pw_dir="/custom/home/foo")
        with mock.patch("pwd.getpwnam", return_value=property_mock):
            self.assertEqual(UserUtils.get_home("foo"), "/custom/home/foo")
