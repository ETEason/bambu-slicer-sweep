"""Per-feature filament usage from Bambu Studio G-code.

Bambu Studio marks each extrusion role with a ``; FEATURE: <name>`` comment.
Following the GUI (GCodeProcessor), a move counts as extrusion only when it
moves in X/Y/Z *and* advances E; pure E moves are retracts/unretracts/purges
and are not attributed to any feature.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

# Bambu Studio 2.x emits "Floating vertical shell" as its own role, but the GUI
# "Line type" legend has no such row: it is counted as "Internal solid infill"
# (verified against GUI numbers, see docs/verification.md).
GUI_FEATURE_ALIASES = {"Floating vertical shell": "Internal solid infill"}

_MOVE_RE = re.compile(r"^G[0-3](?:\s|$)")
_AXIS_RE = re.compile(r"([XYZEF])\s*(-?\d*\.?\d+)")
UNASSIGNED = "(none)"


@dataclass
class FeatureUsage:
    length_mm: dict[str, float] = field(default_factory=dict)

    @property
    def total_mm(self) -> float:
        return sum(self.length_mm.values())


def parse_feature_lengths(lines, aliases: dict[str, str] | None = None) -> FeatureUsage:
    """Sum extruded filament length (mm) per ``; FEATURE:`` type."""
    aliases = GUI_FEATURE_ALIASES if aliases is None else aliases
    usage = FeatureUsage()
    feature = UNASSIGNED
    relative_e = False
    e_pos = 0.0
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line[0] == ";":
            if line.startswith("; FEATURE:"):
                name = line[len("; FEATURE:"):].strip()
                feature = aliases.get(name, name)
            continue
        code = line.split(";", 1)[0].strip()
        if not code:
            continue
        if code.startswith("M83"):
            relative_e = True
        elif code.startswith("M82"):
            relative_e = False
        elif code.startswith("G92"):
            for axis, val in _AXIS_RE.findall(code):
                if axis == "E":
                    e_pos = float(val)
        elif _MOVE_RE.match(code):
            moved = False
            de = 0.0
            # G2/G3 arcs always move in XY; I/J are not captured by _AXIS_RE.
            if code[1] in "23":
                moved = True
            for axis, val in _AXIS_RE.findall(code[2:]):
                if axis == "E":
                    v = float(val)
                    de = v if relative_e else v - e_pos
                    e_pos = e_pos + v if relative_e else v
                elif axis in "XYZ":
                    moved = True
            if de > 0 and moved:
                usage.length_mm[feature] = usage.length_mm.get(feature, 0.0) + de
    return usage


def mm_to_grams(length_mm: float, diameter_mm: float, density_g_cm3: float) -> float:
    """Filament length -> weight, same formula as the GUI (cross-section x density)."""
    area_mm2 = math.pi * (diameter_mm / 2.0) ** 2
    return length_mm * area_mm2 * density_g_cm3 / 1000.0
