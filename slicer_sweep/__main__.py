import sys

if __package__:
    from .cli import main
else:
    # Run as a folder, e.g. `python .\slicer_sweep\` from PowerShell tab completion.
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from slicer_sweep.cli import main

sys.exit(main())
