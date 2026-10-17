"""Run the Bambu Studio CLI for one slice, with a hard timeout."""
from __future__ import annotations

import json
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .i18n import t

DEFAULT_EXE = Path(r"C:\Program Files\Bambu Studio\bambu-studio.exe")
DEFAULT_TIMEOUT_S = 300
# Seconds to let the slicer exit on its own after it has written result.json.
EXIT_GRACE_S = 30
KILL_WAIT_S = 30
POLL_S = 0.25

# bambu-studio.exe attaches to its parent's console and writes its log there, so
# stdout/stderr redirection and console creation flags do not silence it. It is
# therefore started by this helper, which owns a hidden console of its own and
# passes the slicer's exit code through.
_HELPER = ("import subprocess, sys; rc = subprocess.call(sys.argv[1:]); "
           "sys.exit(rc - 2**32 if rc >= 2**31 else rc)")


class SliceError(RuntimeError):
    pass


@dataclass
class SliceRun:
    output_3mf: Path
    result_json: dict
    elapsed_s: float
    warnings: list[str] = field(default_factory=list)


def _kill_tree(proc: subprocess.Popen) -> bool:
    """Kill the process and its children; True once the process has exited."""
    # taskkill /T also ends any child process the slicer may have spawned.
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], timeout=KILL_WAIT_S,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        pass
    if proc.poll() is None:
        try:
            proc.kill()
        except OSError:
            pass
    try:
        proc.wait(timeout=KILL_WAIT_S)
    except subprocess.TimeoutExpired:
        return False
    return True


def _read_result(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None  # missing, or still being written


def _valid_zip(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as z:
            return z.testzip() is None
    except (OSError, zipfile.BadZipFile):
        return False


def slice_plate(model_3mf: Path, plate: int, overrides: dict[str, str], workdir: Path,
                exe: Path = DEFAULT_EXE, timeout_s: float = DEFAULT_TIMEOUT_S) -> SliceRun:
    """Slice one plate of ``model_3mf`` into ``workdir/out.gcode.3mf``.

    ``overrides`` maps config keys (``sparse_infill_density``) to values; they are
    passed as ``--sparse-infill-density VALUE``. Only the hyphenated spelling is
    accepted by Bambu Studio 2.7 (the underscore form fails with exit code -2).

    The slicer runs with ``workdir`` as its current directory because it writes
    ``result.json`` there. It is never waited on without a deadline: after
    ``timeout_s`` the process tree is killed. If the slicer has already written
    its results but does not exit within ``EXIT_GRACE_S`` seconds, it is killed
    and the results are used when the output archive is complete.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    out = workdir / "out.gcode.3mf"
    result_path = workdir / "result.json"
    for stale in (out, result_path):
        stale.unlink(missing_ok=True)

    args = [str(exe)]
    for key, value in overrides.items():
        args += ["--" + key.replace("_", "-"), str(value)]
    args += ["--slice", str(plate), "--export-3mf", out.name, str(model_3mf.resolve())]

    warnings: list[str] = []
    start = time.monotonic()
    deadline = start + timeout_s
    result_seen_at = None
    hidden = subprocess.STARTUPINFO()
    hidden.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    hidden.wShowWindow = 0  # SW_HIDE
    proc = subprocess.Popen([sys.executable, "-I", "-c", _HELPER, *args], cwd=workdir,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, startupinfo=hidden,
                            creationflags=subprocess.CREATE_NEW_CONSOLE)
    try:
        while (rc := proc.poll()) is None:
            now = time.monotonic()
            if now >= deadline:
                exited = _kill_tree(proc)
                raise SliceError(t("timeout_killed", timeout=timeout_s) if exited else
                                 t("timeout_stuck", timeout=timeout_s, pid=proc.pid, wait=KILL_WAIT_S))
            if result_seen_at is None:
                if _read_result(result_path) is not None:
                    result_seen_at = now
            elif now - result_seen_at >= EXIT_GRACE_S:
                exited = _kill_tree(proc)
                warnings.append(t("exit_hang", grace=EXIT_GRACE_S)
                                + ("" if exited else t("exit_hang_unconfirmed", pid=proc.pid)))
                rc = 0  # judged by result.json and the archive below
                break
            time.sleep(POLL_S)
    except BaseException:
        if proc.poll() is None:  # e.g. KeyboardInterrupt while waiting
            _kill_tree(proc)
        raise
    elapsed = time.monotonic() - start

    result = _read_result(result_path) or {}
    if rc != 0 or result.get("return_code", 0) != 0:
        msg = result.get("error_string", "")
        code = rc if rc < 2**31 else rc - 2**32
        hint = t("hint_bad_option") if code == -2 and not result else ""
        raise SliceError(t("slice_failed", code=code) + (t("slice_failed_msg", msg=msg) if msg else "")
                         + hint)
    if warnings and (not result or not _valid_zip(out)):
        raise SliceError(warnings[0] + t("output_incomplete"))
    if not out.exists():
        raise SliceError(t("no_output"))
    return SliceRun(out, result, elapsed, warnings)
