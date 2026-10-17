"""Command line entry point: python -m slicer_sweep MODEL.3mf --range 5 15 1"""
from __future__ import annotations

import argparse
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

from .bambu import DEFAULT_EXE, DEFAULT_TIMEOUT_S
from .i18n import LANGS, detect_lang, set_lang, t
from .sweep import RunResult, best, density_list, fmt_num, model_info, run_sweep, write_csv


def _lang_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--lang", choices=LANGS, help=t("h_lang"))
    return p


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m slicer_sweep", description=t("description"),
                                parents=[_lang_parser()])
    p.add_argument("model", type=Path, help=t("h_model"))
    p.add_argument("--plate", type=int, default=1, help=t("h_plate"))
    p.add_argument("--densities", "-d", metavar="LIST", help=t("h_densities"))
    p.add_argument("--range", "-r", nargs=3, metavar=("START", "END", "STEP"), help=t("h_range"))
    p.add_argument("--patterns", "-p", metavar="LIST", help=t("h_patterns"))
    p.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help=t("h_set"))
    p.add_argument("--out-dir", "-o", type=Path, help=t("h_out_dir"))
    p.add_argument("--keep", action="store_true", help=t("h_keep"))
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S,
                   help=t("h_timeout", default=DEFAULT_TIMEOUT_S))
    p.add_argument("--exe", type=Path, default=DEFAULT_EXE, help=t("h_exe"))
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
    headers = ([t("col_pattern")] if multi else []) + [
        t(k) for k in ("col_density", "col_total", "col_sparse", "col_bridge",
                       "col_sparse_bridge", "col_solid", "col_time", "col_marks")]
    rows = []
    for r in results:
        prefix = [r.pattern] if multi else []
        if not r.ok:
            rows.append(prefix + [fmt_num(r.density) + "%", t("failed"), "", "", "", "", "", r.error])
            continue
        f = r.features_g
        marks = " ".join(m for m, s in ((t("mark_least"), min_g), (t("mark_fastest"), min_t)) if id(r) in s)
        rows.append(prefix + [
            fmt_num(r.density) + "%", f"{r.total_g:.2f}", f"{f.get('Sparse infill', 0):.2f}",
            f"{f.get('Bridge', 0):.2f}", f"{r.sparse_plus_bridge_g:.2f}",
            f"{f.get('Internal solid infill', 0):.2f}", r.total_time, marks])
    off = 1 if multi else 0
    text = render_table(headers, rows, right={off + i for i in range(1, 7)})

    lines = [text, ""]
    sep = t("list_sep")
    for msg, key in (("best_least", "total_g"), ("best_fastest", "total_time_s")):
        b = best(results, key)
        if b:
            runs = sep.join((f"{r.pattern} " if multi else "") + fmt_num(r.density) + "%" for r in b)
            lines.append(t(msg, runs=runs, grams=b[0].total_g, time=b[0].total_time))
    if multi:
        for pat in dict.fromkeys(r.pattern for r in results):
            b = best([r for r in results if r.pattern == pat], "total_g")
            if b:
                lines.append(t("best_per_pattern", pattern=pat, grams=b[0].total_g,
                               runs=sep.join(fmt_num(r.density) + "%" for r in b)))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    pre, _ = _lang_parser().parse_known_args(argv)
    set_lang(pre.lang or detect_lang())
    args = build_parser().parse_args(argv)
    if not args.model.is_file():
        print(t("model_missing", path=args.model), file=sys.stderr)
        return 2
    if not args.exe.is_file():
        print(t("exe_missing", path=args.exe), file=sys.stderr)
        return 2
    try:
        if not args.densities and not args.range:
            raise ValueError(t("need_density"))
        densities = density_list(args.densities, *(args.range or (None, None, None)))
        if not densities:
            raise ValueError(t("empty_density"))
        extra = {}
        for item in args.set:
            k, sep, v = item.partition("=")
            if not sep or not k.strip():
                raise ValueError(t("bad_set", item=item))
            extra[k.strip()] = v.strip()
        for k in ("sparse_infill_density", "sparse_infill_pattern"):
            if k in extra:
                raise ValueError(t("set_reserved", key=k))
    except ValueError as e:
        print(t("arg_error", error=e), file=sys.stderr)
        return 2
    patterns = [p.strip() for p in args.patterns.split(",") if p.strip()] if args.patterns else None

    plates, embedded_pattern, warnings = model_info(args.model)
    if args.plate not in plates:
        print(t("no_plate", plate=args.plate, plates=", ".join(map(str, plates))), file=sys.stderr)
        return 2
    for w in warnings:
        print(t("warning", text=w), file=sys.stderr)

    out_dir = args.out_dir or Path("results") / f"{args.model.stem}_{datetime.now():%Y%m%d-%H%M%S}"
    total = len(densities) * len(patterns or [None])
    print(t("header_model", model=args.model, plate=args.plate, pattern=embedded_pattern))
    print(t("header_runs", n=total, timeout=args.timeout, out=out_dir))

    started = time.monotonic()

    def progress(i: int, n: int, r: RunResult) -> None:
        state = (t("progress_ok", grams=r.total_g, time=r.total_time, secs=r.slice_seconds)
                 if r.ok else t("progress_fail", error=r.error))
        print(f"[{i}/{n}] {r.pattern} {fmt_num(r.density)}%  {state}", flush=True)
        for w in r.warnings:
            print("    " + t("warning", text=w))

    try:
        results = run_sweep(args.model, args.plate, densities, patterns, out_dir, keep=args.keep,
                            extra=extra, exe=args.exe, timeout_s=args.timeout, progress=progress)
    except KeyboardInterrupt:
        print("\n" + t("interrupted"), file=sys.stderr)
        return 130

    csv_path = out_dir / "sweep.csv"
    write_csv(results, csv_path)
    text = summary(results)
    (out_dir / "summary.txt").write_text(
        t("summary_model", model=args.model.name, plate=args.plate) + f"\n\n{text}\n",
        encoding="utf-8")
    print()
    print(text)
    print()
    print(t("csv_written", path=csv_path, secs=time.monotonic() - started))
    return 0 if all(r.ok for r in results) else 1
