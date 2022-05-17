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


"""Get stuff from /usr/share/input-remapper, depending on the prefix."""


import sys
import os
import site
import sysconfig

import pkg_resources

from inputremapper.logger import logger


logged = False


def get_data_path(filename=""):
    """Depending on the installation prefix, return the data dir.

    Since it is a nightmare to get stuff installed with pip across
    distros this is somewhat complicated. Ubuntu uses /usr/local/share
    for data_files (setup.py) and manjaro uses /usr/share.
    """
    global logged

    source = None
    try:
        source = pkg_resources.require("input-remapper")[0].location
        # failed in some ubuntu installations
    except pkg_resources.DistributionNotFound:
        pass

    # depending on where this file is installed to, make sure to use the proper
    # prefix path for data
    # https://docs.python.org/3/distutils/setupscript.html?highlight=package_data#installing-additional-files # noqa pylint: disable=line-too-long

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

    # stupid workaround for github actions:
    # TODO remove this, fix github actions
    path = sysconfig.get_path("platlib")
    path1 = os.path.join(path, "usr/share/input-remapper")
    if path.endswith("site-packages"):
        path2 = os.path.join(path[:-14], "dist-packages/usr/share/input-remapper")
    else:
        path2 = os.path.join(path[:-14], "site-packages/usr/share/input-remapper")
    if not path.startswith("/usr/local"):
        path3 = os.path.join("/usr/local", path1[5:])
        path4 = os.path.join("/usr/local", path2[5:])
    else:
        path3 = os.path.join("/usr", path1[11:])
        path4 = os.path.join("/usr", path2[11:])

    candidates = [
        os.path.join(sysconfig.get_path("data"), "share/input-remapper"),
        "/usr/share/input-remapper",
        "/usr/local/share/input-remapper",
        os.path.join(site.USER_BASE, "share/input-remapper"),
        # "/usr/local/lib/python3.8/dist-packages/usr/share/input-remapper/",
        path1,
        path2,
        path3,
        path4,
    ]

    if data is None:
        # try any of the options
        for candidate in candidates:
            if os.path.exists(candidate):
                data = candidate
                break

        if data is None:
            logger.error("Could not find the application data")
            sys.exit(10)

    if not logged:
        logger.debug('Found data at "%s"', data)
        logged = True

    return os.path.join(data, filename)
