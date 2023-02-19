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

from __future__ import annotations

import asyncio
import copy
import os
import subprocess
import time
from pickle import UnpicklingError

import evdev

from inputremapper.utils import get_evdev_constant_name
from tests.lib.constants import EVENT_READ_TIMEOUT, MIN_ABS, MAX_ABS
from tests.lib.fixtures import Fixture, fixtures, new_event
from tests.lib.pipes import (
    setup_pipe,
    push_events,
    uinput_write_history,
    uinput_write_history_pipe,
    pending_events,
)
from tests.lib.xmodmap import xmodmap
from tests.lib.tmp import tmp
from tests.lib.logger import logger


def patch_paths():
    from inputremapper import user

    user.HOME = tmp


class InputDevice:
    # expose as existing attribute, otherwise the patch for
    # evdev < 1.0.0 will crash the test
    path = None

    def __init__(self, path):
        if path != "justdoit" and not fixtures.get(path):
            # beware that fixtures keys and the path attribute of a fixture can
            # theoretically be different. I don't know if this is the case right now
            logger.error(
                'path "%s" was not found in fixtures. available: %s',
                path,
                list(fixtures.get_paths()),
            )
            raise FileNotFoundError()
        if path == "justdoit":
            self._fixture = Fixture(path="justdoit")
        else:
            self._fixture = fixtures[path]

        self.path = path
        self.phys = self._fixture.phys
        self.info = self._fixture.info
        self.name = self._fixture.name

        # this property exists only for test purposes and is not part of
        # the original evdev.InputDevice class
        self.group_key = self._fixture.group_key or self._fixture.name

        # ensure a pipe exists to make this object act like
        # it is reading events from a device
        setup_pipe(self._fixture)

        self.fd = pending_events[self._fixture][1].fileno()

    def push_events(self, events):
        push_events(self._fixture, events)

    def fileno(self):
        """Compatibility to select.select."""
        return self.fd

    def log(self, key, msg):
        logger.info(f'%s "%s" "%s" %s', msg, self.name, self.path, key)

    def absinfo(self, *args):
        raise Exception("Ubuntus version of evdev doesn't support .absinfo")

    def grab(self):
        logger.info("grab %s %s", self.name, self.path)

    def ungrab(self):
        logger.info("ungrab %s %s", self.name, self.path)

    async def async_read_loop(self):
        logger.info("starting read loop for %s", self.path)
        new_frame = asyncio.Event()
        asyncio.get_running_loop().add_reader(self.fd, new_frame.set)
        while True:
            await new_frame.wait()
            new_frame.clear()
            if not pending_events[self._fixture][1].poll():
                # todo: why? why do we need this?
                # sometimes this happens, as if a other process calls recv on
                # the pipe
                continue

            event = pending_events[self._fixture][1].recv()
            logger.info("got %s at %s", event, self.path)
            yield event

    def read(self):
        # the patched fake InputDevice objects read anything pending from
        # that group.
        # To be realistic it would have to check if the provided
        # element is in its capabilities.
        if self.group_key not in pending_events:
            self.log("no events to read", self.group_key)
            return

        # consume all of them
        while pending_events[self._fixture][1].poll():
            event = pending_events[self._fixture][1].recv()
            self.log(event, "read")
            yield event
            time.sleep(EVENT_READ_TIMEOUT)

    def read_loop(self):
        """Endless loop that yields events."""
        while True:
            event = pending_events[self._fixture][1].recv()
            if event is not None:
                self.log(event, "read_loop")
                yield event
            time.sleep(EVENT_READ_TIMEOUT)

    def read_one(self):
        """Read one event or none if nothing available."""
        if not pending_events.get(self._fixture):
            return None

        if not pending_events[self._fixture][1].poll():
            return None

        try:
            event = pending_events[self._fixture][1].recv()
        except (UnpicklingError, EOFError):
            # failed in tests sometimes
            return None

        self.log(event, "read_one")
        return event

    def capabilities(self, absinfo=True, verbose=False):
        result = copy.deepcopy(self._fixture.capabilities)

        if absinfo and evdev.ecodes.EV_ABS in result:
            absinfo_obj = evdev.AbsInfo(
                value=None,
                min=MIN_ABS,
                fuzz=None,
                flat=None,
                resolution=None,
                max=MAX_ABS,
            )

            ev_abs = []
            for ev_code in result[evdev.ecodes.EV_ABS]:
                if ev_code in range(0x10, 0x18):  # ABS_HAT0X - ABS_HAT3Y
                    absinfo_obj = evdev.AbsInfo(
                        value=None,
                        min=-1,
                        fuzz=None,
                        flat=None,
                        resolution=None,
                        max=1,
                    )
                ev_abs.append((ev_code, absinfo_obj))

            result[evdev.ecodes.EV_ABS] = ev_abs

        return result

    def input_props(self):
        return []


uinputs = {}


class UInput:
    def __init__(self, events=None, name="unnamed", *args, **kwargs):
        self.fd = 0
        self.write_count = 0
        self.device = InputDevice("justdoit")
        self.name = name
        self.events = events
        self.write_history = []

        global uinputs
        uinputs[name] = self

    def capabilities(self, verbose=False, absinfo=True):
        if absinfo or 3 not in self.events:
            return self.events
        else:
            events = self.events.copy()
            events[3] = [code for code, _ in self.events[3]]
            return events

    def write(self, type, code, value):
        self.write_count += 1
        event = new_event(type, code, value, time.time())
        uinput_write_history.append(event)
        uinput_write_history_pipe[1].send(event)
        self.write_history.append(event)
        logger.info(
            '%s %s written to "%s"',
            (type, code, value),
            get_evdev_constant_name(type, code),
            self.name,
        )

    def syn(self):
        pass


def patch_evdev():
    def list_devices():
        return [fixture_.path for fixture_ in fixtures]

    class PatchedInputEvent(evdev.InputEvent):
        def __init__(self, sec, usec, type, code, value):
            self.t = (type, code, value)
            super().__init__(sec, usec, type, code, value)

        def copy(self):
            return PatchedInputEvent(
                self.sec,
                self.usec,
                self.type,
                self.code,
                self.value,
            )

    evdev.list_devices = list_devices
    evdev.InputDevice = InputDevice
    evdev.UInput = UInput
    evdev.InputEvent = PatchedInputEvent


def patch_events():
    # improve logging of stuff
    evdev.InputEvent.__str__ = lambda self: (
        f"InputEvent{(self.type, self.code, self.value)}"
    )


def patch_os_system():
    """Avoid running pkexec."""
    original_system = os.system

    def system(command):
        if "pkexec" in command:
            # because it
            # - will open a window for user input
            # - has no knowledge of the fixtures and patches
            raise Exception("Write patches to avoid running pkexec stuff")
        return original_system(command)

    os.system = system


def patch_check_output():
    """Xmodmap -pke should always return a fixed set of symbols.

    On some installations the `xmodmap` command might be missig completely,
    which would break the tests.
    """
    original_check_output = subprocess.check_output

    def check_output(command, *args, **kwargs):
        if "xmodmap" in command and "-pke" in command:
            return xmodmap
        return original_check_output(command, *args, **kwargs)

    subprocess.check_output = check_output


def patch_regrab_timeout():
    # no need for a high number in tests
    from inputremapper.injection.injector import Injector

    Injector.regrab_timeout = 0.05


def is_running_patch():
    logger.info("is_running is patched to always return True")
    return True


def patch_is_running():
    from inputremapper.gui.reader_service import ReaderService

    setattr(ReaderService, "is_running", is_running_patch)


class FakeDaemonProxy:
    def __init__(self):
        self.calls = {
            "stop_injecting": [],
            "get_state": [],
            "start_injecting": [],
            "stop_all": 0,
            "set_config_dir": [],
            "autoload": 0,
            "autoload_single": [],
            "hello": [],
        }

    def stop_injecting(self, group_key: str) -> None:
        self.calls["stop_injecting"].append(group_key)

    def get_state(self, group_key: str):
        from inputremapper.injection.injector import InjectorState

        self.calls["get_state"].append(group_key)
        return InjectorState.STOPPED

    def start_injecting(self, group_key: str, preset: str) -> bool:
        self.calls["start_injecting"].append((group_key, preset))
        return True

    def stop_all(self) -> None:
        self.calls["stop_all"] += 1

    def set_config_dir(self, config_dir: str) -> None:
        self.calls["set_config_dir"].append(config_dir)

    def autoload(self) -> None:
        self.calls["autoload"] += 1

    def autoload_single(self, group_key: str) -> None:
        self.calls["autoload_single"].append(group_key)

    def hello(self, out: str) -> str:
        self.calls["hello"].append(out)
        return out
