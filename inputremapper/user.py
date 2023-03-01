# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2023 sezanzeb <proxima@sezanzeb.de>
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


"""Figure out the user."""


import os
import getpass
import pwd


def get_user():
    """Try to find the user who called sudo/pkexec."""
    try:
        return os.getlogin()
    except OSError:
        # failed in some ubuntu installations and in systemd services
        pass

    try:
        user = os.environ["USER"]
    except KeyError:
        # possibly the systemd service. no sudo was used
        return getpass.getuser()

    if user == "root":
        try:
            return os.environ["SUDO_USER"]
        except KeyError:
            # no sudo was used
            pass

        try:
            pkexec_uid = int(os.environ["PKEXEC_UID"])
            return pwd.getpwuid(pkexec_uid).pw_name
        except KeyError:
            # no pkexec was used or the uid is unknown
            pass

    return user


def get_home(user):
    """Try to find the user's home directory."""
    return pwd.getpwnam(user).pw_dir


USER = get_user()

HOME = get_home(USER)

CONFIG_PATH = os.path.join(HOME, ".config/input-remapper")
