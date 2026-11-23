# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2026 sezanzeb <4t1pzast9@mozmail.com>
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


"""Starts the beta user interface: `python3 -m inputremapper.bin.input_remapper_beta`."""

from __future__ import annotations

import glob
import os
import subprocess
import sys
from argparse import ArgumentParser
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from inputremapper.bin.process_utils import ProcessUtils
from inputremapper.configs.paths import PathUtils
from inputremapper.daemon import Daemon
from inputremapper.groups import _Groups
from inputremapper.gui.reader_service import ReaderService
from inputremapper.gui_v3.controller import Controller
from inputremapper.gui_v3.recorder import Recorder, RecorderError
from inputremapper.gui_v3.store import default_profiles_dir
from inputremapper.gui_v3.window import Window
from inputremapper.ipc.pipe import Pipe
from inputremapper.logging.logger import logger


def ensure_reader_service() -> bool:
    """Start the root helper that reads keys, if it isn't running yet.

    Returns whether it was started just now.

    It is started from this source tree and not via `input-remapper-control`: that
    would run whichever version is installed on the system, which may use different
    pipe paths than this code, and then the two never find each other.
    """
    if ProcessUtils.count_python_processes("input-remapper-reader-service") >= 1:
        return False

    root = Path(__file__).resolve().parents[2]
    command = [
        "env",
        f"PYTHONPATH={root}",
        sys.executable,
        str(root / "bin" / "input-remapper-reader-service"),
    ]
    # Same rule as the old GUI: only ask for a password if devices aren't readable.
    devices = glob.glob("/dev/input/event*")
    if not (devices and all(os.access(path, os.R_OK) for path in devices)):
        command.insert(0, "pkexec")

    logger.debug("Running `%s`", " ".join(command))
    try:
        subprocess.Popen(
            command,
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as error:
        raise RecorderError(f"Could not start the reader service: {error}") from error
    return True


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("-d", "--debug", action="store_true", dest="debug")
    options = parser.parse_args(sys.argv[1:])
    logger.update_verbosity(options.debug)
    logger.log_info("input-remapper beta GUI")

    daemon = Daemon.connect()

    # The pipes must be created by this (unprivileged) process before the reader
    # service starts, otherwise the service owns them and we can't read them.
    results_path, commands_path = ReaderService.get_pipe_paths()
    recorder = Recorder(Pipe(results_path), Pipe(commands_path), ensure_reader_service)
    GLib.timeout_add(30, lambda: recorder.poll() or True)
    controller = Controller(
        daemon,
        _Groups(),
        default_profiles_dir(),
        PathUtils.get_preset_path(),
        recorder=recorder,
    )

    window = Window(controller)
    window.connect("destroy", Gtk.main_quit)
    window.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
