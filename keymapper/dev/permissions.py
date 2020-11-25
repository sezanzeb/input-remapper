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


import os
import sys
import grp
import getpass

from keymapper.logger import logger


def can_read_devices():
    """If the people ever looks into the console, make sure to help them."""
    is_root = getpass.getuser() == 'root'
    is_test = 'unittest' in sys.modules.keys()
    is_in_input_group = os.getlogin() in grp.getgrnam('input').gr_mem
    is_in_plugdev_group = os.getlogin() in grp.getgrnam('plugdev').gr_mem

    def warn(group):
        logger.warning(
            'Some devices may not be visible without being in the '
            f'"{group}" user group. Try `sudo usermod -a -G {group} $USER` '
            'and log out and back in.'
        )

    if not is_root and not is_test:
        if not is_in_plugdev_group:
            warn('plugdev')
        if not is_in_input_group:
            warn('input')

    return is_root or is_test or is_in_input_group
