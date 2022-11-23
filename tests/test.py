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


"""Sets up input-remapper for the tests and runs them.

This module needs to be imported first in test files.
"""

from __future__ import annotations

import argparse
import os
import sys
import tracemalloc

tracemalloc.start()

# ensure nothing has loaded
if module := sys.modules.get("inputremapper"):
    imported = [m for m in module.__dict__ if not m.startswith("__")]
    raise AssertionError(
        f"The modules {imported} from inputremapper where already imported, this can "
        f"cause issues with the tests. Make sure to always import tests.test before any"
        f" inputremapper module."
    )
try:
    sys.modules.get("tests.test").main
    raise AssertionError(
        "test.py was already imported. "
        "Always use 'from tests.test import ...' "
        "not 'from test import ...' to import this"
    )
    # have fun debugging infinitely blocking tests without this
except AttributeError:
    pass


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


# make sure the "tests" module visible
sys.path.append(get_project_root())
if __name__ == "__main__":
    # import this file to itself to make sure is not run twice and all global
    # variables end up in sys.modules
    # https://stackoverflow.com/questions/13181559/importing-modules-main-vs-import-as-module
    import tests.test

    tests.test.main()

import time
import unittest
import subprocess
import psutil

os.environ["UNITTEST"] = "1"

from tests.lib.logger import logger
from tests.lib.constants import EVENT_READ_TIMEOUT
from tests.lib.fixtures import fixtures
from tests.lib.pipes import setup_pipe
from tests.lib.patches import (
    patch_paths,
    patch_events,
    patch_os_system,
    patch_check_output,
    patch_regrab_timeout,
    patch_is_running,
    patch_evdev,
)
from tests.lib.cleanup import cleanup


def is_service_running():
    """Check if the daemon is running."""
    try:
        subprocess.check_output(["pgrep", "-f", "input-remapper-service"])
        return True
    except subprocess.CalledProcessError:
        return False


def join_children():
    """Wait for child processes to exit. Stop them if it takes too long."""
    this = psutil.Process(os.getpid())

    i = 0
    time.sleep(EVENT_READ_TIMEOUT)
    children = this.children(recursive=True)
    while len([c for c in children if c.status() != "zombie"]) > 0:
        for child in children:
            if i > 10:
                child.kill()
                logger.info("Killed pid %s because it didn't finish in time", child.pid)

        children = this.children(recursive=True)
        time.sleep(EVENT_READ_TIMEOUT)
        i += 1


if is_service_running():
    # let tests control daemon existance
    raise Exception("Expected the service not to be running already.")


# make sure those pipes exist before any process (the reader-service) gets forked,
# so that events can be pushed after the fork.
for _fixture in fixtures:
    setup_pipe(_fixture)


# applying patches before importing input-remappers modules is important, otherwise
# input-remapper might use non-patched modules. Importing modules from inputremapper
# just-in-time in the test-setup functions instead of globally helps. This way,
# it is ensured that the patches on evdev and such are already applied, without having
# to take care about ordering the files in a special way.
patch_paths()
patch_evdev()
patch_events()
patch_os_system()
patch_check_output()
patch_regrab_timeout()
patch_is_running()
# patch_warnings()


def main():
    cleanup()
    # https://docs.python.org/3/library/argparse.html
    parser = argparse.ArgumentParser(description=__doc__)
    # repeated argument 0 or more times with modules
    parser.add_argument("modules", type=str, nargs="*")
    # start-dir value if not using modules, allows eg python tests/test.py --start-dir unit
    parser.add_argument("--start-dir", type=str, default=".")
    parsed_args = parser.parse_args()  # takes from sys.argv by default
    modules = parsed_args.modules

    # discoverer is really convenient, but it can't find a specific test
    # in all of the available tests like unittest.main() does...,
    # so provide both options.
    if len(modules) > 0:
        # for example
        # `tests/test.py integration.test_gui.TestGui.test_can_start`
        # or `tests/test.py integration.test_gui integration.test_daemon`
        testsuite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    else:
        # run all tests by default
        testsuite = unittest.defaultTestLoader.discover(
            parsed_args.start_dir, pattern="test_*.py"
        )

    # add a newline to each "qux (foo.bar)..." output before each test,
    # because the first log will be on the same line otherwise
    original_start_test = unittest.TextTestResult.startTest

    def start_test(self, test):
        original_start_test(self, test)
        print()

    unittest.TextTestResult.startTest = start_test
    result = unittest.TextTestRunner(verbosity=2).run(testsuite)
    sys.exit(not result.wasSuccessful())
