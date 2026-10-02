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

import psutil


class ProcessUtils:
    @staticmethod
    def _find_matching_processes(
        name: str,
        arguments: list[str] | None = None,
    ) -> list[psutil.Process]:
        # This is somewhat complicated, because there might also be a "sudo <name>"
        # process.
        matches = []
        for pid in psutil.pids():
            try:
                process = psutil.Process(pid)
                cmdline = process.cmdline()
                if len(cmdline) < 2:
                    continue

                if "python" not in cmdline[0]:
                    continue

                if name not in cmdline[1]:
                    continue

                if arguments and not all(
                    argument in cmdline[2:] for argument in arguments
                ):
                    continue

                matches.append(process)
            except Exception:  # noqa: S110
                pass
        return matches

    @staticmethod
    def count_python_processes(name: str, arguments: list[str] | None = None) -> int:
        return len(ProcessUtils._find_matching_processes(name, arguments))

    @staticmethod
    def terminate_python_processes(
        name: str, arguments: list[str] | None = None
    ) -> int:
        """Terminate all matching processes. Returns how many were signaled."""
        count = 0
        for process in ProcessUtils._find_matching_processes(name, arguments):
            try:
                process.terminate()
                count += 1
            except Exception:  # noqa: S110
                pass
        return count
