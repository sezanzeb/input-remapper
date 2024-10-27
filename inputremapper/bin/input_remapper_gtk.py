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

"""Starts the user interface."""

from __future__ import annotations

import atexit
import sys
from argparse import ArgumentParser
from typing import Tuple

import gi

from inputremapper.bin.process_utils import ProcessUtils

gi.require_version("Gtk", "3.0")
gi.require_version("GLib", "2.0")
gi.require_version("GtkSource", "4")
from gi.repository import Gtk

# https://github.com/Nuitka/Nuitka/issues/607#issuecomment-650217096
Gtk.init()

from inputremapper.gui.gettext import _, LOCALE_DIR
from inputremapper.gui.reader_service import ReaderService
from inputremapper.daemon import DaemonProxy, Daemon
from inputremapper.logging.logger import logger
from inputremapper.gui.messages.message_broker import MessageBroker, MessageType
from inputremapper.configs.keyboard_layout import keyboard_layout
from inputremapper.gui.data_manager import DataManager
from inputremapper.gui.user_interface import UserInterface
from inputremapper.gui.controller import Controller
from inputremapper.injection.global_uinputs import GlobalUInputs, FrontendUInput
from inputremapper.groups import _Groups
from inputremapper.gui.reader_client import ReaderClient
from inputremapper.configs.global_config import GlobalConfig
from inputremapper.configs.migrations import Migrations


def stop(daemon, controller):
    if isinstance(daemon, Daemon):
        # have fun debugging completely unrelated tests if you remove this
        daemon.stop_all()

    controller.close()


def main() -> Tuple[
    UserInterface,
    Controller,
    DataManager,
    MessageBroker,
    DaemonProxy,
    GlobalConfig,
]:
    parser = ArgumentParser()
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        dest="debug",
        help=_("Displays additional debug information"),
        default=False,
    )
    parser.add_argument(
        "--without-reader-service",
        action="store_true",
        dest="without_reader_service",
        help=_(
            "Don't attempt to start input-remapper-reader-service automatically via "
            "pkexec. You need to start it with elevated privileges yourself "
            "afterwards, and restart it if it times out."
        ),
        default=False,
    )

    options = parser.parse_args(sys.argv[1:])
    logger.update_verbosity(options.debug)
    logger.log_info("input-remapper-gtk")
    logger.debug("Using locale directory: {}".format(LOCALE_DIR))

    global_uinputs = GlobalUInputs(FrontendUInput)

    migrations = Migrations(global_uinputs)
    migrations.migrate()

    message_broker = MessageBroker()

    global_config = GlobalConfig()

    # Create the ReaderClient before we start the reader-service, otherwise the
    # privileged service creates and owns those pipes, and then they cannot be accessed
    # by the user.
    reader_client = ReaderClient(message_broker, _Groups())

    if ProcessUtils.count_python_processes("input-remapper-gtk") >= 2:
        logger.warning(
            "Another input-remapper GUI is already running. "
            "This can cause problems while recording keys"
        )

    if not options.without_reader_service:
        try:
            ReaderService.pkexec_reader_service()
        except Exception as e:
            logger.error(e)
            sys.exit(11)

    daemon = Daemon.connect()

    data_manager = DataManager(
        message_broker,
        global_config,
        reader_client,
        daemon,
        global_uinputs,
        keyboard_layout,
    )
    controller = Controller(message_broker, data_manager)
    user_interface = UserInterface(message_broker, controller)
    controller.set_gui(user_interface)

    message_broker.signal(MessageType.init)

    atexit.register(lambda: stop(daemon, controller))

    Gtk.main()

    # For tests:
    return (
        user_interface,
        controller,
        data_manager,
        message_broker,
        daemon,
        global_config,
    )
