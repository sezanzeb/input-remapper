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

import psutil


class ProcessUtils:
    @staticmethod
    def count_python_processes(name: str) -> int:
        # This is somewhat complicated, because there might also be a "sudo <name>"
        # process.
        count = 0
        pids = psutil.pids()
        for pid in pids:
            try:
                process = psutil.Process(pid)
                cmdline = process.cmdline()
                if len(cmdline) >= 2 and "python" in cmdline[0] and name in cmdline[1]:
                    count += 1
            except Exception:
                pass

        return count
