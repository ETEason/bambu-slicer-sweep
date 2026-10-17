"""Read statistics out of a sliced ``.gcode.3mf``."""
from __future__ import annotations

import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .gcode_stats import mm_to_grams, parse_feature_lengths

_HEADER_RE = {
    "total_time": re.compile(r"^; model printing time: (.*?); total estimated time: (.*)$"),
    "length_mm": re.compile(r"^; total filament length \[mm\] : ([\d.]+)"),
    "weight_g": re.compile(r"^; total filament weight \[g\] : ([\d.]+)"),
}
_CONFIG_RE = re.compile(r"^; (\w+) = (.*)$")


@dataclass
class SliceStats:
    total_g: float                 # slicer's own total (G-code header)
    total_length_mm: float
    print_time: str                # "4h 3m 59s" (model only)
    total_time: str                # "4h 10m 23s" (incl. prepare)
    total_time_s: float            # seconds, from result.json when available
    density_g_cm3: float
    diameter_mm: float
    feature_mm: dict[str, float]
    config: dict[str, str]         # selected applied settings, read back from G-code
    warnings: list[str] = field(default_factory=list)

    @property
    def feature_g(self) -> dict[str, float]:
        return {k: mm_to_grams(v, self.diameter_mm, self.density_g_cm3)
                for k, v in self.feature_mm.items()}


def hms_to_seconds(text: str) -> float:
    total = 0.0
    for num, unit in re.findall(r"([\d.]+)\s*([dhms])", text):
        total += float(num) * {"d": 86400, "h": 3600, "m": 60, "s": 1}[unit]
    return total


def _first_value(v):
    return float(v[0] if isinstance(v, list) else v)


def read_sliced_3mf(path: Path, plate: int, result_json: dict | None = None,
                    config_keys: tuple[str, ...] = ("sparse_infill_density", "sparse_infill_pattern")
                    ) -> SliceStats:
    warnings: list[str] = []
    with zipfile.ZipFile(path) as z:
        settings = json.loads(z.read("Metadata/project_settings.config"))
        gcode_bytes = z.read(f"Metadata/plate_{plate}.gcode")

    densities = settings.get("filament_density", [])
    diameters = settings.get("filament_diameter", [])
    if isinstance(densities, list) and len(densities) > 1:
        warnings.append("3MF 有多個耗材，各走線類型重量一律以第 1 個耗材的密度與線徑換算")
    density = _first_value(densities)
    diameter = _first_value(diameters)

    lines = io.TextIOWrapper(io.BytesIO(gcode_bytes), encoding="utf-8", errors="replace")
    header: dict[str, str] = {}
    config: dict[str, str] = {}
    body = []
    in_config = False
    for line in lines:
        if line.startswith("; CONFIG_BLOCK_START"):
            in_config = True
        elif line.startswith("; CONFIG_BLOCK_END"):
            in_config = False
        elif in_config:
            m = _CONFIG_RE.match(line.rstrip("\n"))
            if m and m.group(1) in config_keys:
                config[m.group(1)] = m.group(2)
        elif "total_time" not in header or "weight_g" not in header:
            for key, rx in _HEADER_RE.items():
                m = rx.match(line.rstrip("\n"))
                if m:
                    header[key] = m.groups() if key == "total_time" else m.group(1)
        body.append(line)

    usage = parse_feature_lengths(body)
    print_time, total_time = header.get("total_time", ("", ""))
    total_s = hms_to_seconds(total_time)
    if result_json:
        for p in result_json.get("sliced_plates", []):
            if p.get("id") == plate and "total_predication" in p:
                total_s = float(p["total_predication"])

    total_len = float(header.get("length_mm", usage.total_mm))
    if abs(usage.total_mm - total_len) > max(1.0, 1e-4 * total_len):
        warnings.append(f"各走線類型加總長度 {usage.total_mm:.2f} mm 與切片器總長 {total_len:.2f} mm 不一致")

    return SliceStats(
        total_g=float(header.get("weight_g", mm_to_grams(usage.total_mm, diameter, density))),
        total_length_mm=total_len,
        print_time=print_time,
        total_time=total_time,
        total_time_s=total_s,
        density_g_cm3=density,
        diameter_mm=diameter,
        feature_mm=usage.length_mm,
        config=config,
        warnings=warnings,
    )
