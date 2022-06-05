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

from inputremapper.daemon import DaemonProxy
from inputremapper.groups import _Groups, _Group
from inputremapper.gui.data_bus import DataBus, UInputsData
from inputremapper.gui.reader import Reader
from inputremapper.injection.global_uinputs import GlobalUInputs


class Backend:
    """provides an interface to communicate with backend services"""

    def __init__(
        self,
        data_bus: DataBus,
        reader: Reader,
        daemon: DaemonProxy,
        uinputs: GlobalUInputs,
    ):

        self.daemon = daemon
        self.data_bus = data_bus
        self._reader = reader
        self._uinputs = uinputs

        self._uinputs.prepare_all()

    @property
    def groups(self) -> _Groups:
        return self._reader.groups

    @property
    def active_group(self) -> _Group:
        return self._reader.group

    def refresh_groups(self):
        self._reader.refresh_groups()

    def emit_groups(self):
        self._reader.emit_groups_changed()

    def set_active_group(self, group_key):
        group = self.groups.find(key=group_key)
        self._reader.set_group(group)

    def emit_uinputs(self):
        self.data_bus.send(
            UInputsData(
                {
                    name: uinput.capabilities()
                    for name, uinput in self._uinputs.devices.items()
                }
            )
        )
