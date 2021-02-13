#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@hip70890b.de>
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


"""Functions to handle numlocks.

For unknown reasons the numlock status can change when starting injections,
which is why these functions exist.
"""


import re
import subprocess

from keymapper.logger import logger


def is_numlock_on():
    """Get the current state of the numlock."""
    try:
        xset_q = subprocess.check_output(
            ['xset', 'q'],
            stderr=subprocess.STDOUT
        ).decode()
        num_lock_status = re.search(
            r'Num Lock:\s+(.+?)\s',
            xset_q
        )

        if num_lock_status is not None:
            return num_lock_status[1] == 'on'

        return False
    except (FileNotFoundError, subprocess.CalledProcessError):
        # tty
        return None


def set_numlock(state):
    """Set the numlock to a given state of True or False."""
    if state is None:
        return

    value = {
        True: 'on',
        False: 'off'
    }[state]

    try:
        subprocess.check_output(['numlockx', value])
    except subprocess.CalledProcessError:
        # might be in a tty
        pass
    except FileNotFoundError:
        # doesn't seem to be installed everywhere
        logger.debug('numlockx not found')


def ensure_numlock(func):
    """Decorator to reset the numlock to its initial state afterwards."""
    def wrapped(*args, **kwargs):
        # for some reason, grabbing a device can modify the num lock state.
        # remember it and apply back later
        numlock_before = is_numlock_on()

        result = func(*args, **kwargs)

        set_numlock(numlock_before)

        return result
    return wrapped
