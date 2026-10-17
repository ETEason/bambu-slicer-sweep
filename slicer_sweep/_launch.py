"""Helper that runs bambu-studio.exe from its own hidden console (see bambu.py).

Usage: python -I _launch.py MARKER_FILE EXE [ARGS...]

Exits with the slicer's exit code. bambu-studio sometimes calls exit
successfully but Windows never finishes tearing the process down: one thread
stays stuck in the kernel, the exit code is already set, yet the process handle
is never signalled, so a plain wait blocks forever. When that happens this
helper writes MARKER_FILE and exits with the exit code the slicer reported.
"""
import _winapi
import subprocess
import sys
import time

STILL_ACTIVE = 259


def main() -> int:
    marker, args = sys.argv[1], sys.argv[2:]
    proc = subprocess.Popen(args)
    while True:
        rc = proc.poll()
        if rc is not None:
            break
        code = _winapi.GetExitCodeProcess(proc._handle)
        if code != STILL_ACTIVE:
            # Give a normal teardown a moment before calling it stuck.
            time.sleep(2)
            if proc.poll() is None:
                with open(marker, "w", encoding="utf-8") as f:
                    f.write(f"{proc.pid}\n")
                rc = code
                break
        time.sleep(0.1)
    return rc - 2**32 if rc >= 2**31 else rc


if __name__ == "__main__":
    sys.exit(main())
