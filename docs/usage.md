# Usage guide

**English** · [繁體中文](usage.zh-TW.md)

## Syntax

```powershell
python -m slicer_sweep <3MF path> <densities> [options]
```

- `<3MF path>`: the 3MF to slice. The printer, filament and process settings embedded in it are used; only the values you sweep are overridden, and the original file is never modified.
- `<densities>`: required, given with `-d`, `-r` or both (see the next section).
- Quote paths that contain spaces or non-ASCII characters.
- Run it from the project folder (`-m slicer_sweep` loads the code from the current folder). It uses only the Python standard library; nothing needs to be installed.
- `python .\slicer_sweep\ …` (what PowerShell tab completion produces) works the same way.

## Densities

| Written as | Densities sliced |
|---|---|
| `-d 11` | 11% |
| `-d 3,10.5,11,13` | 3%, 10.5%, 11%, 13% (comma-separated, decimals allowed, `%` optional) |
| `-r 5 15 1` | 5%, 6%, …, 15% (start, end, step; **the end value is included**) |
| `-r 10 12 0.5` | 10%, 10.5%, 11%, 11.5%, 12% |
| `-r 5 15 1 -d 10.5` | 5%–15% in 1% steps, plus 10.5% (duplicates are sliced once) |

Densities must be between 0 and 100.

> **Decimal densities**: the Bambu Studio 2.7.1.62 CLI really uses decimal values. At 10.5% the G-code
> settings read `sparse_infill_density = 10.5%` and the total is 108.38 g, different from both 10% (106.74 g)
> and 11% (102.45 g), so the value is not rounded. The GUI, however, may not accept the same decimal value, so a
> decimal-density result may not be reproducible there. To print one, add `--keep` and print the kept `.gcode.3mf`.

## Infill patterns

```powershell
python -m slicer_sweep "input\model.3mf" -r 8 14 1 -p gyroid,grid,cubic
```

- `-p` takes comma-separated pattern names; every pattern runs every density (3 × 7 = 21 slices above).
- Without `-p` the pattern embedded in the 3MF is used.
- Names are Bambu Studio setting values (lower-case), not the names shown in the GUI. Verified to work:

  | Setting value | GUI name |
  |---|---|
  | `gyroid` | Gyroid |
  | `grid` | Grid |
  | `cubic` | Cubic |
  | `adaptivecubic` | Adaptive Cubic |
  | `honeycomb` | Honeycomb |
  | `lightning` | Lightning |

  An unknown name makes that slice fail with "exit code -2"; the other combinations continue.

## Pinning other settings

```powershell
python -m slicer_sweep "input\model.3mf" -d 10,11 --set wall_loops=3 --set top_shell_layers=5
```

`--set KEY=VALUE` can be repeated; every slice uses the same values. Keys are the names found in the 3MF's
`Metadata/project_settings.config` or in the `; CONFIG_BLOCK` at the end of the G-code (underscores or hyphens both work).
Density and pattern must be given with `-d` / `-r` / `-p`, not with `--set`.

> Only density and pattern are read back and checked after slicing; `--set` values are not. Use `--keep` and check the files yourself.

## Other options

| Option | Default | Description |
|---|---|---|
| `--plate N` | `1` | Plate to slice (1-based). If the plate does not exist, the plates in the 3MF are listed |
| `-o, --out-dir FOLDER` | `results\<model>_<date-time>` | Output folder, created if missing; an existing `sweep.csv` / `summary.txt` in it is overwritten |
| `--keep` | off | Keep each slice's `.gcode.3mf`, to open in Bambu Studio or print directly |
| `--timeout SECONDS` | `300` | Time limit per slice; a slice that exceeds it is stopped and recorded as failed |
| `--exe PATH` | `C:\Program Files\Bambu Studio\bambu-studio.exe` | For a Bambu Studio installed elsewhere |
| `--lang en` / `--lang zh-TW` | Windows display language (Chinese → `zh-TW`, otherwise `en`) | Language of terminal messages, the summary table and `summary.txt`; CSV column names are always English |

## Progress and output

Each finished slice prints one progress line:

```text
[7/11] gyroid 11%   102.45 g  4h 10m 23s  (sliced in 2.5 s)
```

When everything is done a summary table is printed with these marks:

- `★least filament`: the run with the least total filament
- `⏱fastest`: the run with the shortest total time

Ties (rounded to 0.01 g / 1 s) are all marked. When several patterns are swept, the least-filament density of each pattern is listed too.

The output folder contains:

| File | Content |
|---|---|
| `sweep.csv` | One row per slice; columns are described under "CSV columns" in the [README](../README.md#-usage) |
| `summary.txt` | The same summary table as the terminal |
| `<model>_plate<N>_<pattern>_<density>.gcode.3mf` | Only with `--keep` |

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Every slice succeeded |
| `1` | At least one slice failed (the other results are still in the CSV) |
| `2` | Invalid arguments, file not found or no such plate; nothing was sliced |
| `130` | Ctrl+C (the running slicer process is stopped) |

## Common messages

| Message | Cause and fix |
|---|---|
| `invalid arguments: specify densities with --densities or --range` | Neither `-d` nor `-r` was given |
| `slicing failed: exit code -2 (usually an invalid option name or value)` | A `-p` or `--set` name or value is misspelt |
| `timed out after 300 s; slicer stopped` | The model is too complex; raise `--timeout` |
| `setting was not applied (G-code has …)` | The slicer did not use the override; that result is not trustworthy and is recorded as failed |
| `warning: the slicer exited normally but Windows could not tear its process down …` | Happens in about 2–5% of slices; the result is still valid. See the [design notes](design.md#a-slicer-that-exits-but-cannot-be-cleaned-up) |
| `warning: temp folder … could not be deleted` | The process above keeps its temp folder; it can be deleted after a restart |
| `warning: the slicer did not exit 30 s after writing its results and was stopped` | Fallback mechanism; the result is still valid |
| `warning: the 3MF has a per-object/part …` | Some objects have their own infill settings in the GUI; the command-line override may not apply to them |
