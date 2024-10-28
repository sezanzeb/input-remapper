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
