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

import shutil
import time
import copy
import unittest
import subprocess
import asyncio
import psutil
from pickle import UnpicklingError
from unittest.mock import patch

os.environ["UNITTEST"] = "1"

from tests.logger import logger
from tests.constants import EVENT_READ_TIMEOUT
from tests.tmp import tmp
from tests.fixtures import fixtures
from tests.pipes import (
    setup_pipe,
    pending_events,
    uinput_write_history,
    uinput_write_history_pipe,
)
from tests.patches import (
    patch_paths,
    patch_events,
    patch_os_system,
    patch_check_output,
    patch_regrab_timeout,
    patch_is_running,
    patch_evdev,
    uinputs,
    InputEvent,
)


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


def new_event(type, code, value, timestamp=None, offset=0):
    """Create a new input_event."""
    if timestamp is None:
        timestamp = time.time() + offset

    sec = int(timestamp)
    usec = timestamp % 1 * 1000000
    event = InputEvent(sec, usec, type, code, value)
    return event


def clear_write_history():
    """Empty the history in preparation for the next test."""
    while len(uinput_write_history) > 0:
        uinput_write_history.pop()
    while uinput_write_history_pipe[0].poll():
        uinput_write_history_pipe[0].recv()


# applying patches before importing input-remappers modules is important, otherwise
# input-remapper might use un-patched modules. Importing modules from inputremapper
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


environ_copy = copy.deepcopy(os.environ)


def quick_cleanup(log=True):
    """Reset the applications state."""
    from inputremapper.gui.utils import debounce_manager
    from inputremapper.configs.global_config import global_config
    from inputremapper.injection.macros.macro import macro_variables
    from inputremapper.configs.system_mapping import system_mapping
    from inputremapper.configs.paths import get_config_path
    from inputremapper.injection.global_uinputs import global_uinputs

    if log:
        print("Quick cleanup...")

    debounce_manager.stop_all()

    for device in list(pending_events.keys()):
        try:
            while pending_events[device][1].poll():
                pending_events[device][1].recv()
        except (UnpicklingError, EOFError):
            pass

        # setup new pipes for the next test
        pending_events[device][1].close()
        pending_events[device][0].close()
        del pending_events[device]
        setup_pipe(device)

    try:
        if asyncio.get_event_loop().is_running():
            for task in asyncio.all_tasks():
                task.cancel()
    except RuntimeError:
        # happens when the event loop disappears for magical reasons
        # create a fresh event loop
        asyncio.set_event_loop(asyncio.new_event_loop())

    if macro_variables.process is not None and not macro_variables.process.is_alive():
        # nothing should stop the process during runtime, if it has been started by
        # the injector once
        raise AssertionError("the SharedDict manager is not running anymore")

    if macro_variables.process is not None:
        macro_variables._stop()

    join_children()

    macro_variables.start()

    if os.path.exists(tmp):
        shutil.rmtree(tmp)

    global_config.path = os.path.join(get_config_path(), "config.json")
    global_config.clear_config()
    global_config._save_config()

    system_mapping.populate()

    clear_write_history()

    for name in list(uinputs.keys()):
        del uinputs[name]

    # for device in list(active_macros.keys()):
    #    del active_macros[device]
    # for device in list(unreleased.keys()):
    #    del unreleased[device]
    fixtures.reset()
    os.environ.update(environ_copy)
    for device in list(os.environ.keys()):
        if device not in environ_copy:
            del os.environ[device]

    for _, pipe in pending_events.values():
        assert not pipe.poll()

    assert macro_variables.is_alive(1)
    for uinput in global_uinputs.devices.values():
        uinput.write_count = 0
        uinput.write_history = []

    global_uinputs.is_service = True

    if log:
        print("Quick cleanup done")


def cleanup():
    """Reset the applications state.

    Using this is slower, usually quick_cleanup() is sufficient.
    """
    from inputremapper.groups import groups
    from inputremapper.injection.global_uinputs import global_uinputs

    print("Cleanup...")

    os.system("pkill -f input-remapper-service")
    os.system("pkill -f input-remapper-control")
    time.sleep(0.05)

    quick_cleanup(log=False)
    groups.refresh()
    with patch.object(sys, "argv", ["input-remapper-service"]):
        global_uinputs.prepare_all()

    print("Cleanup done")


def spy(obj, name):
    """Convenient wrapper for patch.object(..., ..., wraps=...)."""
    return patch.object(obj, name, wraps=obj.__getattribute__(name))


cleanup()


def main():
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
