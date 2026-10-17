"""Run the Bambu Studio CLI for one slice, with a hard timeout."""
from __future__ import annotations

import json
import subprocess
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_EXE = Path(r"C:\Program Files\Bambu Studio\bambu-studio.exe")
DEFAULT_TIMEOUT_S = 300
# Seconds to let the slicer exit on its own after it has written result.json.
EXIT_GRACE_S = 30
KILL_WAIT_S = 30
POLL_S = 0.25


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
    proc = subprocess.Popen(args, cwd=workdir, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    try:
        while (rc := proc.poll()) is None:
            now = time.monotonic()
            if now >= deadline:
                exited = _kill_tree(proc)
                raise SliceError(f"逾時 {timeout_s:g} 秒，" + ("已結束切片程序" if exited else
                                 f"且切片程序 PID {proc.pid} 沒有在 {KILL_WAIT_S} 秒內結束"))
            if result_seen_at is None:
                if _read_result(result_path) is not None:
                    result_seen_at = now
            elif now - result_seen_at >= EXIT_GRACE_S:
                exited = _kill_tree(proc)
                warnings.append(f"切片程序寫出結果後 {EXIT_GRACE_S} 秒仍未結束，已強制結束"
                                + ("" if exited else f"（PID {proc.pid} 未確認結束）"))
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
        hint = "（通常是命令列參數名稱或設定值無效）" if code == -2 and not result else ""
        raise SliceError(f"切片失敗：exit code {code}" + (f"，{msg}" if msg else "") + hint)
    if warnings and (not result or not _valid_zip(out)):
        raise SliceError(warnings[0] + "，且輸出不完整")
    if not out.exists():
        raise SliceError("切片程序結束但沒有產生 gcode.3mf")
    return SliceRun(out, result, elapsed, warnings)
