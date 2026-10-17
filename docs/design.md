# Design notes

**English** · [繁體中文](design.zh-TW.md)

## Why command-line overrides instead of editing the 3MF

The Bambu Studio 2.7.1.62 CLI accepts single settings by key name, with higher priority than the settings embedded in the 3MF:

```
bambu-studio --sparse-infill-density 10.5% --slice 1 --export-3mf out.gcode.3mf model.3mf
```

Tested behaviour (see [bambu-cli-help.txt](bambu-cli-help.txt) and [verification.md](verification.md)):

| Written as | Result |
|---|---|
| `--sparse-infill-density 3%` (hyphens) | Works; the G-code CONFIG block reads `sparse_infill_density = 3%` |
| `--sparse-infill-density 3` (no %) | Works, same as above |
| `--sparse-infill-density 10.5%` (decimal) | Works |
| `--sparse-infill-pattern grid` | Works |
| `--sparse_infill_density 3%` (underscores) | Fails with exit code -2 and no output |
| Unknown pattern name | Fails with exit code -2 |

So there is no need to copy and rewrite the 3MF's `project_settings.config`. Every other setting keeps its
embedded value, and the presets in `%AppData%\BambuStudio` are never read. The tool still copies the 3MF into
`_work/` in the output folder before handing it to the slicer, so the original is never touched.

After every slice the tool reads `sparse_infill_density` / `sparse_infill_pattern` back from the output G-code's
`; CONFIG_BLOCK`; if they differ from what was requested the slice is marked as failed instead of silently using
the wrong settings.

## Why parse the G-code

The slicer reports only total weight and total time (in `result.json` and the G-code header). Per-line-type usage has to be computed from the G-code:

- Split by the `; FEATURE: <type>` comments.
- Count only moves that travel in X/Y/Z *and* advance E; pure E moves (retract, unretract, purge) belong to no type.
  This matches the GUI's GCodeProcessor: the 30.04 mm XY purge line in the start G-code is exactly the GUI's "Custom 0.09 g".
- `M82` / `M83` / `G92` and `G2` / `G3` arcs are handled.
- Weight = length × π × (diameter / 2)² × density, with diameter and density read from the sliced 3MF's
  `filament_diameter` and `filament_density`, not hard-coded.
- `Floating vertical shell` is its own type in the G-code, but the GUI "Line type" legend has no such row;
  its usage plus `Internal solid infill` equals the GUI's "Internal solid infill", so it is merged into that type.

The per-type lengths add up exactly to the G-code header's `total filament length`; the tool warns if they do not.

## Process handling and timeouts

- Only one `bambu-studio.exe` runs at a time; the default timeout is 300 s.
- `bambu-studio.exe` attaches to its **parent's** console and writes its log there (`[trace]`, `ZFiller: …`, …).
  Redirecting stdout/stderr, `DETACHED_PROCESS`, `CREATE_NO_WINDOW` and `CREATE_NEW_CONSOLE` do not stop it, and
  `--debug 0` still leaves one line. So the tool starts a tiny Python helper that owns a hidden console, and the
  helper starts the slicer and passes its exit code through; the log only reaches that invisible console.
- Waiting is a deadline-bound poll, never an unbounded wait. On timeout the whole process tree is killed with
  `taskkill /F /T` and the exit is confirmed.
- The slicer writes `result.json` to its current directory, so every slice runs in its own `_work/<combination>/`
  folder, which is deleted afterwards.

## A slicer that exits but cannot be cleaned up

In about 2–5% of slices Bambu Studio finishes its work and exits normally with code 0, but Windows cannot finish tearing the process down.

**Measurements** (the blade model sliced repeatedly, 290 slices in total):

| Launch method | Slices | Occurrences |
|---|---|---|
| bambu-studio.exe started directly | 50 | 2 |
| Through the hidden-console helper | 110 | 1 |
| Helper + polling `result.json` (what the tool does) | 50 | 2 |
| The finished tool, densities 1%–80% | 80 | 4 |

It happens with every launch method, so it is not caused by how the tool starts the slicer. The state is always the same:

- `GetExitCodeProcess` already returns 0 (the slicer exited normally), but the process object never becomes
  signalled, so a plain wait blocks forever. Waiting 90 s does not help.
- One thread remains, in state `Wait / UserRequest`, and its start address can no longer be read; `taskkill /F`
  reports that there is no running instance, and killing has no effect.
- The process still holds its open files and working directory, so `out.gcode.3mf` and the whole
  `_work/<combination>/` folder cannot be deleted until a restart.

**Probable cause**: the thread is stuck in the kernel or a driver. Every time, the process had loaded the NVIDIA
OpenGL driver (`nvoglv64.dll`) and the NVIDIA capture/overlay module (`nvspcap64.dll`). Bambu Studio loads OpenGL at
start-up even in CLI mode (for the preview thumbnails), and none of the CLI options tried avoid it
(`--skip-useless-pick` and `--min-save` make slicing fail in 2.7.1.62). Proving it would need a kernel debugger, which
was not done here; temporarily turning off the NVIDIA in-game overlay and testing again would be a further check.

**What the tool does about it**:

- The helper [slicer_sweep/_launch.py](../slicer_sweep/_launch.py) treats "exit code set but process object not
  finished" lasting 2 seconds as this case: it returns the slicer's exit code and leaves a marker file. The result
  is used as usual (when `result.json` reports success and the ZIP is complete), a warning is printed, and the
  slice only takes about 2 s longer.
- With `--keep`, the output file is still locked and cannot be moved, so it is copied instead.
- If `_work/` cannot be deleted at the end of the sweep, a message says it can be deleted after a restart.
- The original 30-second grace period (stop the slicer if it has not exited 30 s after `result.json` appears) stays as a fallback.

## Why `--help` needs special capturing

`bambu-studio.exe` writes its CLI text straight to the console, so redirecting stdout/stderr captures nothing.
[tools/capture_console.py](../tools/capture_console.py) runs the command in a hidden new console and reads the console buffer.

## Numbers

Density lists and ranges use `Decimal`, so `--range 5 6 0.1` yields exactly 11 values and floating-point error never
drops the end value. "Least filament" and "shortest time" are compared at the precision shown in the CSV (0.01 g, 1 s),
and ties are all marked.
