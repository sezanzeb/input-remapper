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

import os
import sys
import shutil
import time
import asyncio
import psutil
from pickle import UnpicklingError
from unittest.mock import patch

from tests.logger import logger
from tests.pipes import (
    uinput_write_history_pipe,
    uinput_write_history,
    pending_events,
    setup_pipe,
)
from tests.constants import EVENT_READ_TIMEOUT
from tests.tmp import tmp
from tests.fixtures import fixtures
from tests.test import environ_copy
from tests.patches import uinputs

from inputremapper.injection.macros.macro import macro_variables
from inputremapper.configs.global_config import global_config
from inputremapper.groups import groups
from inputremapper.configs.system_mapping import system_mapping
from inputremapper.gui.utils import debounce_manager
from inputremapper.configs.paths import get_config_path
from inputremapper.injection.global_uinputs import global_uinputs


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


def clear_write_history():
    """Empty the history in preparation for the next test."""
    while len(uinput_write_history) > 0:
        uinput_write_history.pop()
    while uinput_write_history_pipe[0].poll():
        uinput_write_history_pipe[0].recv()


def quick_cleanup(log=True):
    """Reset the applications state."""
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
    print("Cleanup...")

    os.system("pkill -f input-remapper-service")
    os.system("pkill -f input-remapper-control")
    time.sleep(0.05)

    quick_cleanup(log=False)
    groups.refresh()
    with patch.object(sys, "argv", ["input-remapper-service"]):
        global_uinputs.prepare_all()

    print("Cleanup done")
