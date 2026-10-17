"""Compare CLI slicing results with numbers measured in the Bambu Studio GUI.

Usage: python tools/verify_gui.py MODEL.3mf [--plate 1] [--out docs/verification.md]
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from slicer_sweep.bambu import slice_plate  # noqa: E402
from slicer_sweep.sliced import read_sliced_3mf  # noqa: E402

# GUI "Line type" statistics (g) and total time; filament 1.27 g/cm3, 1.75 mm.
GUI = {
    3: dict(sparse=3.85, bridge=54.19, solid=32.46, total=121.36, time="4h43m"),
    7: dict(sparse=9.35, bridge=35.03, solid=31.39, total=106.65, time="4h17m"),
    8: dict(sparse=10.86, bridge=32.34, solid=31.10, total=105.17, time="4h15m"),
    9: dict(sparse=11.93, bridge=39.44, solid=31.03, total=113.27, time="4h31m"),
    10: dict(sparse=13.56, bridge=29.85, solid=32.46, total=106.74, time="4h16m"),
    11: dict(sparse=15.29, bridge=25.06, solid=31.24, total=102.45, time="4h10m"),
    12: dict(sparse=16.20, bridge=32.45, solid=31.20, total=110.71, time="4h26m"),
    13: dict(sparse=17.81, bridge=25.64, solid=31.00, total=105.31, time="4h16m"),
    14: dict(sparse=18.92, bridge=25.27, solid=31.10, total=106.15, time="4h17m"),
}
GUI_TOTAL_ONLY = {5: 114.67, 15: 106.75, 20: 110.09, 25: 116.80}
GUI_CONSTANT = {"Inner wall": 4.41, "Outer wall": 4.54, "Top surface": 12.72,
                "Bottom surface": 9.10, "Gap infill": 0.01, "Custom": 0.09}
REQUIRED = (3, 11, 13)
TOLERANCE = 0.01


def minutes(t: str) -> float:
    h, m = t.rstrip("m").split("h")
    return int(h) * 60 + int(m)


def pct(cli: float, gui: float) -> float:
    return (cli - gui) / gui * 100 if gui else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("model", type=Path)
    ap.add_argument("--plate", type=int, default=1)
    ap.add_argument("--out", type=Path, default=Path("docs/verification.md"))
    ap.add_argument("--work", type=Path, default=Path("work/verify"))
    a = ap.parse_args()

    a.work.mkdir(parents=True, exist_ok=True)
    model = a.work / "model.3mf"
    shutil.copyfile(a.model, model)  # never hand the original to the slicer

    rows, const_rows, failures = [], [], []
    for d in sorted(set(GUI) | set(GUI_TOTAL_ONLY)):
        run = slice_plate(model, a.plate, {"sparse_infill_density": f"{d}%"}, a.work / f"d{d}")
        s = read_sliced_3mf(run.output_3mf, a.plate, run.result_json)
        assert s.config["sparse_infill_density"] == f"{d}%", s.config
        g = s.feature_g
        cli = dict(sparse=g.get("Sparse infill", 0), bridge=g.get("Bridge", 0),
                   solid=g.get("Internal solid infill", 0), total=s.total_g,
                   time_min=s.total_time_s / 60)
        ref = GUI.get(d)
        if ref:
            diffs = {k: pct(cli[k], ref[k]) for k in ("sparse", "bridge", "solid", "total")}
            diffs["time"] = pct(cli["time_min"], minutes(ref["time"]))
            ok = all(abs(v) <= TOLERANCE * 100 for v in diffs.values())
        else:
            diffs = {"total": pct(cli["total"], GUI_TOTAL_ONLY[d])}
            ok = abs(diffs["total"]) <= TOLERANCE * 100
        if not ok:
            failures.append(d)
        rows.append((d, cli, ref or {"total": GUI_TOTAL_ONLY[d]}, diffs, ok, s.total_time))
        const_rows.append((d, {k: g.get(k, 0) for k in GUI_CONSTANT}))
        run.output_3mf.unlink()
        print(f"{d:>3}%  total {s.total_g:7.2f} g  {'OK' if ok else 'DIFF'}")

    def fmt(v, digits=2):
        return f"{v:.{digits}f}"

    md = ["# CLI 與 GUI 數據對照", "",
          "由 `tools/verify_gui.py` 產生。CLI：Bambu Studio 2.7.1.62，"
          "使用 3MF 內嵌設定，只以 `--sparse-infill-density` 覆蓋密度。",
          "差異 = (CLI − GUI) / GUI；|差異| ≤ 1% 視為一致。時間以分鐘比較（GUI 只記錄到分鐘）。", "",
          "## 必驗項目（3%、11%、13%）與其他 GUI 實測密度", "",
          "| 密度 | 項目 | GUI | CLI | 差異 |", "|---|---|---|---|---|"]
    labels = [("total", "總用料 (g)"), ("bridge", "橋接 (g)"), ("sparse", "稀疏填充 (g)"),
              ("solid", "內部實心填充 (g)"), ("time", "總時間")]
    for d, cli, ref, diffs, ok, ttext in rows:
        if d not in GUI:
            continue
        mark = "**" if d in REQUIRED else ""
        for key, label in labels:
            if key == "time":
                gui_v, cli_v = ref["time"], f"{ttext}"
            else:
                gui_v, cli_v = fmt(ref[key]), fmt(cli[key])
            md.append(f"| {mark}{d}%{mark} | {label} | {gui_v} | {cli_v} | {diffs[key]:+.2f}% |")
    md += ["", "## 只有總用料的 GUI 數據", "", "| 密度 | GUI 總用料 | CLI 總用料 | 差異 |", "|---|---|---|---|"]
    for d, cli, ref, diffs, ok, _ in rows:
        if d in GUI_TOTAL_ONLY:
            md.append(f"| {d}% | {fmt(ref['total'])} | {fmt(cli['total'])} | {diffs['total']:+.2f}% |")
    md += ["", "## 應固定不變的項目（g）", "",
           "| 密度 | " + " | ".join(GUI_CONSTANT) + " |", "|---" * (len(GUI_CONSTANT) + 1) + "|",
           "| GUI | " + " | ".join(fmt(v) for v in GUI_CONSTANT.values()) + " |"]
    for d, vals in const_rows:
        md.append(f"| {d}% | " + " | ".join(fmt(v) for v in vals.values()) + " |")
    md += ["", "## 換算說明", "",
           "- 依 G-code 的 `; FEATURE: <類型>` 註解分段，只加總「有 X/Y/Z 移動且 E 增加」的擠出量；"
           "純 E 移動（回抽、退料、沖刷）不計入任何類型，與 GUI 的 GCodeProcessor 相同。",
           "- 重量 = 長度 × π × (線徑/2)² × 密度；線徑與密度從切片後 3MF 的 "
           "`Metadata/project_settings.config`（`filament_diameter`、`filament_density`）讀取。",
           "- G-code 有一類 `Floating vertical shell`，GUI「走線類型」沒有這一列。"
           "11% 時它是 12.84 g，加上 `Internal solid infill` 的 18.40 g 正好是 GUI 的內部實心填充 31.24 g，"
           "所以工具把它併入內部實心填充（其他密度也全部吻合）。",
           "- 各類型加總長度與 G-code 標頭 `total filament length` 完全相同。"]
    md += ["", "## 結論", "",
           ("全部一致（差異都在 1% 以內）。" if not failures
            else "差異超過 1% 的密度：" + "、".join(f"{d}%" for d in failures))]
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"wrote {a.out}; failures: {failures or 'none'}")
    return 1 if any(d in REQUIRED for d in failures) else 0


if __name__ == "__main__":
    sys.exit(main())
