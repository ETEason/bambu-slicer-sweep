"""Sweep slicer settings over a 3MF and collect per-run statistics."""
from __future__ import annotations

import csv
import re
import shutil
import zipfile
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable

from .bambu import DEFAULT_EXE, DEFAULT_TIMEOUT_S, SliceError, slice_plate
from .i18n import t
from .sliced import read_sliced_3mf

# CSV column -> GUI "Line type" name (after GUI aliasing).
FEATURE_COLUMNS = {
    "sparse_infill_g": "Sparse infill",
    "bridge_g": "Bridge",
    "internal_solid_infill_g": "Internal solid infill",
    "top_surface_g": "Top surface",
    "bottom_surface_g": "Bottom surface",
    "inner_wall_g": "Inner wall",
    "outer_wall_g": "Outer wall",
    "gap_infill_g": "Gap infill",
    "custom_g": "Custom",
}
CSV_COLUMNS = (["pattern", "density_pct", "status", "total_g", "sparse_plus_bridge_g"]
               + list(FEATURE_COLUMNS) + ["other_g", "filament_m", "total_time", "total_time_s",
                                          "print_time", "slice_seconds", "gcode_3mf", "error"])


def parse_decimal(text: str) -> Decimal:
    try:
        d = Decimal(text.strip().rstrip("%"))
    except InvalidOperation:
        raise ValueError(t("not_number", text=text)) from None
    if not d.is_finite():
        raise ValueError(t("not_number", text=text))
    return d


def density_list(values: str | None = None, start: str | None = None, end: str | None = None,
                 step: str | None = None) -> list[Decimal]:
    """Densities from a comma list and/or an inclusive start..end range (Decimal: no float drift)."""
    out: list[Decimal] = []
    if values:
        out += [parse_decimal(v) for v in values.split(",") if v.strip()]
    if start is not None:
        s, e, st = parse_decimal(start), parse_decimal(end), parse_decimal(step)
        if st <= 0:
            raise ValueError(t("step_positive"))
        if e < s:
            raise ValueError(t("range_order"))
        n = 0
        while s + n * st <= e:
            out.append(s + n * st)
            n += 1
    for d in out:
        if not 0 <= d <= 100:
            raise ValueError(t("density_bounds", value=fmt_num(d)))
    # Keep first-seen order, drop duplicates (e.g. 10 and 10.0).
    seen, uniq = set(), []
    for d in out:
        if d not in seen:
            seen.add(d)
            uniq.append(d)
    return uniq


def fmt_num(d: Decimal) -> str:
    s = format(d, "f")
    return s.rstrip("0").rstrip(".") if "." in s else s


@dataclass
class RunResult:
    pattern: str
    density: Decimal
    status: str = "ok"
    error: str = ""
    total_g: float | None = None
    features_g: dict[str, float] = field(default_factory=dict)
    other_g: float | None = None
    filament_m: float | None = None
    total_time: str = ""
    total_time_s: float | None = None
    print_time: str = ""
    slice_seconds: float | None = None
    gcode_3mf: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    @property
    def sparse_plus_bridge_g(self) -> float | None:
        if not self.ok:
            return None
        return self.features_g.get("Sparse infill", 0.0) + self.features_g.get("Bridge", 0.0)

    def csv_row(self) -> dict[str, str]:
        def g(v):
            return "" if v is None else f"{v:.2f}"
        row = {
            "pattern": self.pattern, "density_pct": fmt_num(self.density), "status": self.status,
            "total_g": g(self.total_g), "sparse_plus_bridge_g": g(self.sparse_plus_bridge_g),
            "other_g": g(self.other_g),
            "filament_m": "" if self.filament_m is None else f"{self.filament_m:.3f}",
            "total_time": self.total_time,
            "total_time_s": "" if self.total_time_s is None else f"{self.total_time_s:.0f}",
            "print_time": self.print_time,
            "slice_seconds": "" if self.slice_seconds is None else f"{self.slice_seconds:.1f}",
            "gcode_3mf": self.gcode_3mf, "error": self.error,
        }
        for col, name in FEATURE_COLUMNS.items():
            row[col] = g(self.features_g.get(name, 0.0)) if self.ok else ""
        return row


def _model_cfg(model: Path) -> str:
    with zipfile.ZipFile(model) as z:
        if "Metadata/model_settings.config" not in z.namelist():
            return ""
        return z.read("Metadata/model_settings.config").decode("utf-8", "replace")


def model_info(model: Path) -> tuple[list[int], str]:
    """(plate ids, embedded sparse_infill_pattern)."""
    import json
    with zipfile.ZipFile(model) as z:
        settings = json.loads(z.read("Metadata/project_settings.config"))
    plates = [int(p) for p in re.findall(r'key="plater_id" value="(\d+)"', _model_cfg(model))] or [1]
    return plates, str(settings.get("sparse_infill_pattern", ""))


@dataclass
class ObjectOverride:
    object_name: str
    object_id: str
    part_name: str | None  # None when the setting is on the whole object
    key: str
    value: str


# Per-object settings that make a density/pattern sweep meaningless for that object:
# the command-line value does not apply to an object with its own value (see docs/design.md).
# skeleton/skin_infill_density are infill densities set alongside sparse_infill_density.
INFILL_KEYS = frozenset({"sparse_infill_density", "sparse_infill_pattern",
                         "skeleton_infill_density", "skin_infill_density"})
# <metadata> keys on objects/parts that describe the object itself rather than a setting.
_NOT_SETTINGS = frozenset({"name", "extruder", "matrix"})


def object_overrides(model: Path, plate: int, keys: set[str] | None = None) -> list[ObjectOverride]:
    """Settings that objects (or their parts) on ``plate`` set for themselves.

    Only ``keys`` when given, otherwise every per-object setting. Bambu Studio stores
    them as <metadata key=... value=...> on the <object> / <part> elements of
    Metadata/model_settings.config.
    """
    import xml.etree.ElementTree as ET
    text = _model_cfg(model)
    if not text:
        return []
    root = ET.fromstring(text)

    def meta(el, key):
        for m in el.findall("metadata"):
            if m.get("key") == key:
                return m.get("value")
        return None

    on_plate: set[str] | None = None
    for p in root.findall("plate"):
        if meta(p, "plater_id") == str(plate):
            on_plate = {meta(mi, "object_id") for mi in p.findall("model_instance")}
    found = []
    for obj in root.findall("object"):
        oid = obj.get("id", "")
        if on_plate is not None and oid not in on_plate:
            continue
        name = meta(obj, "name") or oid
        for el, part in [(obj, None)] + [(p, meta(p, "name") or p.get("id", "")) for p in obj.findall("part")]:
            for m in el.findall("metadata"):
                key = m.get("key")
                if not key or key in _NOT_SETTINGS or key.startswith("source_"):
                    continue
                if keys is None or key in keys:
                    found.append(ObjectOverride(name, oid, part, m.get("key"), m.get("value", "")))
    return found


def run_sweep(model: Path, plate: int, densities: list[Decimal], patterns: list[str] | None,
              out_dir: Path, keep: bool = False, extra: dict[str, str] | None = None,
              exe: Path = DEFAULT_EXE, timeout_s: float = DEFAULT_TIMEOUT_S,
              progress: Callable[[int, int, RunResult], None] | None = None) -> list[RunResult]:
    """Slice every (pattern, density) combination, one process at a time."""
    out_dir.mkdir(parents=True, exist_ok=True)
    work = out_dir / "_work"
    work.mkdir(exist_ok=True)
    # Slice a copy so the original 3MF is never handed to the slicer.
    model_copy = work / "model.3mf"
    shutil.copyfile(model, model_copy)

    _, embedded_pattern = model_info(model)
    combos = [(p, d) for p in (patterns or [None]) for d in densities]
    results: list[RunResult] = []
    try:
        for i, (pattern, density) in enumerate(combos, 1):
            overrides = dict(extra or {})
            overrides["sparse_infill_density"] = fmt_num(density) + "%"
            if pattern:
                overrides["sparse_infill_pattern"] = pattern
            label = f"{pattern or embedded_pattern}_{fmt_num(density)}"
            r = RunResult(pattern=pattern or embedded_pattern, density=density)
            run_dir = work / label
            try:
                run = slice_plate(model_copy, plate, overrides, run_dir, exe=exe, timeout_s=timeout_s)
                r.slice_seconds = run.elapsed_s
                s = read_sliced_3mf(run.output_3mf, plate, run.result_json)
                applied_d = s.config.get("sparse_infill_density", "")
                applied_p = s.config.get("sparse_infill_pattern", "")
                if parse_decimal(applied_d) != density or (pattern and applied_p != pattern):
                    raise SliceError(t("not_applied", pattern=applied_p, density=applied_d))
                r.pattern = applied_p or r.pattern
                r.total_g = s.total_g
                fg = s.feature_g
                known = set(FEATURE_COLUMNS.values())
                r.features_g = {k: v for k, v in fg.items() if k in known}
                r.other_g = sum(v for k, v in fg.items() if k not in known)
                r.filament_m = s.total_length_mm / 1000
                r.total_time, r.total_time_s, r.print_time = s.total_time, s.total_time_s, s.print_time
                r.warnings = run.warnings + s.warnings
                if keep:
                    dest = out_dir / f"{model.stem}_plate{plate}_{label}.gcode.3mf"
                    try:
                        shutil.move(run.output_3mf, dest)
                    except OSError:
                        # Still held open by a slicer stuck in teardown: copy instead.
                        shutil.copyfile(run.output_3mf, dest)
                    r.gcode_3mf = dest.name
            except (SliceError, OSError, KeyError, ValueError, zipfile.BadZipFile) as e:
                r.status = "error"
                r.error = str(e)
            finally:
                shutil.rmtree(run_dir, ignore_errors=True)
            results.append(r)
            if progress:
                progress(i, len(combos), r)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return results


def write_csv(results: list[RunResult], path: Path) -> None:
    # utf-8-sig so Excel opens it with the right encoding.
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        w.writeheader()
        for r in results:
            w.writerow(r.csv_row())


def best(results: list[RunResult], key: str) -> list[RunResult]:
    """All successful runs tied for the minimum of ``key`` (rounded like the CSV)."""
    ok = [r for r in results if r.ok]
    if not ok:
        return []
    digits = 0 if key == "total_time_s" else 2
    low = min(round(getattr(r, key), digits) for r in ok)
    return [r for r in ok if round(getattr(r, key), digits) == low]
