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


"""Get stuff from /usr/share/key-mapper, depending on the prefix."""


import os
import site
import pkg_resources


def get_data_path(filename=''):
    """Depending on the installation prefix, return the data dir."""
    source_path = pkg_resources.require('key-mapper')[0].location

    # depending on where this file is installed to, make sure to use the proper
    # prefix path for data
    # https://docs.python.org/3/distutils/setupscript.html?highlight=package_data#installing-additional-files # noqa pylint: disable=line-too-long
    if source_path.startswith(site.USER_BASE):
        data_path = os.path.join(site.USER_BASE, 'share/key-mapper')
    elif source_path.startswith('/usr/local/'):
        data_path = '/usr/local/share/key-mapper'
    elif source_path.startswith('/usr/'):
        data_path = '/usr/share/key-mapper'
    else:
        # installed with -e, running from the cloned git source
        data_path = os.path.join(source_path, 'data')

    return os.path.join(data_path, filename)
