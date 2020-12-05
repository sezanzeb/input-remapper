#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2020 sezanzeb <proxima@hip70890b.de>
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


"""To check if access to devices in /dev is possible."""


import grp
import getpass
import os

from keymapper.logger import logger
from keymapper.paths import USER


def check_group(group):
    """Check if the user can access files of that group.

    Returns True if this group doesn't even exist.
    """
    try:
        return USER in grp.getgrnam(group).gr_mem
    except KeyError:
        return True


def can_read_devices():
    """If the people ever looks into the console, make sure to help them."""
    is_root = getpass.getuser() == 'root'
    is_input = check_group('input')
    is_plugdev = check_group('plugdev')

    # ubuntu. funnily, individual devices in /dev/input/ have write permitted.
    can_write = os.access('/dev/uinput', os.W_OK)

    def warn(group):
        logger.warning(
            'Some devices may not be visible without being in the '
            '"%s" user group. Try `sudo usermod -a -G %s %s` '
            'and log out and back in.',
            group,
            group,
            USER
        )

    if not is_root:
        if not is_plugdev:
            warn('plugdev')
        if not is_input:
            warn('input')
        if not can_write:
            logger.error(
                'Injecting keycodes into /dev/uinput is not permitted. '
                'Either use sudo or run '
                '`sudo setfacl -m u:%s:rw- /dev/uinput`',
                {USER}
            )

    permitted = (is_root or (is_input and is_plugdev)) and can_write

    return permitted, is_root, is_input, is_plugdev, can_write
