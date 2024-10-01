#!/usr/bin/python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2024 sezanzeb <b8x45ygc9@mozmail.com>
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
import tracemalloc

from inputremapper.configs.global_config import global_config
from inputremapper.configs.paths import PathUtils
from tests.lib.cleanup import cleanup, quick_cleanup
from tests.lib.fixture_pipes import create_fixture_pipes, remove_fixture_pipes
from tests.lib.is_service_running import is_service_running
from tests.lib.logger import update_inputremapper_verbosity
from tests.lib.patches import create_patches


def test_setup(cls):
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

        # I don't know. Somehow tearDownClass is called before the test, so lets
        # make sure the patches are started already when the class is set up, so that
        # an unpatched `prepare_all` doesn't take ages to finish, and doesn't do funky
        # stuff with the real evdev.
        for patch in patches:
            patch.start()

        # TODO if global_config is injected instead, it could work without doing this
        #  load_config call here. Because right now the constructor uses variables
        #  that are unpatched once global_config.py is imported.
        global_config.path = os.path.join(
            PathUtils.config_path(),
            "config.json",
        )

        original_setUpClass()

    def tearDownClass():
        original_tearDownClass()

        remove_fixture_pipes()

        # Do the more thorough cleanup only after all tests of classes, because it
        # slows tests down. If this is required after each test, call it in your
        # tearDown method.
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
