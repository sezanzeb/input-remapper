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


from tests.lib.cleanup import quick_cleanup

import os
import unittest
from unittest import mock

from inputremapper.user import get_user, get_home


def _raise(error):
    raise error


class TestUser(unittest.TestCase):
    def tearDown(self):
        quick_cleanup()

    def test_get_user(self):
        with mock.patch("os.getlogin", lambda: "foo"):
            self.assertEqual(get_user(), "foo")

        with mock.patch("os.getlogin", lambda: "root"):
            self.assertEqual(get_user(), "root")

        property_mock = mock.Mock()
        property_mock.configure_mock(pw_name="quix")
        with mock.patch("os.getlogin", lambda: _raise(OSError())), mock.patch(
            "pwd.getpwuid", return_value=property_mock
        ):
            os.environ["USER"] = "root"
            os.environ["SUDO_USER"] = "qux"
            self.assertEqual(get_user(), "qux")

            os.environ["USER"] = "root"
            del os.environ["SUDO_USER"]
            os.environ["PKEXEC_UID"] = "1000"
            self.assertNotEqual(get_user(), "root")

    def test_get_home(self):
        property_mock = mock.Mock()
        property_mock.configure_mock(pw_dir="/custom/home/foo")
        with mock.patch("pwd.getpwnam", return_value=property_mock):
            self.assertEqual(get_home("foo"), "/custom/home/foo")
