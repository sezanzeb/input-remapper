#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@sezanzeb.de>
#
# This file is part of key-mapper.
#
# key-mapper is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# key-mapper is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with key-mapper.  If not, see <https://www.gnu.org/licenses/>.


"""Exceptions specific to keymapper"""


class Error(Exception):
    """Base class for exceptions in keymapper

    we can catch all keymapper exceptions with this
    """

    pass


class UinputNotAvailable(Error):
    def __init__(self, name):
        super().__init__(f"{name} is not defined or unplugged")


class EventNotHandled(Error):
    def __init__(self, event):
        super().__init__(f"the event {event} can not be handled")
