#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ALSA-Control - ALSA configuration interface
# Copyright (C) 2020 sezanzeb <proxima@hip70890b.de>
#
# This file is part of ALSA-Control.
#
# ALSA-Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ALSA-Control is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with ALSA-Control.  If not, see <https://www.gnu.org/licenses/>.


"""Query settings."""


import os
import site
import pkg_resources


def get_data_path():
    """Depending on the installation prefix, return the data dir."""
    source_path = pkg_resources.require('keymapper')[0].location

    # depending on where this file is installed to, make sure to use the proper
    # prefix path for data
    # https://docs.python.org/3/distutils/setupscript.html?highlight=package_data#installing-additional-files # noqa
    if source_path.startswith(site.USER_BASE):
        data_path = os.path.join(site.USER_BASE, 'share/key-mapper')
    elif source_path.startswith('/usr/local/'):
        data_path = '/usr/local/share/key-mapper'
    elif source_path.startswith('/usr/'):
        data_path = '/usr/share/key-mapper'
    else:
        # installed with -e, running from the cloned git source
        data_path = os.path.join(source_path, 'data')

    return data_path
