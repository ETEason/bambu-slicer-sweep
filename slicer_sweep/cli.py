"""Command line entry point: python -m slicer_sweep MODEL.3mf --range 5 15 1"""
from __future__ import annotations

import argparse
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

from .bambu import DEFAULT_EXE, DEFAULT_TIMEOUT_S
from .sweep import RunResult, best, density_list, fmt_num, model_info, run_sweep, write_csv


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m slicer_sweep",
        description="用 Bambu Studio CLI 以不同稀疏填充密度（與圖案）切片 3MF，彙整用料與時間。")
    p.add_argument("model", type=Path, help="輸入的 3MF（使用其內嵌的印表機／耗材／工藝設定）")
    p.add_argument("--plate", type=int, default=1, help="要切的盤號（從 1 開始，預設 1）")
    p.add_argument("--densities", "-d", metavar="LIST",
                   help="密度清單（%%），逗號分隔，可用小數，例如 3,10.5,11")
    p.add_argument("--range", "-r", nargs=3, metavar=("START", "END", "STEP"),
                   help="密度範圍（含結束值），例如 --range 5 15 1；可與 --densities 併用")
    p.add_argument("--patterns", "-p", metavar="LIST",
                   help="填充圖案清單，逗號分隔（Bambu 設定值，例如 gyroid,grid,cubic）；"
                        "未指定時用 3MF 內嵌的圖案")
    p.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                   help="額外固定覆蓋的設定（Bambu 設定鍵，例如 wall_loops=3），可重複")
    p.add_argument("--out-dir", "-o", type=Path,
                   help="輸出資料夾（預設 results/<模型名>_<時間>）")
    p.add_argument("--keep", action="store_true", help="保留每次切片的 gcode.3mf 到輸出資料夾")
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S,
                   help=f"每次切片的逾時秒數（預設 {DEFAULT_TIMEOUT_S}）")
    p.add_argument("--exe", type=Path, default=DEFAULT_EXE, help="bambu-studio.exe 路徑")
    return p


def _width(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def _pad(s: str, w: int, right: bool) -> str:
    fill = " " * (w - _width(s))
    return fill + s if right else s + fill


def render_table(headers: list[str], rows: list[list[str]], right: set[int]) -> str:
    widths = [max(_width(r[i]) for r in [headers] + rows) for i in range(len(headers))]
    line = lambda r: "  ".join(_pad(c, widths[i], i in right) for i, c in enumerate(r))  # noqa: E731
    sep = "  ".join("-" * w for w in widths)
    return "\n".join(s.rstrip() for s in [line(headers), sep] + [line(r) for r in rows])


def summary(results: list[RunResult]) -> str:
    min_g = {id(r) for r in best(results, "total_g")}
    min_t = {id(r) for r in best(results, "total_time_s")}
    multi = len({r.pattern for r in results}) > 1
    headers = (["圖案"] if multi else []) + ["密度", "總用料 g", "稀疏填充 g", "橋接 g",
                                             "稀疏+橋接 g", "內部實心 g", "總時間", "標記"]
    rows = []
    for r in results:
        prefix = [r.pattern] if multi else []
        if not r.ok:
            rows.append(prefix + [fmt_num(r.density) + "%", "失敗", "", "", "", "", "", r.error])
            continue
        f = r.features_g
        marks = " ".join(m for m, s in (("★最少用料", min_g), ("⏱最短時間", min_t)) if id(r) in s)
        rows.append(prefix + [
            fmt_num(r.density) + "%", f"{r.total_g:.2f}", f"{f.get('Sparse infill', 0):.2f}",
            f"{f.get('Bridge', 0):.2f}", f"{r.sparse_plus_bridge_g:.2f}",
            f"{f.get('Internal solid infill', 0):.2f}", r.total_time, marks])
    off = 1 if multi else 0
    text = render_table(headers, rows, right={off + i for i in range(1, 7)})

    lines = [text, ""]
    for title, key in (("總用料最少", "total_g"), ("時間最短", "total_time_s")):
        b = best(results, key)
        if b:
            desc = "、".join((f"{r.pattern} " if multi else "") + fmt_num(r.density) + "%" for r in b)
            lines.append(f"{title}：{desc}（{b[0].total_g:.2f} g，{b[0].total_time}）")
    if multi:
        for pat in dict.fromkeys(r.pattern for r in results):
            b = best([r for r in results if r.pattern == pat], "total_g")
            if b:
                lines.append(f"  {pat} 用料最少：{'、'.join(fmt_num(r.density) + '%' for r in b)}"
                             f"（{b[0].total_g:.2f} g）")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    if not args.model.is_file():
        print(f"找不到 3MF：{args.model}", file=sys.stderr)
        return 2
    if not args.exe.is_file():
        print(f"找不到 Bambu Studio：{args.exe}", file=sys.stderr)
        return 2
    try:
        if not args.densities and not args.range:
            raise ValueError("請用 --densities 或 --range 指定密度")
        densities = density_list(args.densities, *(args.range or (None, None, None)))
        if not densities:
            raise ValueError("密度清單是空的")
        extra = {}
        for item in args.set:
            k, sep, v = item.partition("=")
            if not sep or not k.strip():
                raise ValueError(f"--set 格式應為 KEY=VALUE：{item!r}")
            extra[k.strip()] = v.strip()
        for k in ("sparse_infill_density", "sparse_infill_pattern"):
            if k in extra:
                raise ValueError(f"{k} 請用 --densities/--range/--patterns 指定")
    except ValueError as e:
        print(f"參數錯誤：{e}", file=sys.stderr)
        return 2
    patterns = [p.strip() for p in args.patterns.split(",") if p.strip()] if args.patterns else None

    plates, embedded_pattern, warnings = model_info(args.model)
    if args.plate not in plates:
        print(f"3MF 中沒有第 {args.plate} 盤（有：{', '.join(map(str, plates))}）", file=sys.stderr)
        return 2
    for w in warnings:
        print(f"警告：{w}", file=sys.stderr)

    out_dir = args.out_dir or Path("results") / f"{args.model.stem}_{datetime.now():%Y%m%d-%H%M%S}"
    total = len(densities) * len(patterns or [None])
    print(f"模型：{args.model}（第 {args.plate} 盤，內嵌圖案 {embedded_pattern}）")
    print(f"共 {total} 次切片，每次逾時 {args.timeout:g} 秒，輸出到 {out_dir}")

    started = time.monotonic()

    def progress(i: int, n: int, r: RunResult) -> None:
        state = (f"{r.total_g:7.2f} g  {r.total_time}  （切片 {r.slice_seconds:.1f} 秒）"
                 if r.ok else f"失敗：{r.error}")
        print(f"[{i}/{n}] {r.pattern} {fmt_num(r.density)}%  {state}", flush=True)
        for w in r.warnings:
            print(f"    警告：{w}")

    try:
        results = run_sweep(args.model, args.plate, densities, patterns, out_dir, keep=args.keep,
                            extra=extra, exe=args.exe, timeout_s=args.timeout, progress=progress)
    except KeyboardInterrupt:
        print("\n已中斷（切片程序已結束）", file=sys.stderr)
        return 130

    csv_path = out_dir / "sweep.csv"
    write_csv(results, csv_path)
    text = summary(results)
    (out_dir / "summary.txt").write_text(
        f"模型：{args.model.name}（第 {args.plate} 盤）\n\n{text}\n", encoding="utf-8")
    print()
    print(text)
    print()
    print(f"CSV：{csv_path}（共 {time.monotonic() - started:.0f} 秒）")
    return 0 if all(r.ok for r in results) else 1
