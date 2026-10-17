"""Run the Bambu Studio CLI for one slice, with a hard timeout."""
from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_EXE = Path(r"C:\Program Files\Bambu Studio\bambu-studio.exe")
DEFAULT_TIMEOUT_S = 300


class SliceError(RuntimeError):
    pass


@dataclass
class SliceRun:
    output_3mf: Path
    result_json: dict
    elapsed_s: float


def _kill_tree(pid: int) -> None:
    # taskkill /T also ends any child process the slicer may have spawned.
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _pid_alive(pid: int) -> bool:
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
                         capture_output=True, text=True).stdout
    return f'"{pid}"' in out


def slice_plate(model_3mf: Path, plate: int, overrides: dict[str, str], workdir: Path,
                exe: Path = DEFAULT_EXE, timeout_s: float = DEFAULT_TIMEOUT_S) -> SliceRun:
    """Slice one plate of ``model_3mf`` into ``workdir/out.gcode.3mf``.

    ``overrides`` maps config keys (``sparse_infill_density``) to values; they are
    passed as ``--sparse-infill-density VALUE``. Only the hyphenated spelling is
    accepted by Bambu Studio 2.7 (the underscore form fails with exit code -2).

    The slicer runs with ``workdir`` as its current directory because it writes
    ``result.json`` there.
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

    start = time.monotonic()
    proc = subprocess.Popen(args, cwd=workdir, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    try:
        rc = proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        _kill_tree(proc.pid)
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            pass
        if _pid_alive(proc.pid):
            raise SliceError(f"逾時 {timeout_s:g} 秒，且無法結束程序 PID {proc.pid}")
        raise SliceError(f"逾時 {timeout_s:g} 秒，已結束切片程序")
    finally:
        if proc.poll() is None:  # e.g. KeyboardInterrupt while waiting
            _kill_tree(proc.pid)
            proc.wait()
    elapsed = time.monotonic() - start

    result = {}
    if result_path.exists():
        result = json.loads(result_path.read_text(encoding="utf-8"))
    if rc != 0 or result.get("return_code", 0) != 0:
        msg = result.get("error_string", "")
        code = rc if rc < 2**31 else rc - 2**32
        hint = "（通常是命令列參數名稱或設定值無效）" if code == -2 and not result else ""
        raise SliceError(f"切片失敗：exit code {code}" + (f"，{msg}" if msg else "") + hint)
    if not out.exists():
        raise SliceError("切片程序結束但沒有產生 gcode.3mf")
    return SliceRun(out, result, elapsed)
