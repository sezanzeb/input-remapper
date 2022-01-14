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


class Error(Exception):
    """Base class for exceptions in inputremapper

    we can catch all inputremapper exceptions with this
    """

    pass


class UinputNotAvailable(Error):
    def __init__(self, name):
        super().__init__(f"{name} is not defined or unplugged")


class EventNotHandled(Error):
    def __init__(self, event):
        super().__init__(f"the event {event} can not be handled")
