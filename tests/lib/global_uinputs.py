#!/usr/bin/python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2023 sezanzeb <proxima@sezanzeb.de>
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

import sys
from unittest.mock import patch

from inputremapper.injection.global_uinputs import global_uinputs


def reset_global_uinputs_for_service():
    with patch.object(sys, "argv", ["input-remapper-service"]):
        # patch argv for global_uinputs to think it is a service
        global_uinputs.reset()


def reset_global_uinputs_for_gui():
    with patch.object(sys, "argv", ["input-remapper-gtk"]):
        global_uinputs.reset()
