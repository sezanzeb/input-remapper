#!/usr/bin/python3
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

from __future__ import annotations

import os
import subprocess
import tracemalloc

from tests.lib.cleanup import cleanup, quick_cleanup
from tests.lib.fixtures import fixtures
from tests.lib.logger import update_inputremapper_verbosity
from tests.lib.patches import create_patches
from tests.lib.pipes import setup_pipe, close_pipe


def get_project_root():
    """Find the projects root, i.e. the uppermost directory of the repo."""
    # when tests are started in pycharm via the green arrow, the working directory
    # is not the project root. Go up until it is found.
    root = os.getcwd()
    for _ in range(10):
        if "setup.py" in os.listdir(root):
            return root

        root = os.path.dirname(root)

    raise Exception("Could not find project root")


def is_service_running():
    """Check if the daemon is running."""
    try:
        subprocess.check_output(["pgrep", "-f", "input-remapper-service"])
        return True
    except subprocess.CalledProcessError:
        return False


def create_fixture_pipes():
    # make sure those pipes exist before any process (the reader-service) gets forked,
    # so that events can be pushed after the fork.
    for _fixture in fixtures:
        setup_pipe(_fixture)


def remove_fixture_pipes():
    for _fixture in fixtures:
        close_pipe(_fixture)


def setup_tests(cls):
    """A class decorator to
    - apply the patches to all tests
    - check if the deamon is already running
    - create pipes to send events to the reader service
    - reset stuff automatically
    """
    original_setUp = cls.setUp
    original_tearDown = cls.tearDown
    original_setUpClass = cls.setUpClass
    original_tearDownClass = cls.tearDownClass

    tracemalloc.start()
    os.environ["UNITTEST"] = "1"
    update_inputremapper_verbosity()

    patches = create_patches()

    def setUpClass():
        if is_service_running():
            # let tests control daemon existance
            raise Exception("Expected the service not to be running already.")

        create_fixture_pipes()

        original_setUpClass()

    def tearDownClass():
        original_tearDownClass()

        remove_fixture_pipes()

        # Do the more thorough cleanup after all tests of classes, because it slows
        # tests down. If this is required after each test, call it in your tearDown
        # method.
        cleanup()

    def setUp(self):
        for patch in patches:
            patch.start()

        original_setUp(self)

    def tearDown(self):
        original_tearDown(self)

        # TODO remove quick_cleanup calls from tearDown methods
        quick_cleanup()

        for patch in patches:
            patch.stop()

    cls.setUp = setUp
    cls.tearDown = tearDown
    cls.setUpClass = setUpClass
    cls.tearDownClass = tearDownClass

    return cls
