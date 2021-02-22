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


"""To check if access to devices in /dev is possible."""


import grp
import glob
import getpass
import subprocess
import os

from keymapper.logger import logger
from keymapper.paths import USER
from keymapper.daemon import is_service_running


def check_group(group):
    """Check if the required group is active and log if not."""
    try:
        in_group = USER in grp.getgrnam(group).gr_mem
    except KeyError:
        # group doesn't exist. Ignore
        return None

    # check if files exist with that group in /dev. Even if plugdev
    # exists, that doesn't mean that it is needed.
    used_groups = [os.stat(path).st_gid for path in glob.glob('/dev/input/*')]
    if grp.getgrnam(group).gr_gid not in used_groups:
        return None

    if not in_group:
        msg = (
            'Some devices may not be accessible without being in the '
            f'"{group}" user group.'
        )
        logger.warning(msg)
        return msg

    try:
        groups = subprocess.check_output('groups').decode().split()
        group_active = group in groups
    except FileNotFoundError:
        # groups command missing. Idk if any distro doesn't have it
        # but if so, cover the case.
        return None

    if in_group and not group_active:
        msg = (
            f'You are in the "{group}" group, but your session is not yet '
            'using it. Some devices may not be accessible. Please log out and '
            'back in or restart'
        )
        logger.warning(msg)
        return msg

    return None


def check_injection_rights():
    """Check if the user may write into /dev/uinput."""
    if not os.access('/dev/uinput', os.W_OK):
        msg = (
            'Rights to write to /dev/uinput are missing, keycodes cannot '
            'be injected.'
        )
        logger.error(msg)
        return msg

    return None


def can_read_devices():
    """Get a list of problems before key-mapper can be used properly."""
    if getpass.getuser() == 'root':
        return []

    input_check = check_group('input')
    plugdev_check = check_group('plugdev')

    # ubuntu. funnily, individual devices in /dev/input/ have write permitted.
    if not is_service_running():
        can_write = check_injection_rights()
    else:
        can_write = None

    ret = [
        check for check
        in [can_write, input_check, plugdev_check]
        if check is not None
    ]

    return ret
