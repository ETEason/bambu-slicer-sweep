"""User-facing messages in Traditional Chinese and English.

The language defaults to the Windows display language (any Chinese -> zh-TW,
otherwise en) and can be forced with ``--lang``.
"""
from __future__ import annotations

import sys

LANGS = ("zh-TW", "en")

MESSAGES: dict[str, tuple[str, str]] = {
    # key: (zh-TW, en)
    # argparse
    "description": ("用 Bambu Studio CLI 以不同稀疏填充密度（與圖案）切片 3MF，彙整用料與時間。",
                    "Slice a 3MF with the Bambu Studio CLI at different sparse infill densities "
                    "(and patterns) and summarise filament usage and print time."),
    "h_model": ("輸入的 3MF（使用其內嵌的印表機／耗材／工藝設定）",
                "input 3MF (its embedded printer/filament/process settings are used)"),
    "h_plate": ("要切的盤號（從 1 開始，預設 1）", "plate to slice (1-based, default 1)"),
    "h_densities": ("密度清單（%%），逗號分隔，可用小數，例如 3,10.5,11",
                    "density list (%%), comma-separated, decimals allowed, e.g. 3,10.5,11"),
    "h_range": ("密度範圍（含結束值），例如 --range 5 15 1；可與 --densities 併用",
                "density range, end included, e.g. --range 5 15 1; can be combined with --densities"),
    "h_patterns": ("填充圖案清單，逗號分隔（Bambu 設定值，例如 gyroid,grid,cubic）；未指定時用 3MF 內嵌的圖案",
                   "infill patterns, comma-separated (Bambu setting values, e.g. gyroid,grid,cubic); "
                   "default: the pattern in the 3MF"),
    "h_set": ("額外固定覆蓋的設定（Bambu 設定鍵，例如 wall_loops=3），可重複",
              "extra setting applied to every slice (Bambu setting key, e.g. wall_loops=3); repeatable"),
    "h_out_dir": ("輸出資料夾（預設 results/<模型名>_<時間>）",
                  "output folder (default results/<model>_<time>)"),
    "h_keep": ("保留每次切片的 gcode.3mf 到輸出資料夾", "keep each sliced gcode.3mf in the output folder"),
    "h_timeout": ("每次切片的逾時秒數（預設 {default}）", "timeout per slice in seconds (default {default})"),
    "h_exe": ("bambu-studio.exe 路徑", "path to bambu-studio.exe"),
    "h_lang": ("輸出語言（預設依 Windows 顯示語言）", "output language (default: Windows display language)"),
    # summary table
    "col_pattern": ("圖案", "Pattern"),
    "col_density": ("密度", "Density"),
    "col_total": ("總用料 g", "Total g"),
    "col_sparse": ("稀疏填充 g", "Sparse g"),
    "col_bridge": ("橋接 g", "Bridge g"),
    "col_sparse_bridge": ("稀疏+橋接 g", "Sparse+Bridge g"),
    "col_solid": ("內部實心 g", "Int. solid g"),
    "col_time": ("總時間", "Total time"),
    "col_marks": ("標記", "Marks"),
    "failed": ("失敗", "failed"),
    "mark_least": ("★最少用料", "★least filament"),
    "mark_fastest": ("⏱最短時間", "⏱fastest"),
    "best_least": ("總用料最少：{runs}（{grams:.2f} g，{time}）", "Least filament: {runs} ({grams:.2f} g, {time})"),
    "best_fastest": ("時間最短：{runs}（{grams:.2f} g，{time}）", "Shortest time: {runs} ({grams:.2f} g, {time})"),
    "best_per_pattern": ("  {pattern} 用料最少：{runs}（{grams:.2f} g）", "  {pattern} least filament: {runs} ({grams:.2f} g)"),
    "list_sep": ("、", ", "),
    # run messages
    "model_missing": ("找不到 3MF：{path}", "3MF not found: {path}"),
    "exe_missing": ("找不到 Bambu Studio：{path}", "Bambu Studio not found: {path}"),
    "need_density": ("請用 --densities 或 --range 指定密度", "specify densities with --densities or --range"),
    "empty_density": ("密度清單是空的", "the density list is empty"),
    "bad_set": ("--set 格式應為 KEY=VALUE：{item!r}", "--set must be KEY=VALUE: {item!r}"),
    "set_reserved": ("{key} 請用 --densities/--range/--patterns 指定", "use --densities/--range/--patterns for {key}"),
    "arg_error": ("參數錯誤：{error}", "invalid arguments: {error}"),
    "no_plate": ("3MF 中沒有第 {plate} 盤（有：{plates}）", "the 3MF has no plate {plate} (plates: {plates})"),
    "warning": ("警告：{text}", "warning: {text}"),
    "header_model": ("模型：{model}（第 {plate} 盤，內嵌圖案 {pattern}）",
                     "Model: {model} (plate {plate}, embedded pattern {pattern})"),
    "header_runs": ("共 {n} 次切片，每次逾時 {timeout:g} 秒，輸出到 {out}",
                    "{n} slices, timeout {timeout:g} s each, output to {out}"),
    "progress_ok": ("{grams:7.2f} g  {time}  （切片 {secs:.1f} 秒）", "{grams:7.2f} g  {time}  (sliced in {secs:.1f} s)"),
    "progress_fail": ("失敗：{error}", "failed: {error}"),
    "interrupted": ("已中斷（切片程序已結束）", "interrupted (the slicer process was stopped)"),
    "summary_model": ("模型：{model}（第 {plate} 盤）", "Model: {model} (plate {plate})"),
    "csv_written": ("CSV：{path}（共 {secs:.0f} 秒）", "CSV: {path} ({secs:.0f} s in total)"),
    # sweep / parsing
    "not_number": ("不是數字：{text!r}", "not a number: {text!r}"),
    "step_positive": ("步長必須大於 0", "the step must be greater than 0"),
    "range_order": ("範圍結束值不能小於起始值", "the range end must not be less than the start"),
    "density_bounds": ("密度必須在 0～100 之間：{value}", "density must be between 0 and 100: {value}"),
    "object_override": ("3MF 中有物件／零件層級的 {key} 設定，命令列覆蓋可能不會套用到該物件",
                        "the 3MF has a per-object/part {key}; the command-line override may not apply to it"),
    "not_applied": ("設定沒有套用（G-code 中為 {pattern} {density}）",
                    "setting was not applied (G-code has {pattern} {density})"),
    "multi_filament": ("3MF 有多個耗材，各走線類型重量一律以第 1 個耗材的密度與線徑換算",
                       "the 3MF has several filaments; per-line-type weights use the first filament's density and diameter"),
    "length_mismatch": ("各走線類型加總長度 {sum:.2f} mm 與切片器總長 {total:.2f} mm 不一致",
                        "per-line-type length {sum:.2f} mm differs from the slicer total {total:.2f} mm"),
    # slicer process
    "timeout_killed": ("逾時 {timeout:g} 秒，已結束切片程序", "timed out after {timeout:g} s; slicer stopped"),
    "timeout_stuck": ("逾時 {timeout:g} 秒，且切片程序 PID {pid} 沒有在 {wait} 秒內結束",
                      "timed out after {timeout:g} s, and slicer PID {pid} did not exit within {wait} s"),
    "exit_hang": ("切片程序寫出結果後 {grace} 秒仍未結束，已強制結束",
                  "the slicer did not exit {grace} s after writing its results and was stopped"),
    "exit_hang_unconfirmed": ("（PID {pid} 未確認結束）", " (PID {pid} not confirmed stopped)"),
    "slice_failed": ("切片失敗：exit code {code}", "slicing failed: exit code {code}"),
    "slice_failed_msg": ("，{msg}", ", {msg}"),
    "hint_bad_option": ("（通常是命令列參數名稱或設定值無效）", " (usually an invalid option name or value)"),
    "output_incomplete": ("，且輸出不完整", ", and the output is incomplete"),
    "no_output": ("切片程序結束但沒有產生 gcode.3mf", "the slicer exited without writing a gcode.3mf"),
}

_lang = "zh-TW"


def detect_lang() -> str:
    """zh-TW when the Windows display language is Chinese, otherwise en."""
    if sys.platform == "win32":
        try:
            import ctypes
            langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            return "zh-TW" if langid & 0x3FF == 0x04 else "en"  # LANG_CHINESE
        except (AttributeError, OSError):
            pass
    return "en"


def set_lang(lang: str) -> None:
    global _lang
    if lang not in LANGS:
        raise ValueError(lang)
    _lang = lang


def get_lang() -> str:
    return _lang


def t(key: str, **kw) -> str:
    text = MESSAGES[key][LANGS.index(_lang)]
    return text.format(**kw) if kw else text
