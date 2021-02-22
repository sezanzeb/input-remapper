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


import os
import grp
import getpass
import subprocess
import unittest

from keymapper.permissions import check_injection_rights, check_group, \
    can_read_devices
from keymapper.paths import USER
from keymapper.daemon import is_service_running


original_access = os.access
original_getgrnam = grp.getgrnam
original_check_output = subprocess.check_output
original_stat = os.stat
oringal_getuser = getpass.getuser


class TestPermissions(unittest.TestCase):
    def tearDown(self):
        # reset all fakes
        os.access = original_access
        grp.getgrnam = original_getgrnam
        subprocess.check_output = original_check_output
        os.stat = original_stat
        getpass.getuser = oringal_getuser

    def test_check_injection_rights(self):
        can_access = False
        os.access = lambda *args: can_access

        self.assertIsNotNone(check_injection_rights())
        can_access = True
        self.assertIsNone(check_injection_rights())

    def fake_setup(self):
        """Patch some functions to have the following fake environment:

        Groups
        ------
        input: id: 0, members: $USER, used in /dev, set up
        plugdev: id: 1, members: $USER, used in /dev, not in `groups`
        foobar: id: 2, no members, used in /dev
        a_unused: id: 0, members: $USER, not used in /dev, set up
        b_unused: id: 1, members: $USER, not used in /dev, not in `groups`
        c_unused: id: 2, no members, not used in /dev
        """
        gr_mems = {
            'input': (0, [USER]),
            'plugdev': (1, [USER]),
            'foobar': (2, []),
            'a_unused': (3, [USER]),
            'b_unused': (4, [USER]),
            'c_unused': (5, [])
        }

        stat_counter = 0

        class stat:
            def __init__(self, path):
                nonlocal stat_counter
                stat_counter += 1
                # make sure stat returns all of those groups at some point.
                # only works if there are more than three files in /dev, which
                # should be the case
                self.st_gid = [0, 1, 2][stat_counter % 3]

        os.stat = stat

        class getgrnam:
            def __init__(self, group):
                if group not in gr_mems:
                    raise KeyError()

                self.gr_gid = gr_mems[group][0]
                self.gr_mem = gr_mems[group][1]

        grp.getgrnam = getgrnam

        def fake_check_output(cmd):
            # fake the `groups` output to act like the current session only
            # has input and a_unused active
            if cmd == 'groups' or cmd[0] == 'groups':
                return b'foo input a_unused bar'

            return original_check_output(cmd)

        subprocess.check_output = fake_check_output

    def test_can_read_devices(self):
        self.fake_setup()
        self.assertFalse(is_service_running())

        # root user doesn't need this stuff
        getpass.getuser = lambda: 'root'
        self.assertEqual(len(can_read_devices()), 0)

        getpass.getuser = lambda: USER
        os.access = lambda *args: False
        # plugdev not yet setup correctly and cannot write
        self.assertEqual(len(can_read_devices()), 2)

        os.access = lambda *args: True
        self.assertEqual(len(can_read_devices()), 1)

        subprocess.check_output = lambda cmd: b'plugdev input'
        self.assertEqual(len(can_read_devices()), 0)

    def test_check_group(self):
        self.fake_setup()

        # correctly setup
        self.assertIsNone(check_group('input'))

        # session restart required, usermod already done
        self.assertIsNotNone(check_group('plugdev'))
        self.assertIn('plugdev', check_group('plugdev'))
        self.assertIn('session', check_group('plugdev'))

        # usermod required
        self.assertIsNotNone(check_group('foobar'))
        self.assertIn('foobar', check_group('foobar'))
        self.assertIn('group', check_group('foobar'))

        # don't exist in /dev
        self.assertIsNone(check_group('a_unused'))
        self.assertIsNone(check_group('b_unused'))
        self.assertIsNone(check_group('c_unused'))

        # group doesn't exist
        self.assertIsNone(check_group('qux'))

        def file_not_found_error(cmd):
            raise FileNotFoundError()
        subprocess.check_output = file_not_found_error

        # groups command doesn't exist, so cannot check this suff
        self.assertIsNone(check_group('plugdev'))
        # which doesn't affect the grp lib
        self.assertIsNotNone(check_group('foobar'))


if __name__ == "__main__":
    unittest.main()
