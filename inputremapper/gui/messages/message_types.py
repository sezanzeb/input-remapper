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

from enum import Enum
from typing import Dict, List

from inputremapper.groups import DeviceType

# useful type aliases
Capabilities = Dict[int, List]
Name = str
Key = str
DeviceTypes = List[DeviceType]


class MessageType(Enum):
    reset_gui = "reset_gui"
    terminate = "terminate"
    init = "init"

    uinputs = "uinputs"
    groups = "groups"
    group = "group"
    preset = "preset"
    mapping = "mapping"
    selected_event = "selected_event"
    combination_recorded = "combination_recorded"

    # only the reader_client should send those messages:
    recording_started = "recording_started"
    recording_finished = "recording_finished"

    combination_update = "combination_update"
    status_msg = "status_msg"
    injector_state = "injector_state"

    gui_focus_request = "gui_focus_request"
    user_confirm_request = "user_confirm_request"

    do_stack_switch = "do_stack_switch"

    # for unit tests:
    test1 = "test1"
    test2 = "test2"
