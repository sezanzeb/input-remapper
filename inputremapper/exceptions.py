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


"""Exceptions specific to inputremapper"""

from typing import Optional


class Error(Exception):
    """Base class for exceptions in inputremapper.

    We can catch all inputremapper exceptions with this.
    """


class UinputNotAvailable(Error):
    """If an expected UInput is not found (anymore)."""

    def __init__(self, name: str):
        super().__init__(f"{name} is not defined or unplugged")


class EventNotHandled(Error):
    """For example mapping to BTN_LEFT on a keyboard target."""

    def __init__(self, event):
        super().__init__(f"Event {event} can not be handled by the configured target")


class MacroParsingError(Error):
    """Macro syntax errors."""

    def __init__(self, symbol: Optional[str] = None, msg="Error while parsing a macro"):
        self.symbol = symbol
        super().__init__(msg)


class MappingParsingError(Error):
    """Anything that goes wrong during the creation of handlers from the mapping."""

    def __init__(self, msg: str, *, mapping=None, mapping_handler=None):
        self.mapping_handler = mapping_handler
        self.mapping = mapping
        super().__init__(msg)


class InputEventCreationError(Error):
    """An input-event failed to be created due to broken factory/constructor calls."""

    def __init__(self, msg: str):
        super().__init__(msg)


class DataManagementError(Error):
    """Any error that happens in the DataManager."""

    def __init__(self, msg: str):
        super().__init__(msg)
