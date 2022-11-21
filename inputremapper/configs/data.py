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


"""Get stuff from /usr/share/input-remapper, depending on the prefix."""


import os
import site
import sys

import pkg_resources

from inputremapper.logger import logger

logged = False


def _try_standard_locations():
    """Look for the data dir where it typically can be found."""
    candidates = [
        "/usr/share/input-remapper",
        "/usr/local/share/input-remapper",
        os.path.join(site.USER_BASE, "share/input-remapper"),
    ]

    # try any of the options
    for candidate in candidates:
        if os.path.exists(candidate):
            data = candidate
            break

    return data


def _try_python_package_location():
    """Look for the data dir at the packages installation location."""
    source = None
    try:
        source = pkg_resources.require("input-remapper")[0].location
        # failed in some ubuntu installations
    except pkg_resources.DistributionNotFound:
        logger.debug("DistributionNotFound")
        pass

    data = None
    # python3.8/dist-packages python3.7/site-packages, /usr/share,
    # /usr/local/share, endless options
    if source and "-packages" not in source and "python" not in source:
        # probably installed with -e, running from the cloned git source
        data = os.path.join(source, "data")
        if not os.path.exists(data):
            if not logged:
                logger.debug('-e, but data missing at "%s"', data)
            data = None

    return data


def get_data_path(filename=""):
    """Depending on the installation prefix, return the data dir.

    Since it is a nightmare to get stuff installed with pip across
    distros this is somewhat complicated. Ubuntu uses /usr/local/share
    for data_files (setup.py) and manjaro uses /usr/share.
    """
    global logged

    # depending on where this file is installed to, make sure to use the proper
    # prefix path for data
    # https://docs.python.org/3/distutils/setupscript.html?highlight=package_data#installing-additional-files # noqa pylint: disable=line-too-long

    data = _try_python_package_location() or _try_standard_locations()

    if data is None:
        logger.error("Could not find the application data")
        sys.exit(10)

    if not logged:
        logger.debug('Found data at "%s"', data)
        logged = True

    return os.path.join(data, filename)
