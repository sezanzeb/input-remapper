# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2026 sezanzeb <4t1pzast9@mozmail.com>
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

from typing import List, Optional
import psutil


class ProcessUtils:
    @staticmethod
    def _find_matching_processes(
        name: str, extra_match: Optional[str] = None
    ) -> List[psutil.Process]:
        # This is somewhat complicated, because there might also be a "sudo <name>"
        # process.
        matches = []
        for pid in psutil.pids():
            try:
                process = psutil.Process(pid)
                cmdline = process.cmdline()
                if len(cmdline) >= 2 and "python" in cmdline[0] and name in cmdline[1]:
                    if extra_match is None or extra_match in cmdline:
                        matches.append(process)
            except Exception:  # noqa: S110
                pass
        return matches

    @staticmethod
    def count_python_processes(name: str, extra_match: Optional[str] = None) -> int:
        return len(ProcessUtils._find_matching_processes(name, extra_match))

    @staticmethod
    def terminate_python_processes(name: str, extra_match: Optional[str] = None) -> int:
        """Terminate all matching processes. Returns how many were signaled."""
        count = 0
        for process in ProcessUtils._find_matching_processes(name, extra_match):
            try:
                process.terminate()
                count += 1
            except Exception:  # noqa: S110
                pass
        return count
