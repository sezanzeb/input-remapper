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


"""Get stuff from /usr/share/input-remapper, depending on the prefix."""


import os
import site
import sys

import pkg_resources

from inputremapper.logger import logger

logged = False


def _try_standard_locations():
    # https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html
    # ensure at least /usr/local/share/ and /usr/share/ are tried
    xdg_data_dirs = set(
        os.environ.get("XDG_DATA_DIRS", "").split(":")
        + [
            "/usr/local/share/",
            "/usr/share/",
            os.path.join(site.USER_BASE, "share/"),
        ]
    )

    for xdg_data_dir in xdg_data_dirs:
        candidate = os.path.join(xdg_data_dir, "input-remapper")
        if os.path.exists(candidate):
            return candidate

    return None


def _try_python_package_location():
    """Look for the data dir at the packages installation location."""
    source = None
    try:
        source = pkg_resources.require("input-remapper")[0].location
        # failed in some ubuntu installations
    except Exception:
        logger.debug("failed to figure out package location")
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


def _try_env_data_dir():
    """Check if input-remappers data can be found at DATA_DIR."""
    data_dir = os.environ.get("DATA_DIR", None)
    print('lakdjs', data_dir)

    if data_dir is None:
        return None

    if os.path.exists(data_dir):
        return data_dir
    else:
        logger.error(f'"{ data_dir }" does not exist')

    return None


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

    data = (
        _try_env_data_dir()
        or _try_python_package_location()
        or _try_standard_locations()
    )

    if data is None:
        logger.error("Could not find the application data")
        sys.exit(10)

    if not logged:
        logger.debug('Found data at "%s"', data)
        logged = True

    return os.path.join(data, filename)
