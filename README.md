<div align="center">

# bambu-slicer-sweep

**English** · [繁體中文](README.zh-TW.md)

Slice a 3MF with the Bambu Studio CLI across many sparse infill densities (and patterns), collect filament usage, print time and per-line-type usage, and find the setting that uses the least material.

[Usage guide](docs/usage.md) · [Design notes](docs/design.md) · [CLI vs GUI check](docs/verification.md) · [Example sweep result](results/blade_gyroid_density_5-15/summary.txt)

![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)
![Bambu Studio](https://img.shields.io/badge/Bambu%20Studio-2.7.1.62-00AE42)
![Platform](https://img.shields.io/badge/platform-Windows-0078D6?logo=windows&logoColor=white)
![Tests](https://img.shields.io/badge/tests-unittest-brightgreen)
![License](https://img.shields.io/badge/license-MIT-blue)

</div>

```text
> python -m slicer_sweep "input/model.3mf" --range 5 15 1 --lang en

Density  Total g  Sparse g  Bridge g  Sparse+Bridge g  Int. solid g  Total time  Marks
-------  -------  --------  --------  ---------------  ------------  ----------  ------------------------
5%        114.67      6.64     45.48            52.12         31.69   4h 31m 1s
6%        117.83      7.79     47.65            55.44         31.53  4h 37m 13s
7%        106.65      9.35     35.03            44.39         31.39  4h 17m 11s
8%        105.17     10.86     32.34            43.20         31.10  4h 15m 27s
9%        113.27     11.93     39.44            51.37         31.03  4h 30m 33s
10%       106.74     13.56     29.85            43.41         32.46  4h 16m 23s
11%       102.45     15.29     25.06            40.35         31.24  4h 10m 23s  ★least filament ⏱fastest
12%       110.71     16.20     32.45            48.64         31.20  4h 25m 48s
13%       105.31     17.81     25.64            43.45         31.00  4h 15m 40s
14%       106.15     18.92     25.27            44.19         31.10  4h 17m 30s
15%       106.75     20.41     24.28            44.69         31.19   4h 20m 9s

Least filament: 11% (102.45 g, 4h 10m 23s)
Shortest time: 11% (102.45 g, 4h 10m 23s)
```

Messages are in English or Traditional Chinese, chosen from the Windows display language; force one with `--lang en` or `--lang zh-TW`.

## ✨ Features

- Uses the printer, filament and process settings embedded in the 3MF and overrides only the swept values from the command line
- Densities as a list or a range with a step, decimals allowed (e.g. `10.5`)
- Sweep several infill patterns at once, and pin other settings with `--set`
- Per-line-type usage computed from the G-code `; FEATURE:` markers, converted the same way as the GUI (the [CLI vs GUI check](docs/verification.md) agrees within 0.2%)
- CSV plus a terminal summary that marks the least-filament and fastest runs and shows sparse infill + bridge
- After every slice the applied settings are read back from the G-code to confirm the override took effect

## 🚀 Quick start

Requirements: Windows, Python 3.14, Bambu Studio 2.7 (default path `C:\Program Files\Bambu Studio\bambu-studio.exe`). Standard library only, nothing to install; run it from the project folder.
The examples assume the 3MF is at `input\model.3mf` (`input\` is git-ignored); any path works.

```powershell
python -m slicer_sweep "input\model.3mf" --range 5 15 1
```

## 📖 Usage

```powershell
python -m slicer_sweep <3MF path> <densities> [options]
```

`<densities>` is required: `-d`, `-r`, or both. Everything else is optional:

| Option | Default | Description |
|---|---|---|
| `-d 3,10.5,11` | — | Density list (%), comma-separated, decimals allowed |
| `-r 5 15 1` | — | Density range: start, end, step; **the end value is included** |
| `-p gyroid,grid` | pattern in the 3MF | Infill patterns (Bambu setting values such as `gyroid`, `grid`, `cubic`, `adaptivecubic`, `honeycomb`, `lightning`); every pattern runs every density |
| `--set wall_loops=3` | — | Extra setting applied to every slice; repeatable |
| `--plate 2` | `1` | Plate number |
| `-o results\xxx` | `results\<model>_<time>` | Output folder |
| `--keep` | off | Keep the sliced `.gcode.3mf` of every run |
| `--timeout 600` | `300` | Timeout per slice, in seconds |
| `--exe PATH` | `C:\Program Files\Bambu Studio\bambu-studio.exe` | Bambu Studio executable |
| `--lang en` | Windows display language | Output language: `en` or `zh-TW` |

Examples:

```powershell
# A few densities (decimals allowed)
python -m slicer_sweep "input\model.3mf" -d 3,10.5,11,13

# 8%-14% x three patterns (21 slices), keep the gcode.3mf files, custom output folder
python -m slicer_sweep "input\model.3mf" -r 8 14 1 -p gyroid,grid,cubic --keep -o results\patterns

# Plate 2, walls fixed at 3, 10-minute timeout
python -m slicer_sweep model.3mf --plate 2 -d 10,15 --set wall_loops=3 --timeout 600
```

The output folder contains `sweep.csv` (one row per slice) and `summary.txt` (the terminal summary table); with `--keep` it also holds each `.gcode.3mf`.
Exit code is 0 when every slice succeeds, 1 when any slice fails, 2 for invalid arguments or when objects have their own value for a swept setting (nothing is sliced then).

The full guide (density syntax, pattern names, decimal densities, error messages) is in **[docs/usage.md](docs/usage.md)**.

<details>
<summary>CSV columns</summary>

Weights are in grams, converted with the filament density and diameter stored in the 3MF; line types match the GUI preview "Line type" statistics.

| Column | Description |
|---|---|
| `pattern` | Infill pattern (actual value read back from the G-code) |
| `density_pct` | Sparse infill density (%) |
| `status` | `ok` or `error` |
| `total_g` | Total filament (slicer's own value, same as the GUI) |
| `sparse_plus_bridge_g` | Sparse infill + bridge |
| `sparse_infill_g` | Sparse infill |
| `bridge_g` | Bridge (including internal bridges) |
| `internal_solid_infill_g` | Internal solid infill (includes the G-code type `Floating vertical shell`) |
| `top_surface_g` / `bottom_surface_g` | Top / bottom surface |
| `inner_wall_g` / `outer_wall_g` | Inner / outer wall |
| `gap_infill_g` | Gap infill |
| `custom_g` | Custom (e.g. the purge line in the start G-code) |
| `other_g` | Any other line type (e.g. support) |
| `filament_m` | Filament length (m) |
| `total_time` / `total_time_s` | Total time including preparation, as text and seconds |
| `print_time` | Model print time, excluding preparation |
| `slice_seconds` | How long the slice took |
| `gcode_3mf` | Kept file name when `--keep` is used |
| `error` | Failure reason |

The CSV is written as UTF-8 with BOM so Excel opens it correctly.

</details>

## 🔒 Safety

- The original 3MF is never modified: it is copied into `_work\` in the output folder before slicing, and the temporary files are removed afterwards
- Nothing is read from `%AppData%\BambuStudio` or the install folder; all settings come from the 3MF
- Only one slicer process runs at a time; on timeout the whole process tree is killed, and a slicer whose process Windows cannot tear down is detected so the sweep carries on
- Ctrl+C stops the running slicer process before exiting

## 🧪 Development

```powershell
python -m unittest discover -s tests -t .
```

Compare against GUI measurements (13 slices; regenerates [docs/verification.md](docs/verification.md) and its Traditional Chinese version):

```powershell
python tools\verify_gui.py "input\model.3mf"
```

<details>
<summary>Project layout</summary>

```text
slicer_sweep/
  cli.py           command-line options, terminal summary table
  sweep.py         sweep loop, CSV, best-run selection
  bambu.py         runs bambu-studio.exe (timeout, process-tree kill)
  _launch.py       hidden-console helper that starts the slicer and detects a stuck teardown
  sliced.py        reads the gcode.3mf: header, settings, filament density
  gcode_stats.py   sums extruded length per ; FEATURE: line type
  i18n.py          English / Traditional Chinese messages
tests/             unit tests
tools/
  verify_gui.py       CLI vs GUI comparison
  capture_console.py  captures bambu-studio --help (it writes only to the console)
docs/              usage guide, design notes, verification, CLI --help output
results/           sweep results
```

</details>

## 📚 Docs

Each document also has a Traditional Chinese version (`*.zh-TW.md`).

- [Usage guide](docs/usage.md): every option, pattern names, output and error messages
- [Design notes](docs/design.md): why command-line overrides, how the G-code is converted, process handling
- [CLI vs GUI check](docs/verification.md)
- [Bambu Studio 2.7.1.62 `--help` output](docs/bambu-cli-help.txt)

## ⚠️ Limitations

- Windows only (uses `taskkill` and Windows process groups); verified only with Bambu Studio 2.7.1.62
- Option names must be Bambu setting keys; for an invalid name or value the slicer only returns exit code -2, with no explanation
- Only `sparse_infill_density` and `sparse_infill_pattern` are checked after slicing; other `--set` values are not read back
- If objects or parts on the plate have their own value for a swept or `--set` setting, the command-line override may not apply to them; the tool lists those objects and stops without slicing
- Multi-filament 3MF: per-line-type weights all use the first filament's density and diameter (the total is still the slicer's correct value)
- Times are the slicer's estimates, same as the GUI, not actual print times
- In about 2-5% of slices the slicer exits normally but Windows cannot tear its process down (probably the graphics driver). Results are unaffected, but that slice's temp folder cannot be deleted until you restart; the tool tells you when this happens. See the [design notes](docs/design.md#a-slicer-that-exits-but-cannot-be-cleaned-up)
- Decimal densities (e.g. 10.5%) are honoured by the CLI, but the GUI may not accept the same value; to print one, use the `.gcode.3mf` kept with `--keep`

## License

[MIT](LICENSE)
