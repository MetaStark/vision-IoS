#!/usr/bin/env python3
"""
FORWARDING SHIM — contains no logic.

Canonical implementation : 03_FUNCTIONS/ec018_alpha_daemon.py
Consolidated             : 2026-09-08, Phase 1 (12_DAILY_REPORTS/AUTONOMOUS_OPS_IMPLEMENTATION_PLAN_20260908.md)
Superseded copy          : git a21a837b (2026-02-01) — recoverable from history, never re-implemented here.

Why this file exists: any launcher or Windows Task Scheduler entry still pointing at
05_ORCHESTRATOR/ec018_alpha_daemon.py keeps working, while exactly ONE implementation exists.
Nothing here can diverge from the canonical file because nothing here is implemented.
"""
import runpy
import sys
from pathlib import Path

_here = Path(__file__).resolve()
_canonical = _here.parent.parent / "03_FUNCTIONS" / _here.name

if __name__ != "__main__":
    # Fail loud, never silent: importing the shim is a wiring error.
    raise ImportError(
        f"{_here.name} under 05_ORCHESTRATOR is a forwarding shim with no symbols. "
        f"Import the canonical module from 03_FUNCTIONS instead: {_canonical}"
    )

if not _canonical.is_file():
    sys.exit(f"SHIM ERROR: canonical implementation missing: {_canonical}")

# Make execution indistinguishable from invoking the canonical file directly:
#  - argv[0]     -> argparse 'prog' and any dirname(argv[0]) logic see the canonical path
#  - sys.path[0] -> sibling imports (daemon_lock, forecast_confidence_damper, ...) resolve in 03_FUNCTIONS
sys.argv[0] = str(_canonical)
sys.path[0] = str(_canonical.parent)
runpy.run_path(str(_canonical), run_name="__main__")
