# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2025 sezanzeb <b8x45ygc9@mozmail.com>
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

"""Control the dbus service from the command line."""

import argparse
import logging
import os
import subprocess
import sys
from enum import Enum
from typing import Optional

import gi

from inputremapper.groups import Groups

gi.require_version("GLib", "2.0")
from gi.repository import GLib

from inputremapper.configs.global_config import GlobalConfig
from inputremapper.configs.migrations import Migrations
from inputremapper.injection.global_uinputs import GlobalUInputs, FrontendUInput
from inputremapper.logging.logger import logger
from inputremapper.user import UserUtils


class Commands(Enum):
    AUTOLOAD = "autoload"
    START = "start"
    STOP = "stop"
    STOP_ALL = "stop-all"
    HELLO = "hello"
    QUIT = "quit"


class Internals(Enum):
    # internal stuff that the gui uses
    START_DAEMON = "start-daemon"
    START_READER_SERVICE = "start-reader-service"


class Options:
    command: str
    config_dir: str
    preset: str
    device: str
    list_devices: bool
    key_names: str
    debug: bool
    version: str


class InputRemapperControlBin:
    def __init__(
        self,
        global_config: GlobalConfig,
        migrations: Migrations,
        groups: Groups,
    ):
        self.groups = groups
        self.global_config = global_config
        self.migrations = migrations

    @staticmethod
    def main(options: Options) -> None:
        global_config = GlobalConfig()
        global_uinputs = GlobalUInputs(FrontendUInput)
        migrations = Migrations(global_uinputs)
        groups = Groups(global_config)
        input_remapper_control = InputRemapperControlBin(
            global_config,
            migrations,
            groups,
        )

        if options.debug:
            logger.update_verbosity(True)

        if options.version:
            logger.log_info()
            return

        logger.debug('Call for "%s"', sys.argv)

        boot_finished_ = input_remapper_control.boot_finished()
        is_root = UserUtils.user == "root"
        is_autoload = options.command == Commands.AUTOLOAD
        config_dir_set = options.config_dir is not None
        if is_autoload and not boot_finished_ and is_root and not config_dir_set:
            # this is probably happening during boot time and got
            # triggered by udev. There is no need to try to inject anything if the
            # service doesn't know where to look for a config file. This avoids a lot
            # of confusing service logs. And also avoids potential for problems when
            # input-remapper-control stresses about evdev, dbus and multiprocessing already
            # while the system hasn't even booted completely.
            logger.warning("Skipping autoload command without a logged in user")
            return

        if options.command is not None:
            if options.command in [command.value for command in Internals]:
                input_remapper_control.internals(options.command, options.debug)
            elif options.command in [command.value for command in Commands]:
                from inputremapper.daemon import Daemon

                daemon = Daemon.connect(fallback=False)

                input_remapper_control.set_daemon(daemon)

                input_remapper_control.communicate(
                    options.command,
                    options.device,
                    options.config_dir,
                    options.preset,
                )
            else:
                logger.error('Unknown command "%s"', options.command)
        else:
            if options.list_devices:
                input_remapper_control.list_devices()

            if options.key_names:
                input_remapper_control.list_key_names()

        if options.command:
            logger.info("Done")

    def list_devices(self):
        logger.setLevel(logging.ERROR)

        for group in self.groups:
            print(group.key)

    def list_key_names(self):
        from inputremapper.configs.keyboard_layout import keyboard_layout

        print("\n".join(keyboard_layout.list_names()))

    def communicate(
        self,
        command: str,
        device: str,
        config_dir: Optional[str],
        preset: str,
    ) -> None:
        """Commands that require a running daemon."""
        if self.daemon is None:
            # probably broken tests
            logger.error("Daemon missing")
            sys.exit(5)

        if config_dir is not None:
            self._load_config(config_dir)

        self.ensure_migrated()

        if command == Commands.AUTOLOAD.value:
            self._autoload(device)

        if command == Commands.START.value:
            self._start(device, preset)

        if command == Commands.STOP.value:
            self._stop(device)

        if command == Commands.STOP_ALL.value:
            self.daemon.stop_all()

        if command == Commands.HELLO.value:
            self._hello()

        if command == Commands.QUIT.value:
            self._quit()

    def _hello(self):
        response = self.daemon.hello("hello")
        logger.info('Daemon answered with "%s"', response)

    def _load_config(self, config_dir: str) -> None:
        path = os.path.abspath(
            os.path.expanduser(os.path.join(config_dir, "config.json"))
        )
        if not os.path.exists(path):
            logger.error('"%s" does not exist', path)
            sys.exit(6)

        logger.info('Using config from "%s" instead', path)
        self.global_config.load_config(path)

    def ensure_migrated(self) -> None:
        # import stuff late to make sure the correct log level is applied
        # before anything is logged
        # TODO since imports shouldn't run any code, this is fixed by moving towards DI
        from inputremapper.user import UserUtils

        if UserUtils.user != "root":
            # Might be triggered by udev, so skip the root user.
            # This will also refresh the config of the daemon if the user changed
            # it in the meantime.
            # config_dir is either the cli arg or the default path in home
            config_dir = os.path.dirname(self.global_config.path)
            self.daemon.set_config_dir(config_dir)
            self.migrations.migrate()

    def _stop(self, device: str) -> None:
        group = self._require_group(device)
        self.daemon.stop_injecting(group.key)

    def _quit(self) -> None:
        try:
            self.daemon.quit()
        except GLib.GError as error:
            if "NoReply" in str(error):
                # The daemon is expected to terminate, so there won't be a reply.
                return

            raise

    def _start(self, device: str, preset: str) -> None:
        group = self._require_group(device)

        logger.info(
            'Starting injection: "%s", "%s"',
            device,
            preset,
        )

        self.daemon.start_injecting(group.key, preset)

    def _require_group(self, device: str):
        if device is None:
            logger.error("--device missing")
            sys.exit(3)

        if device.startswith("/dev"):
            group = self.groups.find(path=device)
        else:
            group = self.groups.find(key=device)

        if group is None:
            logger.error(
                'Device "%s" is unknown or not an appropriate input device',
                device,
            )
            sys.exit(4)

        return group

    def _autoload(self, device: str) -> None:
        # if device was specified, autoload for that one. if None autoload
        # for all devices.
        if device is None:
            logger.info("Autoloading all")
            # timeout is not documented, for more info see
            # https://github.com/LEW21/pydbus/blob/master/pydbus/proxy_method.py
            self.daemon.autoload(timeout=10)
        else:
            group = self._require_group(device)
            logger.info("Asking daemon to autoload for %s", device)
            self.daemon.autoload_single(group.key, timeout=2)

    def internals(self, command: str, debug: True) -> None:
        """Methods that are needed to get the gui to work and that require root.

        input-remapper-control should be started with sudo or pkexec for this.
        """
        debug = " -d" if debug else ""

        if command == Internals.START_READER_SERVICE.value:
            cmd = f"input-remapper-reader-service{debug}"
        elif command == Internals.START_DAEMON.value:
            cmd = f"input-remapper-service --hide-info{debug}"
        else:
            return

        # daemonize
        cmd = f"{cmd} &"
        logger.debug(f"Running `{cmd}`")
        os.system(cmd)

    def _num_logged_in_users(self) -> int:
        """Check how many users are logged in."""
        who = subprocess.run(["who"], stdout=subprocess.PIPE).stdout.decode()
        return len([user for user in who.split("\n") if user.strip() != ""])

    def _is_systemd_finished(self) -> bool:
        """Check if systemd finished booting."""
        try:
            systemd_analyze = subprocess.run(
                ["systemd-analyze"], stdout=subprocess.PIPE
            )
        except FileNotFoundError:
            # probably not systemd, lets assume true to not block input-remapper for good
            # on certain installations
            return True

        if "finished" in systemd_analyze.stdout.decode():
            # it writes into stderr otherwise or something
            return True

        return False

    def boot_finished(self) -> bool:
        """Check if booting is completed."""
        # Get as much information as needed to really safely determine if booting up is
        # complete.
        # - `who` returns an empty list on some system for security purposes
        # - something might be broken and might make systemd_analyze fail:
        #       Bootup is not yet finished
        #       (org.freedesktop.systemd1.Manager.FinishTimestampMonotonic=0).
        #       Please try again later.
        #       Hint: Use 'systemctl list-jobs' to see active jobs
        if self._is_systemd_finished():
            logger.debug("System is booted")
            return True

        if self._num_logged_in_users() > 0:
            logger.debug("User(s) logged in")
            return True

        return False

    def set_daemon(self, daemon):
        # TODO DI?
        self.daemon = daemon

    @staticmethod
    def parse_args() -> Options:
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--command",
            action="store",
            dest="command",
            help=(
                "Communicate with the daemon. Available commands are "
                f"{', '.join([command.value for command in Commands])}"
            ),
            default=None,
            metavar="NAME",
        )
        parser.add_argument(
            "--config-dir",
            action="store",
            dest="config_dir",
            help=(
                "path to the config directory containing config.json, "
                "xmodmap.json and the presets folder. "
                "defaults to ~/.config/input-remapper/"
            ),
            default=None,
            metavar="PATH",
        )
        parser.add_argument(
            "--preset",
            action="store",
            dest="preset",
            help="The filename of the preset without the .json extension.",
            default=None,
            metavar="NAME",
        )
        parser.add_argument(
            "--device",
            action="store",
            dest="device",
            help="One of the device keys from --list-devices",
            default=None,
            metavar="NAME",
        )
        parser.add_argument(
            "--list-devices",
            action="store_true",
            dest="list_devices",
            help="List available device keys and exit",
            default=False,
        )
        parser.add_argument(
            "--symbol-names",
            action="store_true",
            dest="key_names",
            help="Print all available names for the preset",
            default=False,
        )
        parser.add_argument(
            "-d",
            "--debug",
            action="store_true",
            dest="debug",
            help="Displays additional debug information",
            default=False,
        )
        parser.add_argument(
            "-v",
            "--version",
            action="store_true",
            dest="version",
            help="Print the version and exit",
            default=False,
        )

        return parser.parse_args(sys.argv[1:])  # type: ignore
