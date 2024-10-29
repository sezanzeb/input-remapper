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

"""Starts injecting keycodes based on the configuration."""

import sys
from argparse import ArgumentParser

from inputremapper.configs.global_config import GlobalConfig
from inputremapper.injection.global_uinputs import GlobalUInputs, UInput
from inputremapper.injection.mapping_handlers.mapping_parser import MappingParser
from inputremapper.logging.logger import logger


class InputRemapperServiceBin:
    @staticmethod
    def main() -> None:
        parser = ArgumentParser()
        parser.add_argument(
            "-d",
            "--debug",
            action="store_true",
            dest="debug",
            help="Displays additional debug information",
            default=False,
        )
        parser.add_argument(
            "--hide-info",
            action="store_true",
            dest="hide_info",
            help="Don't display version information",
            default=False,
        )

        options = parser.parse_args(sys.argv[1:])

        logger.update_verbosity(options.debug)

        # import input-remapper stuff after setting the log verbosity
        from inputremapper.daemon import Daemon

        if not options.hide_info:
            logger.log_info("input-remapper-service")

        global_config = GlobalConfig()
        global_uinputs = GlobalUInputs(UInput)
        mapping_parser = MappingParser(global_uinputs)

        daemon = Daemon(global_config, global_uinputs, mapping_parser)
        daemon.publish()
        daemon.run()
